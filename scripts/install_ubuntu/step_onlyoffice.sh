#!/bin/bash
# Euro-Office Document Server (Docs) via Docker
#
# Standard: Euro-Office (EU-Fork, API-kompatibel zu ONLYOFFICE Docs).
# Override: ONLYOFFICE_IMAGE=onlyoffice/documentserver:latest für klassisches OnlyOffice.
#
# Proxy-Pfade (Nginx/Apache, parallel):
#   /eurooffice  – Default für neue Installationen (.env)
#   /onlyoffice  – Legacy für bestehende Installationen
#
# Offiziell: https://github.com/Euro-Office/DocumentServer
# Image:     ghcr.io/euro-office/documentserver:latest

ONLYOFFICE_IMAGE="${ONLYOFFICE_IMAGE:-ghcr.io/euro-office/documentserver:latest}"
ONLYOFFICE_HOST_PORT="${ONLYOFFICE_HOST_PORT:-8080}"
ONLYOFFICE_CONTAINER="${ONLYOFFICE_CONTAINER:-eurooffice-documentserver}"
ONLYOFFICE_DATA_ROOT="${ONLYOFFICE_DATA_ROOT:-/var/lib/eurooffice/DocumentServer}"
LEGACY_ONLYOFFICE_CONTAINER="${LEGACY_ONLYOFFICE_CONTAINER:-onlyoffice-documentserver}"

_onlyoffice_is_eurooffice_image() {
    case "${ONLYOFFICE_IMAGE}" in
        *euro-office*|*eurooffice*) return 0 ;;
        *) return 1 ;;
    esac
}

_onlyoffice_container_running() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${ONLYOFFICE_CONTAINER}"
}

_onlyoffice_container_exists() {
    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "${ONLYOFFICE_CONTAINER}"
}

_legacy_onlyoffice_container_running() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${LEGACY_ONLYOFFICE_CONTAINER}"
}

_onlyoffice_port_in_use() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -qE ":${port}\\s"
        return $?
    fi
    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi
    return 1
}

_onlyoffice_dump_logs() {
    log_info "Letzte Document-Server-Container-Logs:"
    docker logs --tail 60 "${ONLYOFFICE_CONTAINER}" 2>&1 || true
}

# Leeres Bind-Mount auf /etc/euro-office/documentserver verdeckt default.json/local.json
# im Image. Der Entrypoint crasht dann (jq: Could not open file local.json) im Restart-Loop.
_onlyoffice_seed_eurooffice_config() {
    local dest="${ONLYOFFICE_DATA_ROOT}/config"
    mkdir -p "$dest"
    if [ -f "${dest}/default.json" ] && [ -s "${dest}/local.json" ]; then
        log_info "Document-Server-Config bereits vorhanden (${dest})"
        return 0
    fi

    log_info "Kopiere Document-Server-Config aus dem Image (leeres Volume würde den Start crashen)..."
    local seed="eurooffice-config-seed"
    docker rm -f "$seed" >/dev/null 2>&1 || true
    if ! docker create --name "$seed" "${ONLYOFFICE_IMAGE}" >/dev/null; then
        log_error "Seed-Container konnte nicht erzeugt werden"
        return 1
    fi
    rm -f "${dest}/local.json.tmp" 2>/dev/null || true
    if ! docker cp "${seed}:/etc/euro-office/documentserver/." "${dest}/"; then
        docker rm -f "$seed" >/dev/null 2>&1 || true
        log_error "docker cp der Document-Server-Config fehlgeschlagen"
        return 1
    fi
    docker rm -f "$seed" >/dev/null 2>&1 || true
    chmod -R a+rX "$dest" 2>/dev/null || true
    if [ ! -f "${dest}/local.json" ] || [ ! -f "${dest}/default.json" ]; then
        log_error "Config-Seed unvollständig (local.json/default.json fehlen in ${dest})"
        return 1
    fi
    log_success "Config aus Image nach ${dest} kopiert"
    return 0
}

# Leeres Logs-Volume verdeckt adminpanel/converter/docservice/metrics.
# Supervisord bricht sonst ab: "directory .../adminpanel/out.log does not exist".
_onlyoffice_prepare_eurooffice_log_dirs() {
    local dest="${ONLYOFFICE_DATA_ROOT}/logs"
    mkdir -p "$dest"/{adminpanel,converter,docservice,metrics}
    chmod -R a+rwX "$dest" 2>/dev/null || true
    log_info "Document-Server-Logverzeichnisse: ${dest}/{adminpanel,converter,docservice,metrics}"
}

