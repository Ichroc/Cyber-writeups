# Linux — systemd & services & escalade de privilèges

> Write-up Semaine 2, pilier 3 (dernier de la triade privesc). Objectif : maîtriser systemd **sous tous les angles** — modèle, anatomie d'une unité, priorité des emplacements, vecteurs offensifs, et surtout le **durcissement** qui neutralise les piliers 1 et 2. Offensif = **lab / cibles autorisées uniquement**.

---

## 1. Ce qu'est systemd (le cadre)

systemd est l'**init system** (PID 1) : il démarre et supervise tout le système via des objets appelés **unités**. Types d'unités à connaître :

| Type | Rôle |
|---|---|
| **.service** | Un programme/démon (le cœur du sujet) |
| **.socket** | Active un service à la 1ʳᵉ connexion réseau/IPC (socket activation) |
| **.timer** | Déclenche un service à heure/intervalle (vu pilier 2) |
| **.path** | Déclenche un service quand un fichier/dossier change |
| **.target** | Groupe d'unités (équivalent des « runlevels », ex. `multi-user.target`) |
| **.mount / .device / .slice / .scope** | Montages, périphériques, gestion de ressources |

Point capital : **un service tourne en root par défaut**, sauf si l'unité précise `User=`.

---

## 2. Où vivent les unités — et qui gagne (priorité = vecteur de privesc)

Les fichiers d'unités sont cherchés dans plusieurs dossiers, avec un **ordre de priorité** :

| Emplacement | Pour | Priorité |
|---|---|---|
| `/etc/systemd/system/` | Unités **de l'admin** (et overrides) | **La plus haute** |
| `/run/systemd/system/` | Unités générées à l'exécution | Moyenne |
| `/usr/lib/systemd/system/` (= `/lib/…`) | Unités **des paquets** | La plus basse |

> **Règle d'or :** en cas de même nom, `/etc` **écrase** `/run` qui **écrase** `/lib`. Donc si `/etc/systemd/system/` (ou un fichier dedans) est **inscriptible**, je peux **remplacer ou masquer** n'importe quel service — y compris un service légitime — par ma version.

**Drop-ins** (overrides partiels) : un dossier `/etc/systemd/system/<unité>.service.d/*.conf` surcharge **certaines directives** sans réécrire toute l'unité. À auditer aussi.

**Unités utilisateur** : `~/.config/systemd/user/`, gérées par `systemctl --user` (tournent avec **mes** droits, sans intérêt pour la privesc — mais à ne pas confondre avec les unités système).

---

## 3. Anatomie d'une unité `.service`

```ini
[Unit]
Description=Service de sauvegarde
After=network.target            # ordre de démarrage
Requires=…                      # dépendances

[Service]
Type=simple                     # simple(défaut) | forking | oneshot | notify | dbus | idle
User=backup                     # SANS cette ligne → tourne en ROOT
ExecStartPre=/opt/pre.sh        # commande(s) avant
ExecStart=/opt/scripts/backup.sh   # LA commande principale (toujours en absolu)
ExecStop=…
Environment=FOO=bar             # variables
EnvironmentFile=/etc/backup.env # variables depuis un fichier
WorkingDirectory=/opt
Restart=on-failure

[Install]
WantedBy=multi-user.target      # cible à laquelle s'attacher lors d'un `enable`
```

**Directives sensibles pour l'attaque comme pour l'audit :** `ExecStart` / `ExecStartPre` / `ExecStartPost` (ce qui est lancé), `User`, `Environment` / `EnvironmentFile`, `WorkingDirectory`.

**Type= en un coup d'œil :** `simple` = ExecStart est le processus principal ; `forking` = le programme se démonise ; `oneshot` = s'exécute puis se termine (typique des scripts) ; `notify`/`dbus` = signalent leur disponibilité.

---

## 4. Les commandes essentielles

| Besoin | Commande |
|---|---|
| État / démarrer / arrêter / redémarrer | `systemctl status/start/stop/restart <unit>` |
| Activer/désactiver au boot | `systemctl enable/disable <unit>` |
| **Voir l'unité effective** (fichier + drop-ins) | `systemctl cat <unit>` |
| Voir **toutes** les propriétés résolues | `systemctl show <unit>` |
| Éditer via un drop-in propre | `systemctl edit <unit>` (ou `--full`) |
| **Recharger après édition d'un fichier d'unité** | `systemctl daemon-reload` |
| Lister services / unités / échecs | `systemctl list-units --type=service` · `list-unit-files` · `--failed` |
| Logs d'un service | `journalctl -u <unit>` · `-f` (suivi) · `-xe` |

