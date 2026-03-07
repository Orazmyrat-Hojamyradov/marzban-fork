#!/usr/bin/env bash
# =============================================================================
# Marzban Fork — Full Setup Script (0 to hero)
# Installs everything on a fresh Ubuntu server:
#   Docker, Marzban panel, Xray (xhttp inbound), nginx reverse proxy, SSL
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Orazmyrat-Hojamyradov/marzban-fork/main/setup.sh | bash
#   OR
#   bash setup.sh
# =============================================================================
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
ask()     { echo -e "${BOLD}$*${NC}"; }

# ── Constants ─────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/Orazmyrat-Hojamyradov/marzban-fork.git"
APP_NAME="marzban"
APP_DIR="/opt/${APP_NAME}"
DATA_DIR="/var/lib/${APP_NAME}"
NGINX_SITE="marzban-xhttp"
XHTTP_PORT=2027
PANEL_PORT=8000

# ── Root check ────────────────────────────────────────────────────────────────
[[ "$(id -u)" -ne 0 ]] && error "Run as root: sudo bash setup.sh"

# ── OS check ─────────────────────────────────────────────────────────────────
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    [[ "$ID" != "ubuntu" ]] && warn "This script is tested on Ubuntu. Proceeding anyway..."
else
    warn "/etc/os-release not found — proceeding anyway..."
    ID="unknown"
fi

# =============================================================================
# STEP 0 — Collect configuration
# =============================================================================
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}         Marzban Fork — Setup Wizard                  ${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Panel admin credentials
ask "Admin username for Marzban panel [admin]:"
read -r ADMIN_USER </dev/tty; ADMIN_USER="${ADMIN_USER:-admin}"

ask "Admin password for Marzban panel [admin]:"
read -r ADMIN_PASS </dev/tty; ADMIN_PASS="${ADMIN_PASS:-admin}"

# CDN domain (Bunny CDN pull zone domain)
ask "Bunny CDN pull zone domain (e.g. maestro969.b-cdn.net) — leave empty to skip:"
read -r CDN_DOMAIN </dev/tty

# Subscription URL prefix
if [[ -n "$CDN_DOMAIN" ]]; then
    DEFAULT_SUB_PREFIX="https://${CDN_DOMAIN}"
else
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
    DEFAULT_SUB_PREFIX="http://${SERVER_IP}:${PANEL_PORT}"
fi
ask "Subscription URL prefix [${DEFAULT_SUB_PREFIX}]:"
read -r SUB_PREFIX </dev/tty; SUB_PREFIX="${SUB_PREFIX:-$DEFAULT_SUB_PREFIX}"

# nginx port
ask "nginx listen port — 80 (HTTP, no SSL) or 443 (HTTPS with SSL) [80]:"
read -r NGINX_PORT </dev/tty; NGINX_PORT="${NGINX_PORT:-80}"

# SSL setup (only if port 443)
DOMAIN=""
CERT_PATH=""
KEY_PATH=""
USE_SSL=false
SSL_CHOICE=""

if [[ "$NGINX_PORT" == "443" ]]; then
    USE_SSL=true
    ask "Domain name pointing to this server (needed for SSL cert):"
    read -r DOMAIN </dev/tty
    [[ -z "$DOMAIN" ]] && error "Domain is required for port 443 (SSL)"

    ask "How to get SSL certificate?
  1) ZeroSSL via acme.sh (domain must point to this server)
  2) I already have a cert (provide paths)
Choice [1]:"
    read -r SSL_CHOICE </dev/tty; SSL_CHOICE="${SSL_CHOICE:-1}"

    if [[ "$SSL_CHOICE" == "2" ]]; then
        ask "Full path to certificate file (.pem / .cer / .crt):"
        read -r CERT_PATH </dev/tty
        ask "Full path to private key file (.key):"
        read -r KEY_PATH </dev/tty
        [[ ! -f "$CERT_PATH" ]] && error "Certificate file not found: $CERT_PATH"
        [[ ! -f "$KEY_PATH"  ]] && error "Key file not found: $KEY_PATH"
    fi
fi

# HWID device limiting
ask "Enable HWID device limiting? (for Happ app) [y/N]:"
read -r HWID_CHOICE </dev/tty
HWID_ENABLED=false
HWID_LIMIT=3
if [[ "${HWID_CHOICE,,}" == "y" ]]; then
    HWID_ENABLED=true
    ask "Max devices per user [3]:"
    read -r HWID_LIMIT </dev/tty; HWID_LIMIT="${HWID_LIMIT:-3}"
