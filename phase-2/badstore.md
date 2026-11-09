# BadStore — Writeup d'exploitation (Vulnerabilities Exploitation)

> **Cible :** BadStore.net (VM volontairement vulnérable)
> **Attaquant :** Kali Linux — réseau de lab isolé
> **Contexte :** ESEO — spécialité Cloud, Système & Sécurité

> ⚠️ **Périmètre.** BadStore est une VM *volontairement* vulnérable, lancée en local. Aucune cible tierce, aucune donnée réelle. Ces manipulations sont illégales hors d'un environnement que l'on possède ou pour lequel on a une autorisation écrite.

> 📸 **Captures :** à chaque bloc marqué *Capture*, insérer la capture prise sur la VM. Montrer l'URL/le payload **et** le résultat dans la même image quand c'est possible.

## Sommaire

0. [Recon — trouver la VM depuis Kali](#0-recon--trouver-la-vm-depuis-kali)
1. [robots.txt & exploitation](#1-robotstxt--exploitation)
2. [XSS → pop-up « plop! »](#2-xss--pop-up-plop)
3. [Parameter tampering → Secret Admin Menu](#3-parameter-tampering--secret-admin-menu)
4. [SQLi — bypass du login principal](#4-sqli--bypass-du-login-principal)
5. [SQLi — l'objet d'invisibilité](#5-sqli--lobjet-dinvisibilité)
6. [Création d'un compte admin via l'inscription](#6-création-dun-compte-admin-via-linscription)
7. [Cookie tampering → acheter à 9.99 $](#7-cookie-tampering--acheter-à-999-)
8. [Récap défensif](#8-récap-défensif)

---

## 0. Recon — trouver la VM depuis Kali

BadStore démarre sans IP affichée : il faut la découvrir sur le sous-réseau du lab.

```bash
# ton IP / sous-réseau
ip a

# découverte des hôtes actifs (adapter le /24)
sudo netdiscover -r 192.168.56.0/24
# ou
sudo nmap -sn 192.168.56.0/24

# une fois l'IP trouvée, scan des services
sudo nmap -sV -p- 192.168.56.XXX
```

**Ce que tu cherches :** un hôte avec le **port 80 (HTTP)** ouvert, bannière Apache. C'est BadStore. Toute l'appli passe par `http://<IP>/cgi-bin/badstore.cgi?action=…`.

> 📸 **Capture 0 :** le résultat du `nmap -sV` montrant l'hôte et le port 80/Apache.

---

## 1. robots.txt & exploitation

### À quoi sert robots.txt ?

Fichier texte à la racine (`http://<IP>/robots.txt`) appliquant le **Robots Exclusion Protocol**. Il **demande** aux robots d'indexation de ne pas parcourir certains chemins (directives `Disallow`).

- Ce n'est **pas** un mécanisme de sécurité : convention **volontaire**, qu'un attaquant ignore.
- Paradoxe : en listant les dossiers « à cacher », il **révèle** les chemins sensibles.

### Exploitation

```bash
curl http://<IP>/robots.txt
```

Contenu typique :

```
User-agent: *
Disallow: /cgi-bin
Disallow: /backup
Disallow: /supplier
```

Le dossier intéressant est `/backup`. Le visiter directement :

```
http://<IP>/backup/
```

**Pourquoi c'est exploitable :** le listing du dossier est activé et expose une **sauvegarde** du site (archive / dump). On y récupère la structure de la base — notamment la table `userdb` et ses colonnes (email, passwd, role…). Matière première pour les injections SQL (questions 4 et 5).

> 📸 **Capture 1 :** (a) le contenu de `robots.txt`, (b) le listing de `/backup/` avec le fichier de sauvegarde visible.

---

## 2. XSS → pop-up « plop! »

Objectif : faire surgir une `alert('plop!')`. Point le plus simple : le **champ de recherche**, qui renvoie la saisie sans l'échapper (XSS réfléchi).

```html
<script>alert('plop!')</script>
```

Via l'URL :

```
http://<IP>/cgi-bin/badstore.cgi?action=search&searchquery=<script>alert('plop!')</script>
```

**Pourquoi ça marche :** l'application réaffiche la recherche (« Results for : … ») en insérant la valeur brute dans le HTML. Le navigateur ne distingue pas « donnée » de « code » : il exécute la balise `<script>`.

> 💡 **Variante stockée (bonus) :** poste le même payload dans le **guestbook** (`action=guestbook`). L'alerte repart alors pour *chaque* visiteur — montre la différence réfléchi vs stocké.

> 📸 **Capture 2 :** la boîte « plop! » avec l'URL/le champ contenant le payload visible.

---

## 3. Parameter tampering → Secret Admin Menu

Toutes les pages sont pilotées par le paramètre `action`. Le menu d'administration n'a pas de lien visible, mais il suffit de **forcer** la bonne valeur.

```
http://<IP>/cgi-bin/badstore.cgi?action=admin
```

**Pourquoi ça marche :** c'est du **parameter tampering** — on modifie un paramètre supposé « non devinable ». Le serveur n'applique **aucun contrôle d'accès côté serveur** : il se contente de ne pas *afficher* le lien. Masquer un lien n'est pas protéger une fonction (*security through obscurity*).

> 📸 **Capture 3 :** la page « Secret Admin Menu » affichée, avec l'URL `?action=admin`.

---

## 4. SQLi — bypass du login principal

Objectif : passer le **login principal** (pas le supplier login) sans identifiants. Requête visée :

```sql
SELECT … FROM userdb WHERE email='$email' AND passwd='$pass'
```

**Payload (champ Email) :**

```sql
' OR 1=1 #
```

Mot de passe : n'importe quoi. Variante : `' OR '1'='1`.

**Pourquoi ça marche :** le `'` ferme la chaîne de l'email, `OR 1=1` rend la condition **toujours vraie**, et `#` (ou `-- `) commente le reste — dont la vérification du mot de passe. La requête retourne la **première ligne** de `userdb` (le compte admin).

> 💡 **Tip — cibler un compte précis :** `' OR email='admin@badstore.net' #` dans le champ email.

> 📸 **Capture 4 :** (a) le payload dans le champ email, (b) la page connectée.

---

## 5. SQLi — l'objet d'invisibilité

Objectif : afficher un article **caché** du catalogue (celui qui donne l'invisibilité). On injecte pour **tout** faire remonter.

**Payload (champ de recherche) :**

```sql
' OR 1=1 #
```

Ou via l'URL de listing :

```
http://<IP>/cgi-bin/badstore.cgi?action=viewitems&category=' OR '1'='1
```

**Pourquoi ça marche :** l'appli filtre l'affichage par une clause `WHERE` (catégorie, ou un flag qui masque certains produits). `OR 1=1` rend la condition universelle : **toutes** les lignes remontent, le produit « invisible » inclus. L'objet n'était pas absent, juste filtré à l'affichage.

> 💡 **Pour aller plus loin (UNION) :** une fois le nombre de colonnes connu (`ORDER BY n`), reconstruire l'affichage avec `UNION SELECT` pour extraire `itemnum, sdesc, price` de l'article caché — utile pour la question 7.

> 📸 **Capture 5 :** la liste où apparaît l'objet d'invisibilité, payload visible. Noter son **itemnum** et son prix.

---

## 6. Création d'un compte admin via l'inscription

Objectif : s'inscrire en **administrateur**. Le formulaire d'inscription (`action=register`) envoie un champ **caché** `role` qui vaut `U` (user) par défaut. On le falsifie en `A` (admin).

### Méthode — intercepter et modifier le POST

1. Configurer le navigateur via **Burp Suite** (proxy `127.0.0.1:8080`), **Intercept ON**.
2. Remplir le formulaire normalement et cliquer **Register**.
3. Dans la requête interceptée, changer `role=U` en `role=A`. S'il est absent, l'**ajouter** : `&role=A`.
4. **Forward** la requête. Le compte est créé avec le rôle administrateur.

**Pourquoi ça marche :** le niveau de privilège est décidé par une valeur **envoyée par le client** et jamais revalidée côté serveur. Règle d'or : **tout ce qui vient du client est falsifiable** (champ caché, menu déroulant, cookie).

> 💡 **Sans Burp :** sauvegarder la page HTML, éditer la valeur du champ caché `role`, puis soumettre le formulaire modifié.

> 📸 **Capture 6 :** (a) la requête Burp avec `role=A`, (b) la confirmation d'inscription, (c) l'accès aux fonctions admin.

---

## 7. Cookie tampering → acheter à 9.99 $

Objectif : acheter l'objet d'invisibilité (trop cher) pour **9.99 $**. BadStore stocke le **panier dans un cookie** côté client, prix compris — donc modifiable.

### Méthode

1. Ajouter l'objet au panier, puis ouvrir les cookies : `F12` → **Application / Stockage** → Cookies (ou une extension *Cookie-Editor*, ou Burp).
2. Repérer le cookie du panier. Sa valeur est généralement **encodée en Base64**. La décoder :
   ```bash
   echo 'VALEUR_DU_COOKIE' | base64 -d
   ```
   Apparaissent les articles et leur **prix** (ex. `itemnum:price:qty`).
3. Remplacer le prix de l'objet par `9.99`, puis ré-encoder :
   ```bash
   echo 'PANIER_MODIFIE' | base64
   ```
4. Coller la nouvelle valeur dans le cookie, recharger le panier, passer commande.

**Pourquoi ça marche :** le prix fait autorité alors qu'il est **stocké chez le client**. Le serveur fait confiance au cookie au lieu de recalculer le total depuis sa base. Même faute que la question 6 : **confiance en une donnée côté client**.

> ⚠️ **Format variable :** selon la version de BadStore, le cookie encode le prix différemment (ou le total global). Décoder d'abord pour voir la structure réelle, puis ne modifier que le champ prix.

> 📸 **Capture 7 :** (a) le cookie décodé (prix d'origine), (b) le cookie modifié à 9.99, (c) le récap de commande affichant 9.99 $.

---

## 8. Récap défensif

| Exploit                      | Cause racine                          | Correctif                                                      |
|------------------------------|---------------------------------------|---------------------------------------------------------------|
| robots.txt / backup          | Dossiers sensibles exposés + listing  | Pas de données sensibles dans la racine web ; désactiver l'autoindex ; contrôle d'accès |
| XSS                          | Sortie non encodée                    | Encodage HTML en sortie + CSP                                 |
| Parameter tampering (admin)  | Fonction protégée par l'obscurité     | Contrôle d'autorisation côté serveur sur chaque action        |
| SQLi (login, articles)       | Requête concaténée                    | Requêtes préparées / paramétrées ; moindre privilège DB       |
| Rôle admin à l'inscription   | Privilège décidé par le client        | Rôle fixé côté serveur, jamais depuis le formulaire           |
| Cookie tampering (prix)      | Prix de confiance stocké côté client  | Recalculer le prix côté serveur ; signer/chiffrer les cookies |

> 💡 **Fil rouge :** **ne jamais faire confiance à ce qui vient du client** (champ caché, cookie, paramètre d'URL) et **séparer code et données** (requêtes préparées).

---

*Writeup BadStore — environnement de lab isolé. Usage strictement pédagogique, sur VM volontairement vulnérable.*
