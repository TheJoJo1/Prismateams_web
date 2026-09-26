#!/usr/bin/env bash
###############################################################################
# Prismateams Web – Debian/Ubuntu Installer
#
# Ziel: einfache Installation auf Debian 12+, Ubuntu 22.04+ und ähnlichen
# Debian-basierten Linux-Distributionen.
#
# Verwendung:
#   sudo bash scripts/install_debian.sh
#   sudo bash scripts/install_debian.sh --interactive
#   sudo bash scripts/install_debian.sh --unattended
#
###############################################################################

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="/var/log/prismateams"
LOG_FILE="${LOG_DIR}/install_debian_$(date +%Y%m%d_%H%M%S).log"
APP_USER="prismateams"
APP_GROUP="prismateams"
APP_HOME="/opt/prismateams"
VENV_PATH="${APP_HOME}/venv"
UPLOADS_DIR="${APP_HOME}/uploads"
DATA_DIR="/var/lib/prismateams"

INTERACTIVE=1
DB_TYPE="mysql"
DB_HOST="localhost"
DB_PORT="3306"
DB_NAME="prismateams"
DB_USER="prismateams"
DB_PASSWORD=""
NGINX_DOMAIN="prismateams.local"
INSTALL_NGINX="yes"
ENABLE_SSL="no"
INSTALL_REDIS="yes"
INSTALL_FFMPEG="no"
INSTALL_LIBREOFFICE="no"
GUNICORN_WORKERS="2"
GUNICORN_THREADS="8"
GUNICORN_PORT="5000"
GUNICORN_BIND="127.0.0.1:${GUNICORN_PORT}"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
log_info() { echo "ℹ️  $*"; }
log_ok() { echo "✅ $*"; }
log_warn() { echo "⚠️  $*"; }
log_err() { echo "❌ $*" >&2; }
fail() { log_err "$1"; exit 1; }

check_root() {
    [[ $EUID -eq 0 ]] || fail "This script must be run as root (sudo)."
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_VERSION="${VERSION_ID:-unknown}"
        log_info "Detected: ${NAME:-Linux} (${DISTRO_ID} ${DISTRO_VERSION})"
    else
        fail "Could not detect OS release."
    fi

    case "$DISTRO_ID" in
        debian|ubuntu|linuxmint|pop|elementary)
            ;;
        *)
            log_warn "Distribution is not officially tested: ${DISTRO_ID}"
            read -r -p "Continue anyway? [y/N] " answer
            [[ "${answer:-n}" =~ ^[Yy]$ ]] || exit 3
            ;;
    esac
}

install_pkg() {
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
}

install_basics() {
    log_info "Installing base packages"
    install_pkg \
        curl wget git ca-certificates gnupg software-properties-common \
        build-essential python3 python3-venv python3-pip python3-dev \
        libssl-dev libffi-dev libpq-dev \
        nginx redis-server rsync sqlite3 \
        unzip zip jq
}

create_app_user() {
    if ! id "$APP_USER" >/dev/null 2>&1; then
        useradd -r -m -d "$APP_HOME" -s /bin/bash "$APP_USER"
    fi
    mkdir -p "$APP_HOME" "$DATA_DIR" "$UPLOADS_DIR"
    chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" "$DATA_DIR" "$UPLOADS_DIR"
}

ensure_group() {
    if ! getent group "$APP_GROUP" >/dev/null; then
        groupadd "$APP_GROUP"
    fi
}

setup_mysql() {
    log_info "Setting up MariaDB/MySQL"
    install_pkg mariadb-server python3-mysqldb
    systemctl enable --now mariadb || systemctl enable --now mysql
    if [[ -z "$DB_PASSWORD" ]]; then
        DB_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
    fi
    mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
    log_ok "MySQL/MariaDB ready"
}

setup_postgres() {
    log_info "Setting up PostgreSQL"
    install_pkg postgresql postgresql-contrib python3-psycopg2
    systemctl enable --now postgresql
    if [[ -z "$DB_PASSWORD" ]]; then
        DB_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
    fi
    sudo -u postgres psql <<SQL
CREATE DATABASE "${DB_NAME}" WITH ENCODING 'UTF8';
CREATE USER "${DB_USER}" WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "${DB_USER}";
SQL
    log_ok "PostgreSQL ready"
}