fi

echo ""
info "Configuration summary:"
echo "  App directory      : $APP_DIR"
echo "  Data directory     : $DATA_DIR"
echo "  Panel port         : $PANEL_PORT"
echo "  Xray xhttp port    : $XHTTP_PORT"
echo "  nginx port         : $NGINX_PORT"
echo "  SSL                : $USE_SSL ${DOMAIN:+($DOMAIN)}"
echo "  CDN domain         : ${CDN_DOMAIN:-none}"
echo "  Sub URL prefix     : $SUB_PREFIX"
echo "  Admin user         : $ADMIN_USER"
echo "  HWID limiting      : $HWID_ENABLED (limit: $HWID_LIMIT)"
echo ""
ask "Proceed? [Y/n]:"
read -r CONFIRM </dev/tty
[[ "${CONFIRM,,}" == "n" ]] && echo "Aborted." && exit 0

# =============================================================================
# STEP 1 — System packages
# =============================================================================
echo ""
info "━━ STEP 1: System packages ━━"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl git unzip wget python3 python3-pip \
    ca-certificates gnupg lsb-release
success "Base packages installed"

# =============================================================================
# STEP 2 — Docker
# =============================================================================
echo ""
info "━━ STEP 2: Docker ━━"

if command -v docker &>/dev/null; then
    success "Docker already installed: $(docker --version)"
else
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    success "Docker installed: $(docker --version)"
fi

if docker compose version &>/dev/null; then
    COMPOSE="docker compose"
elif docker-compose version &>/dev/null; then
    COMPOSE="docker-compose"
else
    info "Installing Docker Compose plugin..."
    apt-get install -y -qq docker-compose-plugin
    COMPOSE="docker compose"
fi
COMPOSE_VER=$($COMPOSE version --short 2>/dev/null || $COMPOSE version 2>/dev/null || echo "unknown")
success "Docker Compose available: $COMPOSE_VER"

# =============================================================================
# STEP 3 — Clone / update repo
# =============================================================================
echo ""
info "━━ STEP 3: Repository ━━"

if [[ -d "$APP_DIR/.git" ]]; then
    info "Repo exists — pulling latest..."
    git -C "$APP_DIR" config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" reset --hard origin/main
    success "Repo updated"
else
    info "Cloning repo to $APP_DIR..."
    mkdir -p "$(dirname "$APP_DIR")"
    git clone "$REPO_URL" "$APP_DIR"
    success "Repo cloned"
fi

# =============================================================================
# STEP 4 — Data directory and xray_config.json
# =============================================================================
echo ""
info "━━ STEP 4: Xray config ━━"

mkdir -p "$DATA_DIR"

cat > "$DATA_DIR/xray_config.json" << 'XRAYEOF'
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "VLESS-XHTTP-NOTLS",
      "listen": "0.0.0.0",
      "port": 2027,
      "protocol": "vless",
      "settings": {
        "clients": [],
        "decryption": "none",
        "fallbacks": []
      },
      "sniffing": {
        "destOverride": ["http", "tls", "quic", "fakedns"],
        "enabled": true
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "none",
        "xhttpSettings": {
          "headers": {},
          "host": "",
          "mode": "packet-up",
          "noGRPCHeader": true,
          "noSSEHeader": false,
          "path": "/",
          "scMaxBufferedPosts": 30,
          "scMaxEachPostBytes": "1000000",
          "xPaddingBytes": "100-1000"
        }
      }
    },
    {
      "tag": "SHADOWSOCKS",
      "listen": "0.0.0.0",
      "port": 888,
      "protocol": "shadowsocks",
      "settings": {
        "method": "aes-256-gcm",
        "password": "changeme",
        "network": "tcp,udp"
      }
    }
  ],
  "outbounds": [
    {"protocol": "freedom", "tag": "DIRECT"},
    {"protocol": "blackhole", "tag": "BLOCK"}
  ],
  "routing": {
    "rules": [
      {"ip": ["geoip:private"],       "outboundTag": "BLOCK", "type": "field"},
      {"domain": ["geosite:private"], "outboundTag": "BLOCK", "type": "field"},
      {"protocol": ["bittorrent"],    "outboundTag": "BLOCK", "type": "field"}
    ]
  }
}
XRAYEOF

success "xray_config.json written to $DATA_DIR"

# =============================================================================
# STEP 5 — .env file (no hardcoded admin — created via CLI later)
# =============================================================================
echo ""
info "━━ STEP 5: Environment file ━━"

