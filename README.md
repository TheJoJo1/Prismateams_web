# Prismateams – Installationsskript (Ubuntu)

<p align="center">
  <img src="../app/static/img/logo.png" alt="Prismateams Logo" width="96">
</p>

<h1 align="center">Prismateams – Installationsskript (Ubuntu)</h1>

<p align="center">
  <strong>Dokumentation · Version 3.4.12</strong><br>
  <img src="https://img.shields.io/badge/version-3.4.12-7c3aed?style=flat-square" alt="Version 3.4.12">
  <img src="https://img.shields.io/badge/Ubuntu-24.04-E95420?style=flat-square&logo=ubuntu&logoColor=white" alt="Ubuntu 24.04">
  <img src="https://img.shields.io/badge/Ubuntu-26.04-E95420?style=flat-square&logo=ubuntu&logoColor=white" alt="Ubuntu 26.04">
  <img src="https://img.shields.io/badge/Installer-ready-22c55e?style=flat-square" alt="Installer ready">
</p>

<p align="center">
  <a href="README.md">Übersicht</a> ·
  <a href="INSTALLATION.md">Manuelle Installation</a> ·
  <a href="WARTUNG.md">Wartung</a> ·
  <a href="ERROR_HANDLING.md">Fehlerbehebung</a>
</p>

---

> **Einsatzbereit**  
> Der modulare Ubuntu-Installer (`scripts/install_ubuntu.sh` + `scripts/install_ubuntu/*.sh`) ist für **Produktion freigegeben**. Empfohlener Weg auf Ubuntu Server **24.04** und **26.04** LTS. Zusätzlich gibt es seit der aktuellen Version ein Debian-Alternativskript für Debian-basierte Linux-Systeme.

Skript-Pfad (beide Batches gleich):

- Entry Ubuntu: [`scripts/install_ubuntu.sh`](../scripts/install_ubuntu.sh)
- Entry Debian / Debian-basierte Distros: [`scripts/install_debian.sh`](../scripts/install_debian.sh)
- Module Ubuntu: [`scripts/install_ubuntu/`](../scripts/install_ubuntu/)

## Unterstützte Ubuntu-Batches

Der Installer erkennt `/etc/os-release` und akzeptiert beide LTS-Batches ohne Extra-Prompt:

| Batch | Version | Codename | Status |
|-------|---------|----------|--------|
| **Batch 1** | Ubuntu **24.04** LTS | Noble Numbat | Python 3.12, MySQL 8.0 |
| **Batch 2** | Ubuntu **26.04** LTS | Resolute Raccoon | Python 3.14, MySQL 8.4 |

Andere Ubuntu-Versionen: Warnung + Nachfrage (im Non-Interactive-Modus: Warnung, dann weiter). Nicht-Ubuntu: Abbruch.

## Debian / andere Debian-basierte Distros

Für Debian 12+ sowie Debian-basierte Distributionen wie Ubuntu, Linux Mint, Pop!_OS oder andere apt-basierte Systeme ist das Debian-Skript vorgesehen:

```bash
sudo bash scripts/install_debian.sh
```

Interaktiv:

```bash
sudo bash scripts/install_debian.sh --interactive
```

Mit Defaults im Nicht-Interaktiv-Modus:

```bash
sudo bash scripts/install_debian.sh --unattended
```

Das Debian-Skript richtet die Standard-Serverkomponenten für Prismateams ein, darunter:

- Python 3 + Virtual Environment
- MariaDB/MySQL oder PostgreSQL
- Redis
- Gunicorn + systemd
- Nginx Reverse Proxy
- Upload-Ordner und Initialisierung
- optionale FFmpeg-/LibreOffice-Erweiterungen

## Voraussetzungen

- Ubuntu **24.04** LTS oder **26.04** LTS oder Debian 12+
- Root-Zugriff (`sudo`)
- Internet-Verbindung
- Mindestens 4 GB RAM empfohlen (für Euro-Office)

## Schnellstart

```bash
git clone https://github.com/iAmCriptic/Prismateams_web.git
cd Prismateams_web
chmod +x scripts/install_ubuntu.sh scripts/install_debian.sh
sudo bash scripts/install_ubuntu.sh
```

Oder für Debian-basierte Distros:

```bash
sudo bash scripts/install_debian.sh
```

Ohne Optionen fragt das Skript interaktiv alle leeren Werte ab und zeigt vor dem Start eine Kurzbestätigung.

## Architektur

Jeder Installationsschritt ist ein eigenes Modul und meldet Status `ok` / `skipped` / `failed` / `aborted`. Am Ende erscheint eine Übersicht inkl. generierter Passwörter; zusätzlich wird `$INSTALL_DIR/install-report.txt` angelegt.

## Was kann konfiguriert werden?

- Installationsverzeichnis
- Git-Repository-URL und Branch (Fork / Development)
- Gunicorn-Port, Worker-Anzahl, Service ja/nein
- Nginx oder Apache (oder manuell) — Nginx setzt Gzip für CSS/JS/JSON; optional Brotli
- MySQL ja/nein (inkl. DB-Name/User/Passwort)
- Redis ja/nein
- Font-/Dokumenten-Tools (FFmpeg, LibreOffice)
- `.env`-Setup mit Default-Values

## Nach der Installation

1. `.env` prüfen (`$INSTALL_DIR/.env`)
2. Anwendung öffnen (`http://` oder `https://` Domain)
3. Admin über Setup-Assistent anlegen
4. Status prüfen: `systemctl status prismateams` und `systemctl status nginx`

Weitere Schritte: [WARTUNG.md](WARTUNG.md) · Probleme: [ERROR_HANDLING.md](ERROR_HANDLING.md) · manuell: [INSTALLATION.md](INSTALLATION.md)

---

<p align="center">
  <img src="../app/static/img/logo.png" alt="" width="40"><br>
  <sub>Prismateams 3.4.12 · Modularer Ubuntu-Installer · Debian- und Ubuntu-Varianten</sub>
</p>

