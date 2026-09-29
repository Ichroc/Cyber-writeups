# portscan.py — Mini scanner de ports TCP

Scanner de ports TCP en Python (technique *TCP connect scan*, sans privilège root).
Premier outil du repo `cyber-writeups/tools`.

> ⚠️ **Cadre légal.** À utiliser **uniquement** sur des cibles que tu possèdes ou
> pour lesquelles tu as une autorisation écrite (ton home lab, tes VM, une box HTB/THM).
> Scanner un système sans autorisation est illégal.

## Comment ça marche

Un port TCP « ouvert » signifie qu'un service écoute derrière. Le scanner tente
une connexion TCP complète (`connect`) sur chaque port :

| Réponse réseau | État déduit |
|---|---|
| Connexion acceptée (SYN/ACK) | **ouvert** |
| Connexion refusée (RST) | fermé |
| Aucune réponse (timeout) | filtré (pare-feu) |

Le scan est **concurrent** : un pool de threads teste de nombreux ports en
parallèle, car un scan passe l'essentiel de son temps à *attendre* le réseau.

## Usage

```bash
python3 portscan.py <cible> [options]
```

| Option | Rôle | Défaut |
|---|---|---|
| `cible` | IP ou nom d'hôte | (obligatoire) |
| `-p`, `--ports` | `80`, `1-1024`, `22,80,443`, `22,8000-8100` | `1-1024` |
| `-t`, `--timeout` | Timeout par port (secondes) | `1.0` |
| `-w`, `--workers` | Threads en parallèle | `100` |
| `--banner` | Récupère la bannière du service | désactivé |

## Exemples

```bash
# Ports courants sur une machine du lab
python3 portscan.py 192.168.1.10 -p 22,80,443,3306

# Les 1024 premiers ports, plus rapide
python3 portscan.py 10.10.10.5 -p 1-1024 -w 200 -t 0.5

# Avec identification des services
python3 portscan.py 127.0.0.1 -p 1-10000 --banner
```

## Exemple de sortie

```
[*] Cible      : 127.0.0.1 (127.0.0.1)
[*] Ports      : 4 à tester
------------------------------------------------
PORT    ÉTAT     SERVICE       BANNIÈRE
22      open     ssh           SSH-2.0-OpenSSH_8.9
80      open     http          HTTP/1.0 200 OK
------------------------------------------------
[*] Terminé    : 2 port(s) ouvert(s) sur 4 testé(s).
```

## Limites (assumées, et pistes d'amélioration)

- **TCP connect scan** : bruyant (connexion complète, souvent journalisée côté
  cible), contrairement au SYN scan furtif de Nmap (`-sS`, qui nécessite root).
- Pas d'UDP, pas de détection de version fine, pas d'IPv6.
- Améliorations possibles : export JSON/CSV, scan UDP, barre de progression,
  détection de version plus riche.

## Notes d'apprentissage

- `socket.AF_INET` = IPv4, `socket.SOCK_STREAM` = TCP.
- `connect_ex()` renvoie `0` en cas de succès (au lieu de lever une exception),
  pratique pour tester un port sans `try/except` à chaque fois.
- `ThreadPoolExecutor` : idéal pour de l'I/O réseau (le GIL Python n'est pas un
  frein ici, car les threads attendent le réseau, ils ne calculent pas).
- `settimeout()` transforme un port filtré (silencieux) en `timeout` rapide au
  lieu d'un blocage de plusieurs secondes.
