#!/bin/bash
###############################################################################
# Prismateams Auto-Update Script v1.0
# Automatisch Updates von GitHub Repository holen
#
# Verwendung:
#   sudo /opt/prismateams/scripts/auto_update.sh
#
# Crontab (automatische Updates):
#   0 3 * * * /opt/prismateams/scripts/auto_update.sh
#
###############################################################################

set -e

# =============================================================================
# KONFIGURATION - ANPASSBAR
# =============================================================================
REPO_URL="https://github.com/TheJoJo1/Prismateams_web.git"
INSTALL_DIR="/opt/prismateams"
BACKUP_DIR="/var/backups/prismateams"
LOG_DIR="/var/log/prismateams"
LOG_FILE="$LOG_DIR/auto_update_$(date +%Y%m%d_%H%M%S).log"
GIT_BRANCH="main"
VENV_PATH="$INSTALL_DIR/venv"
SERVICE_NAME="prismateams"
WEB_USER="prismateams"
WEB_GROUP="prismateams"
MAX_BACKUPS=5

# =============================================================================
# FARBEN & LOGGING
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

fail() {
    log_error "$1"
    exit 1
}

# =============================================================================
# FUNKTIONEN
# =============================================================================

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Dieses Script muss als root ausgefuehrt werden!"
        exit 1
    fi
}

check_dependencies() {
    log "Pruefe Abhaengigkeiten..."
    local missing=()
    for cmd in git rsync python3 mysql mysqldump; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Fehlende Abhaengigkeiten: ${missing[*]}"
        log "Installiere mit: sudo apt install ${missing[*]}"
        exit 1
    fi
    log_success "Alle Abhaengigkeiten vorhanden"
}

