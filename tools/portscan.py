#!/usr/bin/env python3
"""
portscan.py — Mini scanner de ports TCP (TCP connect scan).

Auteur : Ichroc — cyber-writeups/tools
Usage légal uniquement : cibles que tu possèdes ou pour lesquelles tu as
une autorisation écrite (ton home lab, tes VM). Scanner sans autorisation
est illégal.

Exemples :
    python3 portscan.py 127.0.0.1
    python3 portscan.py 192.168.1.10 -p 1-1024
    python3 portscan.py 10.10.10.5 -p 22,80,443,8080 -t 0.5 -w 200 --banner
"""

import argparse
import socket
import concurrent.futures
from datetime import datetime

# --- Table de correspondance minimale port -> service courant ---------------
COMMON_SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 139: "netbios", 143: "imap", 443: "https",
    445: "smb", 3306: "mysql", 3389: "rdp", 5432: "postgresql",
    6379: "redis", 8080: "http-alt", 8443: "https-alt",
}


def parse_ports(spec):
    """Transforme une spec de ports en liste triée d'entiers uniques.

    Accepte : "80" | "1-1024" | "22,80,443" | "22,80,8000-8100".
    Lève ValueError si un port sort de 1..65535 ou si la syntaxe est invalide.
    """
    ports = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:                       # une plage, ex. "8000-8100"
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            if start > end:
                start, end = end, start        # tolère "100-1"
            for p in range(start, end + 1):
                ports.add(p)
        else:                                  # un port isolé
            ports.add(int(part))
    for p in ports:
        if not (1 <= p <= 65535):
            raise ValueError(f"Port hors limites (1-65535) : {p}")
    return sorted(ports)


def resolve(target):
    """Résout un nom d'hôte en IP. Renvoie l'IP (str) ou lève une exception."""
    return socket.gethostbyname(target)


def scan_port(ip, port, timeout, grab_banner=False):
    """Teste UN port. Renvoie un dict si ouvert, sinon None.

    On tente un connect() complet :
      - succès           -> port ouvert
      - refus (RST)      -> ConnectionRefusedError -> fermé
      - pas de réponse   -> socket.timeout -> filtré
    """
    # AF_INET = IPv4, SOCK_STREAM = TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))   # 0 = succès, sinon code d'erreur
        if result != 0:
            return None                        # fermé ou filtré : on ignore

        banner = ""
        if grab_banner:
            try:
                # Certains services parlent en premier (SSH, FTP, SMTP).
                # On tente une petite lecture ; sinon on pousse une requête
                # HTTP minimale pour faire réagir les serveurs web.
                sock.settimeout(1.0)
                try:
                    banner = sock.recv(1024).decode(errors="ignore").strip()
                except socket.timeout:
                    sock.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                    banner = sock.recv(1024).decode(errors="ignore").strip()
                banner = banner.splitlines()[0] if banner else ""
            except Exception:
                banner = ""

        return {
            "port": port,
            "service": COMMON_SERVICES.get(port, "unknown"),
            "banner": banner,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Mini scanner de ports TCP (connect scan)."
    )
    parser.add_argument("target", help="IP ou nom d'hôte à scanner")
    parser.add_argument("-p", "--ports", default="1-1024",
                        help="Ports : '80', '1-1024', '22,80,443' (défaut: 1-1024)")
    parser.add_argument("-t", "--timeout", type=float, default=1.0,
                        help="Timeout par port en secondes (défaut: 1.0)")
    parser.add_argument("-w", "--workers", type=int, default=100,
                        help="Nombre de threads en parallèle (défaut: 100)")
    parser.add_argument("--banner", action="store_true",
                        help="Tente de récupérer la bannière du service")
    args = parser.parse_args()

    # 1. Résolution du nom
    try:
        ip = resolve(args.target)
    except socket.gaierror:
        print(f"[!] Impossible de résoudre : {args.target}")
        return

    # 2. Parsing des ports
    try:
        ports = parse_ports(args.ports)
    except ValueError as e:
        print(f"[!] Spec de ports invalide : {e}")
        return

    print(f"[*] Cible      : {args.target} ({ip})")
    print(f"[*] Ports      : {len(ports)} à tester")
    print(f"[*] Démarrage  : {datetime.now():%H:%M:%S}")
    print("-" * 48)

    open_ports = []
    # 3. Scan concurrent : un pool de threads teste les ports en parallèle.
    #    Le réseau passe son temps à ATTENDRE (I/O), donc les threads sont
    #    parfaits ici : pendant qu'un port attend, un autre travaille.
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(scan_port, ip, p, args.timeout, args.banner): p
            for p in ports
        }
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                open_ports.append(res)

    # 4. Affichage trié
    open_ports.sort(key=lambda r: r["port"])
    if open_ports:
        print(f"{'PORT':<8}{'ÉTAT':<9}{'SERVICE':<14}BANNIÈRE")
        for r in open_ports:
            print(f"{r['port']:<8}{'open':<9}{r['service']:<14}{r['banner']}")
    else:
        print("[*] Aucun port ouvert trouvé.")

    print("-" * 48)
    print(f"[*] Terminé    : {len(open_ports)} port(s) ouvert(s) "
          f"sur {len(ports)} testé(s).")


if __name__ == "__main__":
    main()
