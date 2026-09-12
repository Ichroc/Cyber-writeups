# Semaine 1 — Subnetting & DNS
 
> Write-up de démarrage (Phase 0). Objectif : ancrer deux réflexes de subnetting qui reviennent partout, et poser une fiche mémo DNS avec l'angle sécurité. Notes personnelles, à relire avant tout exercice de réseau ou de recon.
 
---
 
## Partie 1 — Subnetting
 
### La table de référence (à connaître par cœur)
 
| CIDR | Masque décimal | Block size (incrément) | Hôtes utilisables |
|---|---|---|---|
| /24 | 255.255.255.0   | 256 | 254 |
| /25 | 255.255.255.128 | 128 | 126 |
| /26 | 255.255.255.192 | 64  | 62 |
| /27 | 255.255.255.224 | 32  | 30 |
| /28 | 255.255.255.240 | 16  | 14 |
| /29 | 255.255.255.248 | 8   | 6 |
| /30 | 255.255.255.252 | 4   | 2 |
 
**Le masque bit par bit :** chaque bit emprunté ajoute le poids suivant dans l'octet — 128, puis +64, +32, +16… Donc /26 = 2 bits = 128 + 64 = **192**. (`.128` seul = /25, pas /26 : c'est l'erreur que je faisais.)
 
**Sur quel octet le masque « bouge » :** /9–/16 → 2ᵉ octet · /17–/24 → 3ᵉ octet · /25–/30 → 4ᵉ octet. Le block size se calcule toujours sur cet octet-là.
 
---
 
### Réflexe n°1 — Placer une IP dans son sous-réseau (block size)
 
Trois étapes, toujours les mêmes :
 
1. **Block size** = 256 − l'octet du masque qui bouge.
2. **Adresse réseau** = le plus grand **multiple du block size** ≤ à l'octet de l'IP.
3. **Broadcast** = (réseau + block size) − 1.
> Règle d'or : une IP d'hôte n'est **jamais** l'adresse réseau. Le réseau, c'est le multiple juste en dessous.
 
**Exemple travaillé — `10.0.0.130 /25`**
- /25 → masque `.128` → block size = 256 − 128 = **128**.
- Multiples de 128 dans l'octet : 0, **128**, 256. Le plus grand ≤ 130 → réseau = **10.0.0.128** (surtout pas .0).
- Broadcast = 128 + 128 − 1 = **10.0.0.255**.
- Plage utilisable = **.129 → .254**, soit **126 hôtes**.
**Le piège des frontières — `.62/26` et `.65/26`**
Block size 64 → frontière à **63 | 64**. `.62` est encore dans `.0–.63` ; `.65` est déjà dans `.64–.127`. Donc **pas le même sous-réseau**. Dès qu'on franchit un multiple du block size, on change de réseau.
 
---
 
### Réflexe n°2 — Réseau / broadcast / utilisables (le fameux −2)
 
Schéma mental d'un block (ici un /26, block size 64) :
 
```
.0          .1 ───────────── .62          .63        | .64 = réseau suivant
réseau      <── hôtes utilisables ──>      broadcast
```
 
