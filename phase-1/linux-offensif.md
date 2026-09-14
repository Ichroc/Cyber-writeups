# Linux — Permissions & escalade de privilèges (référence complète)
 
> Write-up Semaine 2, pilier 1. Objectif : maîtriser les permissions Linux **sous tous les angles** — modèle de base, bits spéciaux, vecteurs offensifs de privesc, défense, et questions-pièges. Toute manipulation offensive est à faire **uniquement sur ma VM de lab / cibles autorisées**.
 
---
 
## 1. Le modèle de permissions
 
### 1.1 Le principe : 3 catégories × 3 droits
Chaque fichier appartient à **un propriétaire (user)** et **un groupe**. Les permissions se lisent pour trois catégories :
 
- **u** (user) : le propriétaire
- **g** (group) : les membres du groupe du fichier
- **o** (others) : tous les autres
Pour chaque catégorie, trois droits : **r** (read), **w** (write), **x** (execute). Linux applique **la première catégorie qui correspond** à l'utilisateur (u, sinon g, sinon o) — il ne les cumule pas.
 
### 1.2 rwx : le sens change entre fichier et dossier (subtilité clé)
 
| Droit | Sur un **fichier** | Sur un **dossier** |
|---|---|---|
| **r** | Lire le contenu | **Lister** les noms (`ls`) |
| **w** | Modifier le contenu | **Créer / supprimer / renommer** des entrées dedans |
| **x** | Exécuter le fichier | **Traverser** le dossier (`cd`, accéder à un fichier dont on connaît le nom) |
 
**Conséquences pièges :**
- `x` sans `r` sur un dossier → on peut accéder à `dossier/fichier` **si on connaît le nom**, mais pas lister le contenu.
- **Supprimer un fichier dépend du dossier, pas du fichier.** Avoir `w` sur le dossier suffit pour supprimer un fichier qu'on ne peut même pas lire. À l'inverse, `w` sur le fichier sans `w` sur le dossier ne permet **pas** de le supprimer.
### 1.3 Décoder `ls -l` entièrement
```
-rwxr-xr--  1  alice  devs  4096  12 sep 10:00  script.sh
│└──┬──┘    │  └─┬─┘  └┬─┘   └┬─┘
│   │       │    │     │      └─ taille (octets)
│   │       │    │     └──────── groupe
│   │       │    └────────────── propriétaire
│   │       └─────────────────── nb de liens physiques
│   └─────────────────────────── 9 bits de permission (u rwx | g r-x | o r--)
└─────────────────────────────── type : - fichier · d dossier · l lien · c/b périph. · s socket · p pipe
```
Un **`+`** en fin de bloc de permissions (`-rwxr-xr--+`) = une **ACL** est posée (voir §3.8). Un **`.`** = contexte SELinux présent.
 
### 1.4 Octal ↔ symbolique
Poids : **r = 4, w = 2, x = 1**, on additionne par catégorie.
 
| Symbolique | Calcul | Octal |
|---|---|---|
| `rwx` | 4+2+1 | 7 |
| `rw-` | 4+2 | 6 |
| `r-x` | 4+1 | 5 |
| `r--` | 4 | 4 |
 
Donc `-rwxr-xr--` = **754**. Inversement, `640` = `rw-r-----`.
 
### 1.5 Modifier : chmod, chown, chgrp
```bash
chmod 754 f            # numérique (absolu)
chmod u+x,g-w f        # symbolique : +ajoute -retire =fixe ; u/g/o/a (a=all)
chmod -R o-rwx dir/    # récursif
chown alice f          # change le propriétaire
chown alice:devs f     # propriétaire + groupe
chgrp devs f           # change le groupe
```
> Seuls **root** et (pour le groupe) le propriétaire peuvent changer ces attributs. Un utilisateur ne peut pas « se donner » un fichier appartenant à un autre.
 
