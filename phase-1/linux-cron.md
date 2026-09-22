# Linux — Tâches planifiées (cron, at, timers) & escalade de privilèges
 
> Write-up Semaine 2, pilier 2. Objectif : maîtriser **tous les mécanismes de planification** Linux et **tous les vecteurs de privesc** qui en découlent. Manipulations offensives **uniquement sur ma VM de lab / cibles autorisées**.
 
---
 
## 1. Vue d'ensemble : 4 mécanismes à distinguer
 
| Mécanisme | Démon | Pour quoi | Fichiers clés |
|---|---|---|---|
| **cron** | `crond`/`cron` | Tâches récurrentes à heure fixe | crontabs utilisateur + système |
| **at** | `atd` | Tâche **unique**, différée | file `atq`, `/var/spool/at` |
| **anacron** | `anacron` | Rattrape les tâches ratées (machines éteintes par moments) | `/etc/anacrontab` |
| **systemd timers** | `systemd` | Alternative moderne à cron | unités `.timer` + `.service` |
 
Les connaître tous, c'est ne rien rater en énumération : une tâche root peut se cacher dans n'importe lequel.
 
---
 
## 2. cron en détail
 
### 2.1 Les emplacements des tâches cron (tous à vérifier)
 
| Emplacement | Portée | Champ « utilisateur » ? |
|---|---|---|
| `crontab -e` (par utilisateur) | Stocké dans `/var/spool/cron/crontabs/<user>` (Debian) ou `/var/spool/cron/<user>` (RHEL) | **Non** (s'exécute en tant que cet utilisateur) |
| `/etc/crontab` | Système | **Oui** (une colonne indique qui exécute) |
| `/etc/cron.d/*` | Système (drop-in) | **Oui** |
| `/etc/cron.hourly/`, `cron.daily/`, `cron.weekly/`, `cron.monthly/` | Dossiers de **scripts** lancés par `run-parts` | (exécutés par root) |
 
> Différence à retenir : une ligne de **crontab utilisateur** n'a **pas** de champ utilisateur ; une ligne de **`/etc/crontab` ou `/etc/cron.d`** en a un (juste avant la commande).
 
### 2.2 Syntaxe d'une ligne
```
┌───── minute (0-59)
│ ┌─── heure (0-23)
│ │ ┌─ jour du mois (1-31)
│ │ │ ┌ mois (1-12)
│ │ │ │ ┌ jour de semaine (0-7 ; 0 ET 7 = dimanche)
│ │ │ │ │
* * * * *  commande
```
- **Opérateurs** : `*` (tout), `,` (liste : `1,15`), `-` (plage : `1-5`), `/` (pas : `*/10` = toutes les 10).
- **Ligne système** (`/etc/crontab`, `/etc/cron.d`) : on insère l'utilisateur avant la commande :
```
  */5 * * * * root /opt/scripts/backup.sh
```
- **Raccourcis** : `@reboot` (au démarrage), `@hourly`, `@daily` (= `@midnight`), `@weekly`, `@monthly`, `@yearly`/`@annually`.
### 2.3 L'environnement de cron (crucial pour la privesc)
cron s'exécute avec un **environnement minimal** : pas le PATH complet d'un shell interactif. Le PATH par défaut est souvent court (ex. `/usr/bin:/bin`). On peut le fixer en tête de crontab :
```
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=admin@exemple.com     # où sont envoyées les sorties/erreurs
SHELL=/bin/bash
```
Ce PATH restreint et modifiable est **une porte d'entrée** (voir §4.3).
 
### 2.4 Contrôle d'accès & logs
- **Qui peut créer des tâches** : `/etc/cron.allow` et `/etc/cron.deny`.
  - Si `cron.allow` existe → **seuls** les utilisateurs listés peuvent utiliser cron (`cron.deny` ignoré).
  - Sinon, si `cron.deny` existe → tous **sauf** ceux listés.
  - Si aucun des deux → selon la distrib (souvent root seul, ou tous).
- **Logs** : `/var/log/syslog` (Debian) ou `/var/log/cron` (RHEL), ou `journalctl -u cron`.
---
 
## 3. at, anacron, systemd timers
 
### 3.1 `at` — tâche unique différée
```bash
echo "/opt/x.sh" | at now + 5 minutes   # planifier
atq                                       # lister
atrm <id>                                 # supprimer
```
Contrôle d'accès : `/etc/at.allow`, `/etc/at.deny` (même logique que cron). Les jobs vivent dans `/var/spool/at`.
 
### 3.2 `anacron` — rattrapage
Pour les machines pas toujours allumées : exécute les tâches `daily/weekly/monthly` **manquées** au prochain démarrage. Config dans `/etc/anacrontab` (champs : période en jours, délai, identifiant, commande).
 
### 3.3 systemd timers (le remplaçant moderne de cron)
Un **`.timer`** déclenche un **`.service`** du même nom.
```bash
systemctl list-timers --all      # lister tous les timers (colonne NEXT/LAST)
```
Directives typiques d'un `.timer` : `OnCalendar=*-*-* 02:00:00` (planning type cron), `OnBootSec=`, `OnUnitActiveSec=`, `Persistent=true` (rattrape au boot). Le **détail des unités systemd** est traité au pilier 3 — mais côté énumération, **ne jamais oublier `list-timers`**.
 
---
 
## 4. Angle offensif — escalade de privilèges via les tâches planifiées
 
Principe : une tâche exécutée **en root** dont je peux **influencer ce qui est exécuté** = exécution de code en root. Voici **tous les vecteurs**.
 
### 4.1 Script inscriptible exécuté par une tâche root (le grand classique)
1. Identifier les tâches et le **chemin du script** exécuté (`/etc/crontab`, `/etc/cron.d/*`, `cron.*`).
2. Vérifier si **le script — ou un dossier de son chemin — est modifiable** par moi :
```bash
   ls -la /opt/scripts/backup.sh
   find / -perm -002 -type f 2>/dev/null   # scripts world-writable
```
3. Si oui, y injecter une charge (reverse shell, ajout d'un compte, ou pose d'un binaire SUID) — elle s'exécutera en root à la prochaine occurrence.
> Corollaire : même si le **script** n'est pas inscriptible, avoir `w` sur **son dossier** peut suffire à le remplacer (cf. pilier 1 : supprimer/recréer dépend du dossier).
 
### 4.2 Fichier cron lui-même inscriptible
Si `/etc/crontab`, un fichier de `/etc/cron.d/`, ou le spool d'un crontab est modifiable, j'ajoute **directement** une ligne root :
```
* * * * * root /tmp/payload.sh
```
Toujours vérifier les permissions de ces fichiers, pas seulement des scripts qu'ils appellent.
 
### 4.3 Détournement de PATH dans cron
Si une tâche root appelle une commande **sans chemin absolu** (`backup` au lieu de `/usr/local/bin/backup`) **et** qu'une entrée du PATH de cron pointe vers un dossier que je contrôle, je dépose un binaire malveillant du même nom. Cas fréquent : une crontab qui définit `PATH=/home/user:/usr/bin` puis lance une commande courte → je place mon faux binaire dans `/home/user`.
 
### 4.4 Injection par wildcard (technique tar/rsync/chown)
Une tâche root du type `tar czf /backup/archive.tar.gz *` exécutée **dans un dossier où je peux écrire** est exploitable : `*` est développé par le shell en **noms de fichiers**, et tar interprète les noms commençant par `-` comme des **options**. Je crée donc des fichiers-pièges :
```
# dans le dossier concerné :
echo 'cp /bin/bash /tmp/rootbash; chmod +s /tmp/rootbash' > payload.sh
touch -- '--checkpoint=1'
touch -- '--checkpoint-action=exec=sh payload.sh'
```
Au passage de la tâche root, tar exécute `payload.sh` **en root**. Le même principe s'applique à d'autres commandes via des options comme `--reference` (`chown`/`chmod`) ou `-e` (`rsync`). GTFOBins documente ces détournements.
> Défense : dans un script privilégié, préfixer les motifs par `./` (`tar … ./*`), utiliser `--` pour clore les options, ou lister explicitement les fichiers.
 
### 4.5 Découvrir une tâche root qu'on ne peut pas lire (indispensable)
Le crontab de root (`/var/spool/cron/crontabs/root`) n'est **pas lisible** par un utilisateur normal. Or c'est souvent là que se cache la tâche exploitable. Solution : **observer les processus en temps réel** avec **`pspy`** (pas besoin de root) — il révèle les commandes lancées périodiquement (chemin du script, arguments, utilisateur). Une grande partie du travail de privesc-cron, c'est **découvrir** la tâche, pas seulement l'exploiter.
 
### 4.6 `at` et autres
Lire les jobs `at` en file, ou en soumettre si un mécanisme privilégié les traite. Moins fréquent, mais à cocher dans l'énumération.
 
---
 
## 5. Énumération — la checklist complète
```bash
crontab -l                              # mes propres tâches
cat /etc/crontab                        # crontab système
ls -la /etc/cron.d/ /etc/cron.*/        # drop-ins + dossiers hourly/daily/…
cat /etc/cron.d/*                       # contenu des drop-ins
ls -la /var/spool/cron/crontabs/ 2>/dev/null   # spools (souvent root-only)
systemctl list-timers --all             # timers systemd
atq                                     # jobs at
cat /etc/anacrontab                     # anacron
# puis, sur chaque script référencé : vérifier propriétaire + droits d'écriture
# et, pour le caché :
./pspy64                                # observer les tâches root en direct
```
Automatisation : **LinPEAS** / **lse.sh** couvrent tout ça, mais savoir le faire à la main d'abord.
 
---
 
## 6. Angle défensif — détection & remédiation
- **Scripts de tâches** appartenant à root, **non world-writable**, dans des dossiers non inscriptibles ; vérifier tout le chemin.
- **Chemins absolus** dans les commandes cron ; définir un **PATH sûr et fixe** en tête de crontab.
- **Pas de wildcards** dans les scripts privilégiés (ou `./*`, `--`, listes explicites).
- **Restreindre** la création de tâches via `cron.allow` / `at.allow`.
- **Journaliser et surveiller** l'exécution des tâches ; **auditd** + **AIDE** sur `/etc/crontab`, `/etc/cron.d/`, les spools et les scripts (toute modification = alerte).
- Privilégier des **systemd timers** avec des unités `.service` durcies (voir pilier 3 : `ProtectSystem`, `NoNewPrivileges`, etc.).
---
 
## 7. Aide-mémoire
 
| Besoin | Commande |
|---|---|
| Éditer / lister / supprimer ma crontab | `crontab -e` · `crontab -l` · `crontab -r` |
| Crontab d'un autre utilisateur (root) | `crontab -u user -l` |
| Voir la crontab système | `cat /etc/crontab` |
| Lister timers systemd | `systemctl list-timers --all` |
| Planifier une tâche unique | `echo cmd \| at now + 1 hour` · `atq` · `atrm` |
| Trouver les scripts world-writable | `find / -perm -002 -type f 2>/dev/null` |
| Observer les tâches root en direct | `./pspy64` |
| Logs cron | `journalctl -u cron` · `/var/log/syslog` |
 
---
 
## 8. Questions qu'on peut te poser (le filet de sécurité)
 
**Q. Ordre des 5 champs d'une ligne cron ?**
minute, heure, jour du mois, mois, jour de semaine.
 
**Q. `0` et `7` en jour de semaine ?**
Les deux désignent **dimanche**.
 
**Q. Différence entre une crontab utilisateur et `/etc/crontab` ?**
`/etc/crontab` (et `/etc/cron.d`) contient un **champ utilisateur** avant la commande ; la crontab d'un utilisateur n'en a pas (elle s'exécute en tant que cet utilisateur).
 
**Q. Où sont stockées les crontabs utilisateur ?**
`/var/spool/cron/crontabs/<user>` (Debian) ou `/var/spool/cron/<user>` (RHEL) — non lisibles par les autres.
 
**Q. Que fait `@reboot` ?**
Exécute la tâche au démarrage du système.
 
**Q. Pourquoi le PATH de cron compte-t-il en privesc ?**
cron a un PATH minimal et modifiable ; si une tâche root appelle une commande sans chemin absolu, on peut détourner le PATH pour exécuter notre binaire en root.
 
**Q. Explique l'injection par wildcard.**
Un `*` développé par le shell devient une liste de noms de fichiers ; en créant des fichiers nommés comme des options (`--checkpoint-action=exec=…` pour tar), on force la commande privilégiée à exécuter du code arbitraire.
 
**Q. Comment trouver une tâche root que je ne peux pas lire ?**
Avec **pspy** : il observe les processus/commandes lancés périodiquement sans nécessiter root.
 
**Q. Règle de priorité `cron.allow` / `cron.deny` ?**
Si `cron.allow` existe, seuls ses utilisateurs sont autorisés (deny ignoré) ; sinon `cron.deny` liste les interdits ; si aucun, comportement selon la distrib.
 
**Q. Différence cron / anacron / at / systemd timer ?**
cron = récurrent à heure fixe ; anacron = rattrape les tâches ratées sur machine intermittente ; at = exécution unique différée ; systemd timer = équivalent moderne de cron, couplé à un service.
 
**Q. Comment lister les timers systemd ?**
`systemctl list-timers --all`.
 
**Q. Un script cron non inscriptible mais dans un dossier où j'ai le droit d'écrire — exploitable ?**
Oui : `w` sur le dossier permet de remplacer/supprimer-recréer le script (la suppression dépend du dossier, pas du fichier).
 
---
 
## Ce que je retiens
1. Il y a **quatre** mécanismes de planification — cron, at, anacron, systemd timers — et une tâche root peut se cacher dans **n'importe lequel** : je les énumère tous.
2. Le vecteur roi = **un script inscriptible (ou son dossier) exécuté en root** ; viennent ensuite **PATH**, **wildcard injection** et **fichiers cron inscriptibles**.
3. Souvent, la difficulté n'est pas d'exploiter mais de **découvrir** la tâche → **pspy** est l'outil réflexe.