setup_database() {
    case "$DB_TYPE" in
        mysql|mariadb) setup_mysql ;;
        postgres|postgresql) setup_postgres ;;
        sqlite) mkdir -p "$DATA_DIR" ;;
        *) fail "Unsupported DB type: $DB_TYPE" ;;
    esac
}

copy_app() {
    log_info "Copying project to ${APP_HOME}"
    rsync -a --delete \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='__pycache__' \
        --exclude='.pytest_cache' \
        --exclude='.env' \
        --exclude='uploads' \
        "${PROJECT_ROOT}/" "${APP_HOME}/"
    chown -R "${APP_USER}:${APP_GROUP}" "${APP_HOME}"
}

setup_venv() {
    log_info "Creating Python virtual environment"
    python3 -m venv "$VENV_PATH"
    "$VENV_PATH/bin/pip" install --upgrade pip setuptools wheel
    "$VENV_PATH/bin/pip" install -r "${APP_HOME}/requirements.txt"
    chown -R "${APP_USER}:${APP_GROUP}" "$VENV_PATH"
}

create_env() {
    local env_file="${APP_HOME}/.env"
    if [[ -f "$env_file" ]]; then
        log_warn "Existing .env detected; leaving it in place"
        return 0
    fi

    local secret_key
    secret_key="$(openssl rand -base64 48 | tr -d '\n')"

    cat > "$env_file" <<EOF
FLASK_ENV=production
DEBUG=False
SECRET_KEY=${secret_key}
DATABASE_URI=mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
REDIS_ENABLED=${INSTALL_REDIS}
REDIS_URL=redis://localhost:6379/0
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
REMEMBER_COOKIE_SECURE=True
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=536870912
PUBLIC_BASE_URL=https://${NGINX_DOMAIN}
ENABLE_APP_GZIP=True
EOF
    chmod 600 "$env_file"
    chown "${APP_USER}:${APP_GROUP}" "$env_file"
    log_ok "Created .env"
}

setup_uploads() {
    log_info "Preparing upload directories"
    mkdir -p "${UPLOADS_DIR}" \
        "${UPLOADS_DIR}/chat" \
        "${UPLOADS_DIR}/chat/avatars" \
        "${UPLOADS_DIR}/profile_pics" \
        "${UPLOADS_DIR}/manuals" \
        "${UPLOADS_DIR}/media_downloader" \
        "${UPLOADS_DIR}/file_converter"
    chown -R "${APP_USER}:${APP_GROUP}" "${UPLOADS_DIR}"
    chmod -R 755 "${UPLOADS_DIR}"
}

initialize_db() {
    log_info "Initializing database schema"
    chown -R "${APP_USER}:${APP_GROUP}" "${APP_HOME}"
    cd "$APP_HOME"
    su -s /bin/bash -c "cd '${APP_HOME}' && FLASK_ENV=production '${VENV_PATH}/bin/python' scripts/init_database.py" "$APP_USER" || fail "Database initialization failed"
    log_ok "Database initialized"
}

configure_systemd() {
    log_info "Configuring systemd service"
    cat > /etc/systemd/system/prismateams.service <<EOF
[Unit]
Description=Prismateams Web Portal
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_HOME}
EnvironmentFile=${APP_HOME}/.env
ExecStart=${VENV_PATH}/bin/gunicorn --worker-class gthread --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --bind ${GUNICORN_BIND} --timeout 180 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 wsgi:app
Restart=on-failure
RestartSec=10s
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now prismateams || fail "Failed to enable prismateams service"
    log_ok "Prismateams service enabled"
}