### 1.6 umask : les permissions par défaut
Un nouveau fichier/dossier reçoit : **permissions de base ET-NON umask** (le umask *retire* des droits).
- Base : **666** pour un fichier, **777** pour un dossier (le `x` n'est jamais donné par défaut aux fichiers).
- `umask 022` → fichier **644**, dossier **755** (valeur classique).
- `umask 027` → fichier **640**, dossier **750** (durci : rien pour « others »).
Vérifier : `umask` (affiche la valeur courante).
 
---
 
## 2. Les 3 bits spéciaux
 
Au-dessus des 9 bits normaux, trois bits « spéciaux » forment un 4ᵉ chiffre octal placé **devant** (ex. `chmod 4755`).
 
| Bit | Octal | Effet sur un **exécutable** | Effet sur un **dossier** | Affichage |
|---|---|---|---|---|
| **SUID** | 4000 | S'exécute avec l'**UID du propriétaire** du fichier | (sans effet standard) | `s`/`S` à la place du `x` de **u** |
| **SGID** | 2000 | S'exécute avec le **GID du groupe** du fichier | Les fichiers créés **héritent du groupe** du dossier | `s`/`S` à la place du `x` de **g** |
| **Sticky** | 1000 | (obsolète sur fichier) | **Suppression restreinte** : seul le propriétaire d'un fichier (ou root) peut le supprimer | `t`/`T` à la place du `x` de **o** |
 
**Minuscule vs MAJUSCULE :** `s`/`t` = le bit `x` sous-jacent est **présent** ; `S`/`T` = le bit spécial est posé mais **`x` absent** (souvent une config bancale, à noter en audit).
 
**Poser les bits :**
```bash
chmod 4755 f     # SUID + rwxr-xr-x
chmod u+s f      # ajoute SUID (symbolique)
chmod 2755 dir   # SGID sur un dossier (héritage de groupe)
chmod +t /tmp    # sticky bit
```
 
### 2.1 RUID / EUID / SUID — la mécanique derrière SUID
Un processus porte plusieurs identités :
- **RUID** (Real UID) : qui a **lancé** le processus.
- **EUID** (Effective UID) : identité **utilisée pour les vérifications de permission**. C'est elle qui compte.
- **SUID** (Saved UID) : copie mémorisée pour pouvoir basculer.
Quand on lance un binaire **SUID root**, l'**EUID passe à 0 (root)** alors que le **RUID reste** celui de l'utilisateur. Le programme agit donc avec les droits de root. `id` montre `uid=1000(alice) euid=0(root)` dans ce cas.
 
**Exemples légitimes de SUID root :** `passwd` (doit écrire dans `/etc/shadow`, propriété de root), `sudo`, `su`, `mount`, `ping` (historiquement). Un SUID sur ces binaires est **normal**.
 
### 2.2 Nuances indispensables (souvent demandées)
- **Le SUID est ignoré sur les scripts** (`#!/bin/bash …`) : le noyau Linux refuse le set-user-ID sur les interpréteurs, pour raison de sécurité. Le SUID n'a d'effet que sur des **binaires compilés** (ELF).
- **Les bits SUID/SGID sont effacés à la modification** du fichier (écriture, `chown`) : le noyau les retire automatiquement pour éviter qu'un binaire trafiqué reste privilégié.
- **Option de montage `nosuid`** : sur un système de fichiers monté en `nosuid`, les bits SUID/SGID sont **ignorés**. `noexec` interdit l'exécution, `nodev` les fichiers de périphériques. Ce sont des durcissements courants pour `/tmp`, `/home`, supports amovibles.
---
 
## 3. Angle offensif — escalade de privilèges via les permissions
 
Principe général de la privesc locale : partir d'un utilisateur non privilégié et **obtenir un EUID 0** (root) en exploitant une permission trop large. Les permissions sont l'un des plus gros gisements. Voici **tous les vecteurs** liés aux permissions.
 
### 3.1 Binaires SUID détournables (le grand classique)
1. **Énumérer** les binaires SUID :
```bash
   find / -perm -4000 -type f 2>/dev/null
```
   (`-perm -4000` = « le bit SUID est posé, peu importe le reste ».)
2. **Croiser avec [GTFOBins](https://gtfobins.github.io)** (catalogue public des binaires détournables), section **SUID**.
3. **Exploiter.** Beaucoup de binaires courants (`find`, `vim`, `less`, `awk`, `nmap` ancien, `cp`, `bash`, `python`…) ont une méthode documentée. Exemple si `find` est SUID root :
```bash
   find . -exec /bin/sh -p \; -quit
```
   **Pourquoi `-p` ?** Sans lui, `bash`/`sh` **abandonnent le privilège** : au démarrage, s'ils détectent `EUID ≠ RUID`, ils remettent l'EUID au niveau du RUID. L'option `-p` (*privileged mode*) **conserve l'EUID root**. C'est le détail qui fait tout.
 
### 3.2 SGID détournable
Même logique que SUID mais on hérite d'un **groupe** privilégié. Utile pour **lire/écrire des fichiers réservés à un groupe** (ex. un groupe `shadow`, `adm` pour les logs). Énumération :
```bash
find / -perm -2000 -type f 2>/dev/null
```
 
### 3.3 Fichiers & dossiers modifiables par tous (world-writable)
Un attaquant cherche des cibles **inscriptibles** exécutées par un compte privilégié.
```bash
find / -perm -002 -type f 2>/dev/null   # fichiers world-writable
find / -perm -002 -type d 2>/dev/null   # dossiers world-writable
```
Cas les plus rentables :
- **Script world-writable exécuté par une tâche cron/systemd root** → on injecte notre code, il s'exécute en root (fait le lien avec les piliers 2 et 3).
- **`/etc/passwd` inscriptible** → on peut y insérer un utilisateur avec **UID 0**, ou remplacer le `x` du champ mot de passe par un hash qu'on génère (`openssl passwd`), donnant un second compte root.
- **`/etc/shadow` lisible** → on récupère les hashes et on les casse hors-ligne (John, hashcat).
- **Clés SSH / fichiers de config avec identifiants** aux permissions trop ouvertes → réutilisation directe.
### 3.4 Détournement de PATH sur un binaire SUID
Si un binaire SUID appelle une commande **sans chemin absolu** (ex. `system("service …")` qui invoque `service` via le PATH), on **préfixe le PATH** avec un dossier qu'on contrôle contenant un faux binaire du même nom :
```bash
export PATH=/tmp:$PATH   # /tmp/service = notre script → exécuté en root
```
Défense : les programmes privilégiés doivent **toujours utiliser des chemins absolus**.
 
### 3.5 Injection de bibliothèque : LD_PRELOAD / LD_LIBRARY_PATH
Variables d'environnement chargées **avant** l'exécution. Si `sudo` est configuré avec `env_keep += LD_PRELOAD` (mauvaise config, visible via `sudo -l`), on fait charger une bibliothèque `.so` malveillante par un binaire lancé en root. Vecteur lié à la fois aux permissions et à l'environnement.
 
### 3.6 Capabilities (l'alternative moderne au SUID… et sa faille)
Les **capabilities** découpent les pouvoirs de root en droits fins posés sur un binaire, sans SUID. Mais mal choisies, elles donnent root :
```bash
getcap -r / 2>/dev/null        # lister les capabilities du système
```
- `cap_setuid+ep` sur `python`/`perl` → le binaire peut appeler `setuid(0)` → shell root.
- `cap_dac_read_search` → contourne les vérifications de **lecture** (lire n'importe quel fichier).
- `cap_dac_override` → contourne lecture **et** écriture.
GTFOBins a aussi une section **Capabilities**.
### 3.7 ACLs — permissions étendues hors du triplet u/g/o
Les **ACL** (Access Control Lists) accordent des droits à des utilisateurs/groupes **supplémentaires**, invisibles dans le triplet classique. Un fichier « `640 root:root` » peut en réalité être lisible par `alice` via une ACL.
```bash
getfacl fichier          # voir les ACL
setfacl -m u:alice:rw f  # poser une ACL
```
Le **`+`** en fin de `ls -l` signale leur présence. À vérifier systématiquement, sinon on rate un accès.
 
### 3.8 Attribut immuable (l'angle inverse : ce qui bloque même root)
```bash
lsattr fichier           # voir les attributs
chattr +i fichier        # rend immuable : ni modif ni suppression, même pour root
chattr +a fichier        # append-only (utile pour protéger des logs)
```
Point d'examen : **root peut tout, sauf modifier un fichier `+i`** tant qu'il n'a pas d'abord retiré l'attribut (`chattr -i`). C'est un piège classique (« pourquoi root n'arrive pas à supprimer ce fichier ? »).
 
### 3.9 Outillage d'énumération
- **Manuel** : les `find` ci-dessus + `sudo -l` (droits sudo — vecteur adjacent, pas une permission de fichier mais à vérifier).
- **Automatisé** : **LinPEAS**, **linux-smart-enumeration (lse.sh)** — ils listent SUID/SGID, world-writable, capabilities, ACL, cron, etc. À connaître, mais savoir le faire **à la main** d'abord.
> À distinguer : **`sudo -l`** relève des droits `sudo` (fichier `/etc/sudoers`), pas des permissions de fichier. C'est un vecteur de privesc majeur mais d'une autre famille — je le traiterai à part.
 
---
 
## 4. Angle défensif — détection & remédiation
 
Chaque vecteur ci-dessus a sa contre-mesure. C'est la partie qui transforme le write-up en analyse de sécurité :
 
- **Auditer** régulièrement SUID/SGID, world-writable, capabilities et comparer à une **baseline** (tout ajout = alerte).
- **Retirer le superflu** : `chmod u-s /chemin` sur les SUID inutiles ; préférer les **capabilities** ciblées à un SUID root global.
- **Monter** `/tmp`, `/home`, les supports amovibles en **`nosuid,noexec,nodev`**.
- **Chemins absolus** dans tout programme privilégié ; nettoyer l'environnement (`env_reset` dans sudoers, pas de `env_keep` laxiste).
- **Durcir le umask** (027) et les permissions des fichiers sensibles (clés SSH en `600`, configs sans secrets lisibles).
- **Surveiller** avec **auditd** (règles sur les binaires sensibles) et un contrôle d'intégrité (**AIDE**) qui détecte tout changement de permission ou de bit spécial.
- **Protéger les logs** en append-only (`chattr +a`).
---
 
## 5. Aide-mémoire commandes
 
| Besoin | Commande |
|---|---|
| Voir les permissions | `ls -l` · dossier : `ls -ld dir` |
| Changer les permissions | `chmod 750 f` · `chmod u+s f` |
| Changer propriétaire/groupe | `chown user:group f` · `chgrp group f` |
| Permissions par défaut | `umask` · `umask 027` |
| Lister les SUID | `find / -perm -4000 -type f 2>/dev/null` |
| Lister les SGID | `find / -perm -2000 -type f 2>/dev/null` |
| Lister world-writable | `find / -perm -002 -type f 2>/dev/null` |
| Lister les capabilities | `getcap -r / 2>/dev/null` |
| Voir/poser une ACL | `getfacl f` · `setfacl -m u:bob:rw f` |
| Voir/poser un attribut | `lsattr f` · `chattr +i f` |
| Voir ses droits sudo | `sudo -l` |
 
---
 
## 6. Questions qu'on peut te poser (le filet de sécurité)
 
**Q. Différence RUID / EUID ?**
RUID = qui a lancé le processus ; EUID = identité utilisée pour les vérifications de droits. Un binaire SUID met l'EUID à celui du propriétaire.
 
**Q. Pourquoi un shell obtenu via SUID a besoin de `-p` ?**
Sans `-p`, bash/sh remettent l'EUID au niveau du RUID au démarrage (abandon de privilège). `-p` conserve l'EUID root.
 
**Q. Un SUID sur un script bash, ça marche ?**
Non : le noyau ignore le SUID sur les scripts interprétés. Uniquement efficace sur les binaires compilés.
 
**Q. Peut-on supprimer un fichier sur lequel on n'a aucun droit d'écriture ?**
Oui, si on a le droit `w` (et `x`) sur le **dossier** qui le contient. La suppression est une opération sur le dossier, pas sur le fichier.
 
**Q. Que fait `x` sur un dossier, sans `r` ?**
On peut le traverser (`cd`) et accéder à un fichier **dont on connaît le nom**, mais pas lister son contenu.
 
**Q. Différence SGID sur fichier vs sur dossier ?**
Sur un fichier exécutable : s'exécute avec le groupe du fichier. Sur un dossier : les nouveaux fichiers héritent du **groupe du dossier** (utile pour le travail collaboratif).
 
**Q. À quoi sert le sticky bit sur `/tmp` ?**
Tout le monde peut écrire dans `/tmp`, mais chacun ne peut supprimer **que ses propres** fichiers. Empêche la suppression des fichiers des autres.
 
**Q. `umask 027` donne quoi sur un nouveau fichier ? un nouveau dossier ?**
Fichier 640, dossier 750.
 
**Q. Root est-il soumis aux permissions ?**
Non, root (UID 0) contourne les vérifications de permissions — **sauf** l'attribut immuable (`chattr +i`) et certaines protections LSM (SELinux/AppArmor).
 
**Q. C'est quoi le `+` à la fin d'un `ls -l` ?**
Une ACL est présente sur le fichier (droits étendus au-delà de u/g/o).
 
**Q. Différence entre `chmod 4755` et `chmod 755` ?**
Le `4` en tête pose le bit **SUID** ; `755` seul ne l'a pas. `4755` = `rwsr-xr-x`.
 
**Q. Comment retirer un SUID ?**
`chmod u-s fichier` (ou `chmod 0755`).
 
**Q. Comment un `/etc/passwd` inscriptible mène-t-il à root ?**
On y ajoute une entrée avec UID 0, ou on place un hash (généré via `openssl passwd`) dans le champ mot de passe → nouveau compte root.
 
---
 
## Ce que je retiens
1. Les droits sur un **dossier** commandent la création/suppression ; sur un **fichier**, le contenu. Ne pas confondre.
2. Le **SUID** fait tourner un binaire avec l'EUID de son propriétaire → si root, c'est le vecteur de privesc n°1 (méthode : `find -perm -4000` → GTFOBins → shell `-p`).
3. Les permissions ne s'arrêtent pas au triplet : **capabilities, ACL, attributs, world-writable, PATH, LD_PRELOAD** sont autant d'angles à vérifier — chacun avec sa remédiation.
 