get_current_commit() {
    cd "$INSTALL_DIR" 2>/dev/null && git rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

get_latest_commit() {
    git ls-remote --heads "$REPO_URL" "$GIT_BRANCH" 2>/dev/null | head -1 | cut -d'/' -f3 | cut -c1-8 || echo "unknown"
}

get_current_version() {
    if [ -f "$INSTALL_DIR/version.txt" ]; then
        cat "$INSTALL_DIR/version.txt"
    elif [ -f "$INSTALL_DIR/VERSION" ]; then
        cat "$INSTALL_DIR/VERSION"
    else
        cd "$INSTALL_DIR" && git describe --tags --abbrev=0 2>/dev/null || echo "unknown"
    fi
}

cleanup_old_backups() {
    log "Bereinige alte Backups..."
    (cd "$BACKUP_DIR" && ls -t | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f) 2>/dev/null || true
    log_success "Alte Backups bereinigt"
}

create_backup() {
    log "Erstelle Backup..."
    mkdir -p "$BACKUP_DIR"

    # Datenbank Backup
    if command -v mysqldump &>/dev/null; then
        log "Backupe MySQL Datenbank..."
        local db_user=$(grep -oP 'DB_USER=\K[^ ]+' "$INSTALL_DIR/.env" 2>/dev/null || echo "prismateams")
        local db_name=$(grep -oP 'DATABASE_URI=.*\/\K[^?]+' "$INSTALL_DIR/.env" 2>/dev/null || echo "prismateams")
        local db_pass=$(grep -oP 'DB_PASSWORD=\K[^ ]+' "$INSTALL_DIR/.env" 2>/dev/null || echo "")

        local db_backup="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
        if [ -n "$db_pass" ]; then
            mysqldump -u "$db_user" -p"$db_pass" "$db_name" > "$db_backup" 2>/dev/null
        fi

        if [ ! -s "$db_backup" ]; then
            mysqldump -u "$db_user" "$db_name" > "$db_backup" 2>/dev/null
        fi

        if [ -s "$db_backup" ]; then
            log_success "Datenbank-Backup erstellt: $db_backup"
        else
            log_warn "Datenbank-Backup fehlgeschlagen"
        fi
    else
        log_warn "mysqldump nicht gefunden, ueberspringe Datenbank-Backup"
    fi

    # Uploads Backup
    if [ -d "$INSTALL_DIR/uploads" ]; then
        log "Backupe Uploads-Verzeichnis..."
        tar -czf "$BACKUP_DIR/uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz" -C "$INSTALL_DIR" uploads 2>/dev/null && \
        log_success "Uploads-Backup erstellt" || \
        log_warn "Uploads-Backup fehlgeschlagen"
    fi

    # .env Backup
    if [ -f "$INSTALL_DIR/.env" ]; then
        log "Backupe .env Datei..."
        cp "$INSTALL_DIR/.env" "$BACKUP_DIR/.env.backup_$(date +%Y%m%d_%H%M%S)" && \
        log_success ".env Backup erstellt" || \
        log_warn ".env Backup fehlgeschlagen"
    fi

    cleanup_old_backups
}

stop_service() {
    log "Stoppe $SERVICE_NAME Service..."
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl stop "$SERVICE_NAME"
        local retries=30
        local count=0
        while systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && [ $count -lt $retries ]; do
            sleep 1
            count=$((count + 1))
        done
        if [ $count -ge $retries ]; then
            log_warn "Service konnte nicht gestoppt werden, versuche SIGTERM..."
            pkill -TERM -f gunicorn || true
            sleep 5
        fi
        log_success "Service gestoppt"
    else
        log_warn "Service $SERVICE_NAME laeuft nicht, ueberspringe..."
    fi
}

start_service() {
    log "Starte $SERVICE_NAME Service..."
    systemctl start "$SERVICE_NAME" 2>/dev/null || fail "Service konnte nicht gestartet werden"

    local retries=30
    local count=0
    while ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null && [ $count -lt $retries ]; do
        sleep 1
        count=$((count + 1))
    done
    if [ $count -ge $retries ]; then
        log_error "Service konnte nicht gestartet werden!"
        log "Versuche manuell: systemctl start $SERVICE_NAME"
        log "Logs: journalctl -u $SERVICE_NAME -n 50"
        return 1
    fi
    log_success "Service gestartet"
}

perform_update() {
    log "Fuehre Update durch..."

    cd "$INSTALL_DIR" || fail "Installationsverzeichnis nicht gefunden: $INSTALL_DIR"

    local current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "$GIT_BRANCH")
    local current_sha=$(get_current_commit)
    local latest_sha=$(get_latest_commit)

    log "Aktueller Commit: $current_sha"
    log "Neuester Commit:  $latest_sha"

    if [ "$current_sha" = "unknown" ] || [ "$latest_sha" = "unknown" ]; then
        log_warn "Konnte Commits nicht vergleichen, versuche trotzdem Update..."
    elif [ "$current_sha" = "$latest_sha" ]; then
        log_success "Keine neuen Aenderungen veruegbar (bereits aktuell: $current_sha)"
        return 0
    fi

    if [ "$current_branch" != "$GIT_BRANCH" ]; then
        log "Wechsle zu Branch $GIT_BRANCH..."
        git fetch origin "$GIT_BRANCH" 2>/dev/null || true
        git checkout "$GIT_BRANCH" 2>/dev/null || fail "Konnte nicht zu Branch $GIT_BRANCH wechseln"
    fi

    log "Lade neueste Aenderungen von GitHub..."
    git fetch origin
    git reset --hard origin/"$GIT_BRANCH" || fail "Git Reset fehlgeschlagen"

    log_success "Code aktualisiert auf Commit: $(get_current_commit)"

    if [ -f "$VENV_PATH/bin/pip" ]; then
        log "Aktualisiere Python Pakete..."
        "$VENV_PATH/bin/pip" install --upgrade pip setuptools wheel 2>/dev/null || true
        "$VENV_PATH/bin/pip" install -r requirements.txt 2>/dev/null || \
        log_warn "Pip Install fehlgeschlagen"
    else
        log_warn "VENV nicht gefunden: $VENV_PATH"
    fi

    if [ -f "$INSTALL_DIR/scripts/init_database.py" ]; then
        log "Fuehre Datenbank Migrationen aus..."
        cd "$INSTALL_DIR"
        su -s /bin/bash -c "cd '$INSTALL_DIR' && FLASK_ENV=production '$VENV_PATH/bin/python' scripts/init_database.py" "$WEB_USER" 2>/dev/null && \
        log_success "Datenbank Migrationen ausgefuehrt" || \
        log_warn "Datenbank Migration fehlgeschlagen"
    fi

    log "Setze Berechtigungen..."
    chown -R "$WEB_USER:$WEB_GROUP" "$INSTALL_DIR"
    chmod -R 755 "$INSTALL_DIR/uploads" 2>/dev/null || true
    chmod -R 755 "$INSTALL_DIR/app/static" 2>/dev/null || true

    log_success "Update erfolgreich durchgefuehrt"
    return 0
}

check_version() {
    log "Pruefe Version..."
    local current_version=$(get_current_version)
    local current_commit=$(get_current_commit)
    local latest_commit=$(get_latest_commit)

    log "Aktuelle Version: ${current_version:-unknown}"
    log "Aktueller Commit:  ${current_commit:-unknown}"
    log "Neuester Commit:   ${latest_commit:-unknown}"

    if [ "$current_commit" = "$latest_commit" ]; then
        log_success "System ist bereits aktuell!"
        return 1
    fi

    return 0
}

# =============================================================================
# HAUPTPROGRAMM
# =============================================================================

main() {
    check_root
    check_dependencies

    mkdir -p "$LOG_DIR"
    exec > >(tee -a "$LOG_FILE") 2>&1

    echo
    echo "================================================================================"
    echo "  Prismateams Auto-Update Script v1.0"
    echo "  Repository: $REPO_URL"
    echo "  Branch:    $GIT_BRANCH"
    echo "  Zeit:      $(date '+%Y-%m-%d %H:%M:%S')"
    echo "================================================================================"
    echo

    if check_version; then
        stop_service
        create_backup
        perform_update
        start_service
    else
        log_success "System ist bereits auf dem neuesten Stand."
    fi

    echo
    echo "================================================================================"
    echo "  Update abgeschlossen!"
    echo "  Log:       $LOG_FILE"
    echo "  Backup:   $BACKUP_DIR"
    echo "  Version:  $(get_current_version)"
    echo "  Commit:   $(get_current_commit)"
    echo "================================================================================"
}

main "$@"