# Data-Volume als root 0755 → Node-User ds kann App_Data nicht anlegen (EACCES, Editor-Fehler -4).
_onlyoffice_prepare_eurooffice_data_dir() {
    local dest="${ONLYOFFICE_DATA_ROOT}/data"
    mkdir -p "${dest}/App_Data"
    chmod -R a+rwX "$dest" 2>/dev/null || true
    log_info "Document-Server-Datenverzeichnis beschreibbar: ${dest}"
}

_onlyoffice_container_status() {
    docker inspect -f '{{.State.Status}}' "${ONLYOFFICE_CONTAINER}" 2>/dev/null || echo "missing"
}

# Host-Fonts für PDF/Druck im Document Server (Volume …/fonts).
# Nur Microsoft Core Fonts kopieren (Arial, Times New Roman, …) – die fehlen im Image.
# Carlito/Liberation/DejaVu liegen bereits im Document-Server-Image. Dieselben Familien
# zusätzlich ins Custom-Volume zu legen zerlegt font_selection.bin (Calibri→Carlito)
# und führt zu Open-Fehlern in Word/Excel/PowerPoint.
_onlyoffice_ensure_font_repos() {
    if command -v add-apt-repository >/dev/null 2>&1; then
        add-apt-repository -y universe >/dev/null 2>&1 || true
        add-apt-repository -y multiverse >/dev/null 2>&1 || true
    fi
    export DEBIAN_FRONTEND=noninteractive
    apt_update -qq || log_warning "apt-get update für Schriftarten fehlgeschlagen"
}

_onlyoffice_install_host_fonts() {
    log_info "Installiere Microsoft Core Fonts für Document Server (Arial, Times New Roman, …)..."
    _onlyoffice_ensure_font_repos

    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections
    echo "ttf-mscorefonts-installer msttcorefonts/present-mscorefonts-eula note" | debconf-set-selections

    # mscorefonts lädt TTFs von SourceForge – kann fehlschlagen; Carlito bleibt im Image
    if apt_install ttf-mscorefonts-installer cabextract; then
        log_success "Host-Schriftarten installiert (mscorefonts); Calibri rendert als Carlito"
    else
        log_warning "ttf-mscorefonts-installer fehlgeschlagen (EULA/Download) – Arial/Times ggf. unvollständig"
        log_warning "Document Server nutzt dann die im Image enthaltenen Ersatzschriften (Carlito/Liberation)"
    fi
}

_onlyoffice_copy_fonts_to_volume() {
    local dest="${ONLYOFFICE_DATA_ROOT}/fonts"
    mkdir -p "$dest"
    log_info "Bereite Document-Server-Fonts-Volume vor (nur mscorefonts, keine Duplikate)..."

    # Alte Kopien von Carlito/Liberation/DejaVu entfernen – sonst bleibt ein kaputter Index
    find "$dest" -maxdepth 1 -type f \( -iname '*.ttf' -o -iname '*.otf' -o -iname '*.ttc' \) -delete 2>/dev/null || true

    local copied=0
    local src="/usr/share/fonts/truetype/msttcorefonts"
    if [ -d "$src" ]; then
        while IFS= read -r -d '' fontfile; do
            if cp "$fontfile" "$dest/" 2>/dev/null; then
                copied=$((copied + 1))
            fi
        done < <(find "$src" -type f \( -iname '*.ttf' -o -iname '*.otf' \) -print0 2>/dev/null)
    fi

    if [ "$copied" -gt 0 ]; then
        log_success "${copied} Microsoft-Core-Schriften im Document-Server-Fonts-Volume"
    else
        log_warning "Keine mscorefonts zum Kopieren gefunden – Document Server nutzt Image-Fonts (Carlito für Calibri)"
    fi
}

_onlyoffice_run_container() {
    local run_err="$1"
    if _onlyoffice_is_eurooffice_image; then
        docker run -d \
            --name "${ONLYOFFICE_CONTAINER}" \
            --restart=always \
            -p "127.0.0.1:${ONLYOFFICE_HOST_PORT}:80" \
            -v "${ONLYOFFICE_DATA_ROOT}/logs:/var/log/euro-office/documentserver" \
            -v "${ONLYOFFICE_DATA_ROOT}/data:/var/lib/euro-office/documentserver" \
            -v "${ONLYOFFICE_DATA_ROOT}/config:/etc/euro-office/documentserver" \
            -v "${ONLYOFFICE_DATA_ROOT}/fonts:/usr/share/fonts/truetype/custom" \
            -e JWT_ENABLED=true \
            -e JWT_SECRET="${ONLYOFFICE_SECRET}" \
            -e JWT_HEADER=Authorization \
            -e ALLOW_PRIVATE_IP_ADDRESS=true \
            "${ONLYOFFICE_IMAGE}" >"${run_err}" 2>&1
        return $?
    fi

    # Legacy OnlyOffice volume layout (wenn ONLYOFFICE_IMAGE auf onlyoffice/… gesetzt)
    docker run -d \
        --name "${ONLYOFFICE_CONTAINER}" \
        --restart=always \
        -p "127.0.0.1:${ONLYOFFICE_HOST_PORT}:80" \
        -v "${ONLYOFFICE_DATA_ROOT}/logs:/var/log/onlyoffice" \
        -v "${ONLYOFFICE_DATA_ROOT}/data:/var/www/onlyoffice/Data" \
        -v "${ONLYOFFICE_DATA_ROOT}/lib:/var/lib/onlyoffice" \
        -v "${ONLYOFFICE_DATA_ROOT}/fonts:/usr/share/fonts/truetype/custom" \
        -e JWT_ENABLED=true \
        -e JWT_SECRET="${ONLYOFFICE_SECRET}" \
        -e JWT_HEADER=Authorization \
        -e ALLOW_PRIVATE_IP_ADDRESS=true \
        "${ONLYOFFICE_IMAGE}" >"${run_err}" 2>&1
}