cat > "$APP_DIR/.env" << ENVEOF
UVICORN_HOST = "0.0.0.0"
UVICORN_PORT = ${PANEL_PORT}

XRAY_JSON = "${DATA_DIR}/xray_config.json"
XRAY_EXECUTABLE_PATH = "/usr/local/bin/xray"
XRAY_ASSETS_PATH = "/usr/local/share/xray"

XRAY_SUBSCRIPTION_URL_PREFIX = "${SUB_PREFIX}"
XRAY_SUBSCRIPTION_PATH = "sub"

SQLALCHEMY_DATABASE_URL = "sqlite:////${DATA_DIR}/db.sqlite3"

HWID_ENABLED = ${HWID_ENABLED}
HWID_FALLBACK_LIMIT = ${HWID_LIMIT}

SUB_UPDATE_INTERVAL = "2"

DOCS = false
DEBUG = false
ENVEOF

success ".env written to $APP_DIR/.env"

# =============================================================================
# STEP 6 — SSL certificate (if port 443)
# =============================================================================
if [[ "$USE_SSL" == "true" && "$SSL_CHOICE" == "1" ]]; then
    echo ""
    info "━━ STEP 6: SSL certificate (ZeroSSL) ━━"

    mkdir -p /etc/ssl/marzban
    CERT_PATH="/etc/ssl/marzban/fullchain.pem"
    KEY_PATH="/etc/ssl/marzban/privkey.pem"

    # acme.sh --standalone needs port 80 free — stop nginx if running
    if systemctl is-active nginx &>/dev/null; then
        info "Stopping nginx temporarily (acme.sh needs port 80)..."
        systemctl stop nginx
    fi

    # Install acme.sh if missing
    if [[ ! -f "$HOME/.acme.sh/acme.sh" ]]; then
        info "Installing acme.sh..."
        curl -fsSL https://get.acme.sh | sh
    fi
    ACME="$HOME/.acme.sh/acme.sh"
    [[ ! -f "$ACME" ]] && error "acme.sh installation failed"

    info "Registering ZeroSSL account (ssl@${DOMAIN})..."
    "$ACME" --register-account -m "ssl@${DOMAIN}" --server zerossl

    info "Issuing certificate for $DOMAIN via ZeroSSL..."
    if "$ACME" --issue --standalone -d "$DOMAIN" --server zerossl; then
        info "New certificate issued"
    elif "$ACME" --issue --standalone -d "$DOMAIN" --server zerossl --force; then
        info "Certificate renewed (forced)"
    else
        warn "acme.sh --issue returned error — checking if cert already exists..."
    fi

    info "Installing certificate to $CERT_PATH..."
    if "$ACME" --install-cert -d "$DOMAIN" \
        --fullchain-file "$CERT_PATH" \
        --key-file "$KEY_PATH" \
        --reloadcmd "systemctl reload nginx 2>/dev/null || true"; then
        success "Certificate installed: $CERT_PATH"
    else
        [[ -f "$CERT_PATH" ]] && success "Certificate already at $CERT_PATH" \
            || error "Failed to obtain or install SSL certificate for $DOMAIN"
    fi
elif [[ "$USE_SSL" == "true" && "$SSL_CHOICE" == "2" ]]; then
    echo ""
    info "━━ STEP 6: SSL certificate (provided) ━━"
    success "Using provided cert: $CERT_PATH"
else
    echo ""
    info "━━ STEP 6: SSL — skipped (HTTP mode) ━━"
fi

# =============================================================================
# STEP 7 — Build and start Docker container
# =============================================================================
echo ""
info "━━ STEP 7: Docker build and start ━━"

cd "$APP_DIR"

# Stop existing container in this project if running
RUNNING=$($COMPOSE ps -q 2>/dev/null || true)
if [[ -n "$RUNNING" ]]; then
    info "Stopping existing container..."
    $COMPOSE down
fi

# Free up required ports (old installs, other containers, stale processes)
free_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
    if [[ -n "$pids" ]]; then
        for pid in $pids; do
            local pname
            pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
            info "Port $port in use by $pname (PID $pid) — stopping..."
            if [[ "$pname" == "docker-proxy" ]]; then
                # Find and stop the docker container using this port
                local cid
                cid=$(docker ps --format '{{.ID}} {{.Ports}}' 2>/dev/null | grep ":${port}->" | awk '{print $1}' || true)
                if [[ -n "$cid" ]]; then
                    info "Stopping container $cid (holds port $port)..."
                    docker stop "$cid" 2>/dev/null || true
                fi
            elif [[ "$pname" == "nginx" ]]; then
                systemctl stop nginx 2>/dev/null || true
            else
                kill "$pid" 2>/dev/null || true
            fi
        done
        sleep 1
    fi
}