- **Première** adresse du block = adresse réseau → interdite aux hôtes.
- **Dernière** adresse du block = broadcast → interdite aux hôtes.
- **Hôtes utilisables** = 2^(bits d'hôte) − 2.
**Exemple — `192.168.10.37 /26`** → réseau **.0**, broadcast **.63** (et pas .64 : .64 est déjà le réseau suivant), plage **.1 → .62**, **62 hôtes**.
 
**Cas limites à ne pas rater :**
- `/30` (block 4) : .0 réseau, .3 broadcast → **2** hôtes (.1 et .2), jamais 4.
- `192.168.1.63/26` : c'est un **broadcast**, donc **pas** une adresse d'hôte valide.
- `/31` : exception (RFC 3021) → 2 adresses utilisables sur les liaisons point-à-point, sans réseau ni broadcast.
---
 
### Concevoir un plan d'adressage
 
- **Nombre de sous-réseaux** obtenus en partant d'un /24 = 2^(nouveau préfixe − 24). Ex. /26 → 2² = **4** ; /28 → 2⁴ = **16**. Besoin de 8 sous-réseaux → 8 = 2³ → +3 bits → **/27**.
- **Choisir le masque pour N hôtes** : plus petite puissance de 2 telle que 2ⁿ − 2 ≥ N. Ex. 50 hôtes → 2⁶ − 2 = 62 → **/26** ; 500 hôtes → 2⁹ − 2 = 510 → **/23**.
**VLSM — exemple `192.168.1.0/24`** (on alloue du plus grand au plus petit) :
 
| Segment | Besoin | Masque | Réseau | Plage utilisable | Broadcast |
|---|---|---|---|---|---|
| LAN A | 100 h | /25 | 192.168.1.0   | .1 → .126   | .127 |
| LAN B | 50 h  | /26 | 192.168.1.128 | .129 → .190 | .191 |
| LAN C | 25 h  | /27 | 192.168.1.192 | .193 → .222 | .223 |
| WAN   | 2 h   | /30 | 192.168.1.224 | .225 → .226 | .227 |
 
Tout tient dans le /24, et il reste `.228 → .255` de libre. La clé du VLSM : **trier les besoins par taille décroissante** avant d'allouer, sinon on gaspille.
 
---
 
## Partie 2 — Fiche mémo DNS (avec angle sécu)
 
Le DNS traduit des noms en adresses (et l'inverse). Chaque **type d'enregistrement** a un rôle précis. Pour chacun : à quoi il sert + pourquoi il compte côté sécurité.
 
| Type | Rôle | Exemple | Angle sécurité |
|---|---|---|---|
| **A** | Nom → adresse **IPv4** | `exemple.com → 93.184.216.34` | Point de départ de toute recon : résoudre les A/sous-domaines révèle la surface exposée. |
| **AAAA** | Nom → adresse **IPv6** | `exemple.com → 2606:2800:220:1:...` | Souvent oublié en défense : un service peut être joignable en IPv6 alors qu'on ne filtre qu'en IPv4. |
| **CNAME** | **Alias** vers un autre nom | `www.exemple.com → exemple.com` | **Dangling CNAME** : un alias qui pointe vers une ressource cloud supprimée → risque de **subdomain takeover**. |
| **MX** | Serveur de **mail** (avec priorité) | `exemple.com → 10 mail.exemple.com` | Révèle l'infra mail. Priorité basse = préféré. Cible d'énumération pour le phishing. |
| **PTR** | **Reverse** : IP → nom (`in-addr.arpa`) | `34.216.184.93.in-addr.arpa → exemple.com` | Reverse DNS : recon d'un range d'IP, et réputation des serveurs mail (un PTR absent/incohérent = mails rejetés). |
| **TXT** | Texte libre | `"v=spf1 include:_spf.google.com ~all"` | Cœur de la lutte anti-spoofing : **SPF, DKIM, DMARC** vivent dans des TXT. Aussi utilisé pour la vérification de domaine. |
| **NS** | **Délègue** une zone à ses serveurs de noms autoritaires | `exemple.com → ns1.hébergeur.com` | Un NS mal configuré peut autoriser un **transfert de zone (AXFR)** → fuite de **tous** les enregistrements. Test classique de recon. |
 
### Le trio anti-spoofing (à retenir, tout en TXT)
- **SPF** : liste les serveurs autorisés à envoyer du mail pour le domaine.
- **DKIM** : signe cryptographiquement les mails (clé publique publiée en DNS).
- **DMARC** : dit quoi faire si SPF/DKIM échouent (rien / quarantaine / rejet) + reporting.
### Pour aller plus loin (vu rapidement)
- **SOA** : enregistrement « maître » d'une zone (serveur primaire, numéro de série, TTL). Une zone en a toujours un.
- **SRV** : localise un service (host + port), ex. `_sip._tcp`. Très présent en environnement Active Directory.
- **CAA** : restreint quelles autorités de certification peuvent émettre un certificat pour le domaine.
---
 
## Ce que je retiens de la Semaine 1
1. Le **block size** répond à 90 % des questions de subnetting : IP → réseau → broadcast → plage.
2. **Réseau et broadcast ne sont jamais des hôtes** → toujours penser au **−2** (sauf /31).
3. Le DNS n'est pas qu'un annuaire : **TXT (SPF/DKIM/DMARC), NS (AXFR), CNAME (takeover)** sont des points sécu à part entière.
 