setup_nginx() {
    if [[ "$INSTALL_NGINX" != "yes" ]]; then
        return 0
    fi

    log_info "Configuring nginx reverse proxy"
    install_pkg nginx

    cat > /etc/nginx/sites-available/prismateams.conf <<EOF
upstream prismateams_app {
    server 127.0.0.1:${GUNICORN_PORT};
}

server {
    listen 80;
    server_name ${NGINX_DOMAIN};

    location / {
        proxy_pass http://prismateams_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

    ln -sf /etc/nginx/sites-available/prismateams.conf /etc/nginx/sites-enabled/prismateams.conf
    rm -f /etc/nginx/sites-enabled/default
    nginx -t || fail "Nginx config invalid"
    systemctl enable --now nginx || fail "Failed to start nginx"
    log_ok "Nginx ready"
}

setup_redis() {
    if [[ "$INSTALL_REDIS" != "yes" ]]; then
        return 0
    fi
    log_info "Configuring Redis"
    systemctl enable --now redis-server || service redis-server start
    log_ok "Redis ready"
}

setup_ffmpeg() {
    if [[ "$INSTALL_FFMPEG" != "yes" ]]; then
        return 0
    fi
    log_info "Installing FFmpeg"
    install_pkg ffmpeg
    log_ok "FFmpeg installed"
}

setup_libreoffice() {
    if [[ "$INSTALL_LIBREOFFICE" != "yes" ]]; then
        return 0
    fi
    log_info "Installing LibreOffice"
    install_pkg libreoffice
    log_ok "LibreOffice installed"
}

interactive_setup() {
    log_info "Interactive setup"
    read -r -p "Database type [mysql/mariadb|postgresql|sqlite] [mysql]: " answer
    DB_TYPE="${answer:-mysql}"

    read -r -p "Database host [localhost]: " answer
    DB_HOST="${answer:-localhost}"

    read -r -p "Database name [prismateams]: " answer
    DB_NAME="${answer:-prismateams}"

    read -r -p "Database user [prismateams]: " answer
    DB_USER="${answer:-prismateams}"

    read -r -s -p "Database password (empty = random): " answer
    echo
    DB_PASSWORD="${answer}"

    read -r -p "Install Nginx? [Y/n]: " answer
    INSTALL_NGINX="${answer:-y}"
    if [[ "$INSTALL_NGINX" =~ ^[Yy]$ ]]; then
        read -r -p "Domain name [prismateams.local]: " answer
        NGINX_DOMAIN="${answer:-prismateams.local}"
    fi

    read -r -p "Install Redis? [Y/n]: " answer
    INSTALL_REDIS="${answer:-y}"

    read -r -p "Install FFmpeg? [y/N]: " answer
    [[ "$answer" =~ ^[Yy]$ ]] && INSTALL_FFMPEG="yes" || INSTALL_FFMPEG="no"

    read -r -p "Install LibreOffice? [y/N]: " answer
    [[ "$answer" =~ ^[Yy]$ ]] && INSTALL_LIBREOFFICE="yes" || INSTALL_LIBREOFFICE="no"
}

show_summary() {
    echo
    echo "================================================================================"
    echo "Prismateams installation completed"
    echo "================================================================================"
    echo "Web URL: http://${NGINX_DOMAIN}"
    echo "App dir: ${APP_HOME}"
    echo "Virtual env: ${VENV_PATH}"
    echo "Log file: ${LOG_FILE}"
    echo "Database: ${DB_TYPE} / ${DB_NAME}"
    echo "Important: review ${APP_HOME}/.env before first production use."
    echo "================================================================================"
}

main() {
    case "${1:-}" in
        --help|-h)
            echo "Usage: sudo bash scripts/install_debian.sh [--interactive|--unattended|--help]"
            exit 0
            ;;
        --interactive)
            INTERACTIVE=1
            ;;
        --unattended)
            INTERACTIVE=0
            ;;
    esac

    check_root
    check_os

    if [[ "$INTERACTIVE" -eq 1 ]]; then
        interactive_setup
    fi

    ensure_group
    create_app_user
    install_basics
    setup_database
    copy_app
    setup_venv
    create_env
    setup_uploads
    initialize_db
    configure_systemd
    setup_redis
    setup_nginx
    setup_ffmpeg
    setup_libreoffice
    show_summary
}

main "$@"