free_port "$PANEL_PORT"
free_port "$XHTTP_PORT"

info "Building Docker image (this takes a few minutes on first run)..."
$COMPOSE build

info "Starting container..."
$COMPOSE up -d

# Wait for Marzban to start
info "Waiting for Marzban to start..."
PANEL_UP=false
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${PANEL_PORT}/api/core" &>/dev/null; then
        PANEL_UP=true
        break
    fi
    sleep 2
done

if [[ "$PANEL_UP" == "true" ]]; then
    success "Marzban panel is up"
else
    warn "Panel may still be starting — check logs: marzban logs"
fi

XRAY_VERSION=$($COMPOSE exec -T marzban /usr/local/bin/xray version 2>/dev/null | grep -o 'Xray [0-9.]*' | awk '{print $2}' || echo "unknown")
success "Container running | Xray version: ${XRAY_VERSION:-unknown}"

# =============================================================================
# STEP 8 — Create admin via CLI (not hardcoded in .env)
# =============================================================================
echo ""
info "━━ STEP 8: Create admin user ━━"

info "Creating sudo admin: $ADMIN_USER"
if $COMPOSE exec -T \
    -e MARZBAN_ADMIN_PASSWORD="$ADMIN_PASS" \
    marzban marzban-cli admin create -u "$ADMIN_USER" --sudo 2>/dev/null; then
    success "Admin '$ADMIN_USER' created via CLI"
else
    warn "Admin creation returned error (may already exist — that's OK)"
fi

# =============================================================================
# STEP 9 — Install systemwide 'marzban' command
# =============================================================================
echo ""
info "━━ STEP 9: Install marzban command ━━"

if curl -sSL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh \
    | install -m 755 /dev/stdin /usr/local/bin/marzban; then
    success "Systemwide 'marzban' command installed"
else
    warn "Failed to install marzban command — you can install it later with:"
    warn "  curl -sSL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh | install -m 755 /dev/stdin /usr/local/bin/marzban"
fi
info "  marzban up / down / restart / logs / status"
info "  marzban cli admin list"
info "  marzban cli admin create -u USERNAME --sudo"
info "  marzban edit-env"

# =============================================================================
# STEP 10 — nginx
# =============================================================================
echo ""
info "━━ STEP 10: nginx ━━"

if ! command -v nginx &>/dev/null; then
    info "Installing nginx..."
    apt-get install -y -qq nginx
    success "nginx installed"
else
    success "nginx already installed: $(nginx -v 2>&1)"
fi

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Build nginx config
NGINX_CONF="/etc/nginx/sites-available/${NGINX_SITE}"

if [[ "$USE_SSL" == "true" ]]; then
    # Port 80 MUST serve xhttp directly (Bunny CDN origin connects here)
    # Port 443 serves xhttp over SSL (for direct connections)
    cat > "$NGINX_CONF" << NGINXEOF
