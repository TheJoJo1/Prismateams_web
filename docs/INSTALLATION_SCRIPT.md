# Prismateams – Installationsskripte

Dieser Bereich umfasst die modularen und distrospezifischen Installer für die Einrichtung des Portals auf Linux-Systemen.

## Verfügbare Installer

- `scripts/install_ubuntu.sh` – empfohlen für Ubuntu 24.04/26.04 LTS, inklusive modularer Installations-Logik und optionaler Zusatzmodule
- `scripts/install_debian.sh` – passend für Debian 12+ und andere Debian-basierte Linux-Distributionen

## Debian / andere Debian-basierte Linux-Distributionen

Für Debian 12+, Ubuntu 22.04+ und ähnliche Debian-basierte Systeme kann das Debian-Skript genutzt werden:

```bash
sudo bash scripts/install_debian.sh
```

Interaktiv:

```bash
sudo bash scripts/install_debian.sh --interactive
```

Nicht-interaktiv mit Defaults:

```bash
sudo bash scripts/install_debian.sh --unattended
```

Das Skript richtet typischerweise die folgenden Komponenten ein:

- Python 3 + Virtual Environment
- MariaDB/MySQL oder PostgreSQL (je nach Auswahl)
- Redis
- Gunicorn + systemd-Service
- Nginx als Reverse Proxy
- Upload-Verzeichnisse und Datenbankinitialisierung
- optionales FFmpeg und LibreOffice

Die beiden Installationsskripte ergänzen sich: Das Ubuntu-Skript ist für produktionsnahe Server-Installationen auf Ubuntu empfohlen; das Debian-Skript ist der leichtgewichtige Standardpfad für Debian-basierte Systeme und andere Debian-Derivate.
