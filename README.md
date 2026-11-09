# Cyber-writeups

> Carnet personnel de montée en compétences en **cybersécurité** — réseau, Linux, escalade de privilèges et exploitation web. Chaque dossier `phase-*` correspond à une étape de progression ; les writeups mêlent théorie, commandes, payloads et captures, avec à chaque fois le **pourquoi** derrière la technique.

![Focus](https://img.shields.io/badge/Focus-S%C3%A9curit%C3%A9%20offensive-0d1117?style=flat-square)
![Langue](https://img.shields.io/badge/Langue-Fran%C3%A7ais-blue?style=flat-square)
![Lab](https://img.shields.io/badge/Environnement-Lab%20isol%C3%A9-3fb950?style=flat-square)

---

## Sommaire

| Phase | Thème | Writeups |
|-------|-------|----------|
| **0** | Fondamentaux réseau | Subnetting & DNS |
| **1** | Linux & escalade de privilèges | Permissions · Tâches planifiées · systemd |
| **2** | Exploitation web | DVWA · BadStore |
| — | Outils | `portscan.py` |

---

### Phase 0 — Fondamentaux réseau

- [**Subnetting & DNS**](phase-0/subnetting-et-dns.md) — réflexes de subnetting (table de référence, découpage) et fiche mémo DNS sous l'angle sécurité.

### Phase 1 — Linux & escalade de privilèges

La triade privesc, abordée sous tous les angles (modèle, vecteurs offensifs, durcissement) :

- [**Permissions & escalade de privilèges**](phase-1/linux-offensif.md) — modèle rwx, bits spéciaux (SUID/SGID/sticky), vecteurs de privesc et défense.
- [**Tâches planifiées (cron, at, timers)**](phase-1/linux-cron.md) — tous les mécanismes de planification et les privesc qui en découlent.
- [**systemd & services**](phase-1/linux-systemd.md) — anatomie d'une unité, priorité des emplacements, vecteurs offensifs et durcissement.

### Phase 2 — Exploitation web

TP de sécurité offensive sur applications **volontairement vulnérables**, en lab isolé :

- [**DVWA**](phase-2/dvwa.md) — XSS (reflected/stored), CSRF, command injection, SQLi + cracking et webshell, niveau par niveau (Low → Medium → High).
- [**BadStore**](phase-2/badstore.md) — recon, robots.txt, XSS, parameter & cookie tampering, SQL injection — 7 exploits, captures d'écran à l'appui.

### Outils

- [**`portscan.py`**](tools/README.md) — mini scanner de ports TCP.

---

## ⚠️ Cadre légal & éthique

L'intégralité des manipulations offensives de ce dépôt est réalisée **exclusivement** sur des environnements de lab personnels, des VM volontairement vulnérables ou des cibles pour lesquelles j'ai une autorisation explicite. Rien ici n'est destiné à être employé contre un système tiers sans consentement écrit — c'est le cadre légal et déontologique du test d'intrusion.

---

*Notes d'apprentissage — ESEO, spécialité Cloud, Système & Sécurité.*