# Port 80 — Bunny CDN origin (NO redirect — CDN connects here via HTTP)
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:${XHTTP_PORT};
        proxy_http_version 1.1;
        proxy_buffering         off;
        proxy_request_buffering off;
        proxy_read_timeout    300s;
        proxy_send_timeout    300s;
        proxy_connect_timeout  10s;
        chunked_transfer_encoding on;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# Port 443 — direct SSL access
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     ${CERT_PATH};
    ssl_certificate_key ${KEY_PATH};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    location / {
        proxy_pass http://127.0.0.1:${XHTTP_PORT};
        proxy_http_version 1.1;
        proxy_buffering         off;
        proxy_request_buffering off;
        proxy_read_timeout    300s;
        proxy_send_timeout    300s;
        proxy_connect_timeout  10s;
        chunked_transfer_encoding on;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF
else
    cat > "$NGINX_CONF" << NGINXEOF
server {
    listen ${NGINX_PORT};
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:${XHTTP_PORT};
        proxy_http_version 1.1;
        proxy_buffering         off;
        proxy_request_buffering off;
        proxy_read_timeout    300s;
        proxy_send_timeout    300s;
        proxy_connect_timeout  10s;
        chunked_transfer_encoding on;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF
fi

ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/${NGINX_SITE}"

nginx -t || error "nginx config test failed — check $NGINX_CONF"
systemctl enable nginx
systemctl restart nginx
success "nginx configured and running on port $NGINX_PORT"

# =============================================================================
# STEP 11 — Firewall
# =============================================================================
echo ""
info "━━ STEP 11: Firewall ━━"

if command -v ufw &>/dev/null && ufw status &>/dev/null; then
    ufw allow 22/tcp   2>/dev/null || true
    ufw allow "${PANEL_PORT}/tcp" 2>/dev/null || true
    ufw allow "${NGINX_PORT}/tcp" 2>/dev/null || true
    if [[ "$USE_SSL" == "true" ]]; then
        ufw allow 80/tcp 2>/dev/null || true
    fi
    success "UFW rules added (SSH, panel, nginx)"
else
    info "UFW not active — skipping firewall rules"
    info "Make sure ports 22, $PANEL_PORT, and $NGINX_PORT are open"
fi

# =============================================================================
# STEP 12 — Configure Marzban hosts (VLESS-XHTTP-NOTLS)
# =============================================================================
echo ""
info "━━ STEP 12: Marzban host config ━━"

if [[ -n "$CDN_DOMAIN" ]]; then
    # Get API token
    TOKEN=""
    for i in $(seq 1 15); do
        TOKEN=$(curl -sf -X POST "http://127.0.0.1:${PANEL_PORT}/api/admin/token" \
            -d "username=${ADMIN_USER}&password=${ADMIN_PASS}" 2>/dev/null | \
            python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null) || true
        [[ -n "$TOKEN" ]] && break
        sleep 2
    done

    if [[ -n "${TOKEN:-}" ]]; then
        curl -sf -X PUT "http://127.0.0.1:${PANEL_PORT}/api/hosts" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
              \"VLESS-XHTTP-NOTLS\": [{
                \"remark\": \"Marz ({USERNAME}) [VLESS - xhttp]\",
                \"address\": \"${CDN_DOMAIN}\",
                \"port\": 443,
                \"sni\": \"${CDN_DOMAIN}\",
                \"host\": \"${CDN_DOMAIN}\",
                \"path\": \"/\",
                \"security\": \"tls\",
                \"alpn\": \"h2\",
                \"fingerprint\": \"chrome\",
                \"allowinsecure\": false,
                \"is_disabled\": false,
                \"mux_enable\": false,
                \"fragment_setting\": null,
                \"noise_setting\": null,
                \"random_user_agent\": false,
                \"use_sni_as_host\": false
              }]
            }" > /dev/null
        success "Host config set: address=$CDN_DOMAIN, alpn=h2, security=tls"
    else
        warn "Could not get API token — set host config manually in the panel"
    fi
else
    warn "No CDN domain provided — configure VLESS-XHTTP-NOTLS host manually in the panel"
fi

# =============================================================================
# Done — Print summary
# =============================================================================
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}           Setup complete!                             ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Panel URL${NC}      : http://${SERVER_IP}:${PANEL_PORT}/dashboard/"
echo -e "  ${BOLD}Username${NC}       : ${ADMIN_USER}"
echo -e "  ${BOLD}Password${NC}       : ${ADMIN_PASS}"
echo ""
echo -e "  ${BOLD}xhttp inbound${NC}  : port ${XHTTP_PORT} (inside Docker)"
echo -e "  ${BOLD}nginx proxy${NC}    : port ${NGINX_PORT} -> ${XHTTP_PORT}"
if [[ -n "$CDN_DOMAIN" ]]; then
echo -e "  ${BOLD}CDN origin${NC}     : set Bunny CDN pull zone origin to http://${SERVER_IP}"
echo -e "  ${BOLD}CDN timeout${NC}    : set Origin Response Timeout to 60s in Bunny CDN"
fi
echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "    marzban logs       — view panel logs"
echo -e "    marzban restart    — restart panel"
echo -e "    marzban status     — check panel status"
echo -e "    marzban cli        — run marzban CLI"
echo -e "    marzban edit-env   — edit .env file"
echo -e "    marzban update     — update to latest version"
echo ""
if [[ "$ADMIN_PASS" == "admin" ]]; then
    warn "Default password detected — change it immediately in the panel!"
fi
if [[ -n "$CDN_DOMAIN" ]]; then
    echo -e "  ${YELLOW}Bunny CDN checklist:${NC}"
    echo -e "    - Pull zone origin URL : http://${SERVER_IP}"
    echo -e "    - Origin Response Timeout : 60 seconds"
    echo -e "    - Disable Force HTTPS redirect (or ensure clients use h2)"
    echo -e "    - Disable TM PoP if Turkmenistan users have issues"
fi
echo ""