step_onlyoffice() {
    if ! is_yes "$INSTALL_ONLYOFFICE"; then
        print_manual_onlyoffice_hint
        return 2
    fi

    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker nicht gefunden – Euro-Office Document Server braucht Docker"
        log_error "Schritt 'Docker' muss vorher erfolgreich sein"
        return 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_info "Docker-Daemon nicht bereit – starte neu..."
        systemctl start docker >/dev/null 2>&1 || true
        sleep 3
        if ! docker info >/dev/null 2>&1; then
            log_error "Docker-Daemon nicht erreichbar (docker info fehlgeschlagen)"
            return 1
        fi
    fi

    local mem_kb mem_gb
    mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
    mem_gb=$((mem_kb / 1024 / 1024))
    if [ "$mem_gb" -gt 0 ] && [ "$mem_gb" -lt 4 ]; then
        log_warning "Document Server empfiehlt ≥4 GB RAM (aktuell ca. ${mem_gb} GB) – Start kann scheitern/OOM"
    fi

    local free_kb=0
    free_kb=$(df -Pk /var/lib/docker 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -z "$free_kb" ] || [ "$free_kb" = "0" ]; then
        free_kb=$(df -Pk / 2>/dev/null | awk 'NR==2 {print $4}')
    fi
    if [ -n "$free_kb" ] && [ "$free_kb" -lt 5000000 ]; then
        log_warning "Wenig freier Speicher (~$((free_kb / 1024)) MB) – Docs-Image braucht mehrere GB"
    fi

    local arch
    arch=$(uname -m)
    if [ "$arch" != "x86_64" ] && [ "$arch" != "amd64" ]; then
        log_error "Document-Server-Docker-Image ist nur für amd64/x86_64 (diese Maschine: ${arch})"
        return 1
    fi

    if [ -z "${ONLYOFFICE_SECRET:-}" ]; then
        ONLYOFFICE_SECRET=$(generate_secret)
    fi

    # Legacy-Schutz: laufender OnlyOffice-Container belassen, wenn wir Euro-Office neu installieren
    if [ "${ONLYOFFICE_CONTAINER}" != "${LEGACY_ONLYOFFICE_CONTAINER}" ] \
        && _legacy_onlyoffice_container_running \
        && ! _onlyoffice_container_running; then
        if _onlyoffice_port_in_use "${ONLYOFFICE_HOST_PORT}"; then
            log_warning "Legacy-Container ${LEGACY_ONLYOFFICE_CONTAINER} läuft weiter auf Port ${ONLYOFFICE_HOST_PORT}"
            log_warning "Bestehende .env mit ONLYOFFICE_DOCUMENT_SERVER_URL=/onlyoffice bleibt kompatibel"
            log_warning "Optionaler Wechsel zu Euro-Office: siehe docs/WARTUNG.md"
            log_success "Document Server (Legacy OnlyOffice) belassen – kein Ersatz-Install"
            return 0
        fi
    fi

    mkdir -p "${ONLYOFFICE_DATA_ROOT}/data"
    mkdir -p "${ONLYOFFICE_DATA_ROOT}/logs"
    mkdir -p "${ONLYOFFICE_DATA_ROOT}/fonts"
    if _onlyoffice_is_eurooffice_image; then
        mkdir -p "${ONLYOFFICE_DATA_ROOT}/config"
    else
        mkdir -p "${ONLYOFFICE_DATA_ROOT}/lib"
    fi

    _onlyoffice_install_host_fonts
    _onlyoffice_copy_fonts_to_volume

    if _onlyoffice_port_in_use "${ONLYOFFICE_HOST_PORT}"; then
        if ! _onlyoffice_container_running; then
            log_error "Port ${ONLYOFFICE_HOST_PORT} ist belegt (nicht durch ${ONLYOFFICE_CONTAINER})"
            log_error "Port freigeben oder ONLYOFFICE_HOST_PORT setzen"
            return 1
        fi
    fi

    if _onlyoffice_container_exists; then
        log_info "Entferne bestehenden Container ${ONLYOFFICE_CONTAINER}..."
        docker stop "${ONLYOFFICE_CONTAINER}" >/dev/null 2>&1 || true
        docker rm "${ONLYOFFICE_CONTAINER}" >/dev/null 2>&1 || true
    fi

    log_info "Lade Document-Server-Image (${ONLYOFFICE_IMAGE})..."
    if ! docker pull "${ONLYOFFICE_IMAGE}"; then
        log_error "docker pull fehlgeschlagen: ${ONLYOFFICE_IMAGE}"
        log_error "Netzwerk, Registry-Zugang und Speicherplatz prüfen"
        if _onlyoffice_is_eurooffice_image; then
            log_error "Quelle: https://github.com/Euro-Office/DocumentServer"
        else
            log_error "Quelle: https://github.com/ONLYOFFICE/Docker-DocumentServer"
        fi
        return 1
    fi

    if _onlyoffice_is_eurooffice_image; then
        if ! _onlyoffice_seed_eurooffice_config; then
            log_error "Ohne Image-Config crasht der Document-Server-Entrypoint"
            return 1
        fi
        _onlyoffice_prepare_eurooffice_log_dirs
        _onlyoffice_prepare_eurooffice_data_dir
    fi

    log_info "Starte Document Server (JWT aktiv, Port ${ONLYOFFICE_HOST_PORT})..."
    local run_err cid
    run_err="$(mktemp)"

    if ! _onlyoffice_run_container "${run_err}"; then
        log_error "Document-Server-Container konnte nicht gestartet werden"
        log_error "$(cat "${run_err}")"
        rm -f "${run_err}"
        return 1
    fi
    cid="$(tr -d '\r\n' <"${run_err}")"
    rm -f "${run_err}"
    log_info "Container gestartet: ${cid:0:12}"

    # Erststart (DB/Fonts) kann 2–3 Minuten dauern
    log_info "Warte auf Document Server (bis 180s)..."
    local OO_READY=0
    local i
    local restarting_for=0
    local oo_status
    for i in $(seq 1 180); do
        oo_status=$(_onlyoffice_container_status)
        if [ "$oo_status" = "missing" ] || [ "$oo_status" = "exited" ] || [ "$oo_status" = "dead" ]; then
            log_error "Container ${ONLYOFFICE_CONTAINER} ist unerwartet gestoppt (Status ${oo_status})"
            _onlyoffice_dump_logs
            return 1
        fi
        if [ "$oo_status" = "restarting" ]; then
            restarting_for=$((restarting_for + 1))
            if [ "$restarting_for" -ge 20 ]; then
                log_error "Container ${ONLYOFFICE_CONTAINER} im Restart-Loop (oft leeres Config-Volume)"
                _onlyoffice_dump_logs
                return 1
            fi
        else
            restarting_for=0
        fi
        if curl -sf "http://127.0.0.1:${ONLYOFFICE_HOST_PORT}/healthcheck" 2>/dev/null | grep -qi true; then
            OO_READY=1
            log_success "Document Server ist bereit (${i}s)"
            break
        fi
        if [ $((i % 30)) -eq 0 ]; then
            log_info "Noch kein Ready-Signal (${i}/180s, Status ${oo_status})..."
        fi
        sleep 1
    done

    if [ "$OO_READY" -eq 0 ]; then
        log_error "Document Server antwortet nach 180s nicht auf /healthcheck"
        _onlyoffice_dump_logs
        return 1
    fi

    # Font-Index: Der Container-Entrypoint indexiert /usr/share/fonts/truetype/custom
    # beim Start selbst. documentserver-generate-allfonts.sh danach nicht live ausführen –
    # das überschreibt AllFonts.js/font_selection.bin während docservice läuft und
    # bricht Calibri→Carlito (Open-Fehler in Word/Excel/PowerPoint).
    # Zusätzliche TTFs später: ins Volume legen, dann `docker restart ${ONLYOFFICE_CONTAINER}`.

    log_info "JWT_SECRET = ONLYOFFICE_SECRET_KEY (für .env)"
    log_info "Proxy: /eurooffice (neu) und /onlyoffice (Legacy) → Port ${ONLYOFFICE_HOST_PORT}"
    log_success "Document Server installiert (${ONLYOFFICE_IMAGE})"
    return 0
}