> **`enable` ≠ `start`.** `enable` crée les liens pour un **démarrage au boot** (via `WantedBy`) ; `start` lance **maintenant**. Après avoir modifié un **fichier** d'unité, il faut `daemon-reload` pour que systemd relise la définition.

---

## 5. Angle offensif — privesc via systemd

Même idée-mère que le pilier 2 : **root exécute quelque chose ; si je maîtrise _ce qui est exécuté_, j'ai root.** Ici la « chaîne » va de la **définition de l'unité** → au **binaire/scripts d'ExecStart**. Vecteurs :

### 5.1 Fichier d'unité inscriptible (root)
Si un `.service` lancé en root est **modifiable**, je change `ExecStart` :
```ini
ExecStart=/tmp/payload.sh
```
puis `systemctl daemon-reload && systemctl restart <unit>` (ou j'attends un restart/reboot). Payload exécuté en root.

### 5.2 Dossier de recherche inscriptible → masquage / création d'unité
Si `/etc/systemd/system/` est inscriptible, je peux :
- **Masquer** un service légitime de `/lib` par une unité de même nom (priorité `/etc`), ou
- **Créer** une nouvelle unité et — si j'ai le droit (`sudo -l`) — la `enable`/`start`.

### 5.3 ExecStart pointe vers un script/binaire modifiable
`ExecStart=/opt/scripts/backup.sh` : si **ce script**, ou **son dossier**, est modifiable, j'injecte dedans (identique au maillon 3 du pilier 2 : écrire le fichier **ou** son dossier).

### 5.4 Drop-in inscriptible
Si le dossier `<unit>.service.d/` est modifiable, j'ajoute un `.conf` qui surcharge `ExecStart`. Subtilité : pour **remplacer** `ExecStart`, il faut d'abord le **réinitialiser** à vide :
```ini
[Service]
ExecStart=
ExecStart=/tmp/payload.sh
```

### 5.5 EnvironmentFile inscriptible
Si l'unité lit `EnvironmentFile=/chemin` que je peux écrire, je peux y injecter des variables dangereuses (ex. utilisées ensuite dans une commande, ou une bibliothèque préchargée). Plus niche, mais à cocher.

### 5.6 Activation par `.socket` / `.path` / `.timer`
Une unité `.socket`, `.path` ou `.timer` inscriptible (ou dont le service activé l'est) permet de **déclencher** l'exécution. Les timers relèvent du pilier 2 ; le réflexe reste : suivre ce qui **lance** quoi.

### 5.7 `systemctl` via sudo/SUID — l'échappement par le pager
Si `sudo -l` montre que je peux lancer `systemctl` en root (ou s'il est SUID) : `systemctl status <unit>` envoie sa sortie longue dans un **pager** (`less`). Depuis `less`, la commande `!sh` ouvre **un shell root**. (Contre-mesure côté script : `--no-pager`.) C'est un détournement documenté sur GTFOBins.

### 5.8 Énumération — checklist
```bash
systemctl list-units --type=service           # services actifs
systemctl list-unit-files --state=enabled      # activés au boot
systemctl --failed                             # services en échec
# unités/dossiers inscriptibles :
find /etc/systemd/system /run/systemd/system /usr/lib/systemd/system -writable 2>/dev/null
# pour chaque service intéressant :
systemctl cat <unit>        # voir ExecStart + User + drop-ins
# → vérifier les droits du fichier d'unité, du script ExecStart, et de leurs dossiers
sudo -l                     # droits systemctl ?
./pspy64                    # voir les (re)démarrages de services en direct
```
LinPEAS/lse.sh automatisent, mais faire à la main d'abord.

---

## 6. Angle défensif — durcissement (là où systemd brille)

systemd n'est pas qu'une surface d'attaque : c'est **l'outil de confinement** qui referme les piliers 1 et 2. Bonnes pratiques :

- **Ne pas tourner en root** : `User=…`, ou `DynamicUser=yes` (utilisateur éphémère).
- **Unités root:root en 644**, hors des dossiers inscriptibles ; **chemins absolus** dans `ExecStart`.
- **Directives de confinement** (dans `[Service]`) :

| Directive | Effet | Ferme quel trou |
|---|---|---|
| `NoNewPrivileges=yes` | Le service et ses enfants **ne peuvent plus gagner de privilège** (setuid/file caps ignorés) | **Neutralise les SUID (pilier 1)** dans ce service |
| `PrivateTmp=yes` | `/tmp` **privé** et isolé | Tue l'abus de `/tmp` partagé |
| `ProtectSystem=strict` | `/usr`, `/etc`… en **lecture seule** | Empêche l'altération de binaires/config |
| `ProtectHome=yes` | `/home`, `/root` inaccessibles | Limite le vol de secrets |
| `ReadOnlyPaths=` / `ReadWritePaths=` | Contrôle fin des écritures | Réduit la surface |
| `CapabilityBoundingSet=` | **Retire** des capabilities | Limite les pouvoirs root résiduels |
| `RestrictSUIDSGID=yes` | Interdit la création de fichiers SUID/SGID | Coupe la pose de backdoors SUID |
| `SystemCallFilter=` | Restreint les appels système | Durcit fortement |

- **Mesurer** l'exposition : `systemd-analyze security <unit>` (donne un score et pointe ce qui manque).
- **Surveiller** les changements d'unités avec **auditd** / **AIDE** ; journaliser via `journald`.

---

## 7. Questions qu'on peut te poser (le filet de sécurité)

**Q. Où sont stockées les unités, et laquelle gagne en cas de doublon ?**
`/etc/systemd/system/` > `/run/systemd/system/` > `/usr/lib/systemd/system/`. `/etc` l'emporte.

**Q. Un service tourne sous quel utilisateur par défaut ?**
root, sauf si `User=` est défini.

**Q. Différence `enable` / `start` ?**
`enable` = démarrage automatique au boot (via `WantedBy`) ; `start` = lancer maintenant. Indépendants.

**Q. À quoi sert `daemon-reload` ?**
À faire relire par systemd les **fichiers d'unités** après une modification, pour prendre en compte les changements.

**Q. Comment voir la définition réellement appliquée (avec les drop-ins) ?**
`systemctl cat <unit>` (fichier + overrides) ; `systemctl show <unit>` pour toutes les propriétés résolues.

**Q. Comment un fichier d'unité inscriptible mène-t-il à root ?**
On réécrit `ExecStart` vers notre charge, `daemon-reload` + `restart` → exécution en root.

**Q. Pour surcharger `ExecStart` via un drop-in, pourquoi le réinitialiser ?**
Parce que `ExecStart` est cumulatif : il faut une ligne `ExecStart=` vide avant de redéfinir, sinon les deux s'ajoutent.

**Q. Que fait `NoNewPrivileges=yes` ?**
Empêche le processus et ses enfants d'acquérir de nouveaux privilèges → les binaires SUID **n'élèvent plus** dans ce contexte.

**Q. En quoi `PrivateTmp` aide-t-il ?**
Le service reçoit un `/tmp` isolé → plus d'abus via des fichiers partagés dans `/tmp`.

**Q. Escalade avec `systemctl` en sudo ?**
`systemctl status` ouvre un pager (`less`) ; `!sh` y lance un shell root. Parade : `--no-pager`.

**Q. Les Type= d'un service ?**
`simple` (défaut), `forking`, `oneshot`, `notify`, `dbus`, `idle`.

**Q. Comment trouver les unités exploitables ?**
`find … -writable` sur les 3 dossiers d'unités + `systemctl cat` pour vérifier `ExecStart`, son script et leurs dossiers ; `sudo -l` ; `pspy` pour les redémarrages.

---

## 8. Synthèse de la triade (permissions + cron + systemd)

Les trois piliers ne sont qu'**une seule idée** déclinée :

> **Quelque chose s'exécute avec des droits élevés. Si je contrôle _ce qui est exécuté_ — le fichier, son dossier, son PATH, ses arguments — j'hérite de ces droits.**

- **Pilier 1 (permissions)** = le socle : qui peut lire/écrire/exécuter quoi ; SUID = un binaire qui *porte* déjà les droits.
- **Pilier 2 (cron)** = un déclencheur **temporel** de root.
- **Pilier 3 (systemd)** = un déclencheur **de service** de root — et l'outil qui **referme** les deux autres via le confinement.

Le réflexe unique en privesc locale : **énumérer tout ce qui s'exécute en root (SUID, cron, services), puis remonter à _ce que je peux modifier_ dans ce qui est exécuté.** `pspy` pour voir, GTFOBins pour exploiter, la section « défense » pour corriger.

---

## Ce que je retiens
1. **Priorité des emplacements** (`/etc` > `/run` > `/lib`) : un dossier d'unités inscriptible = je masque/remplace n'importe quel service root.
2. Les points chauds d'une unité = **ExecStart + User + drop-ins + EnvironmentFile** ; toujours vérifier le fichier **et** le script pointé **et** leurs dossiers.
3. systemd est aussi la **meilleure défense** : `User=`, `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`… ferment les trous des piliers 1 et 2. `systemd-analyze security` pour mesurer.
