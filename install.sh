#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/Orazmyrat-Hojamyradov/marzban-fork.git"
SCRIPT_URL="https://github.com/Orazmyrat-Hojamyradov/marzban-fork/raw/main/install.sh"
APP_NAME="marzban"
INSTALL_DIR="/opt"
APP_DIR="$INSTALL_DIR/$APP_NAME"
DATA_DIR="/var/lib/$APP_NAME"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"
ENV_FILE="$APP_DIR/.env"
LAST_XRAY_CORES=10

colorized_echo() {
    local color=$1
    local text=$2
    case $color in
        "red")     printf "\e[91m${text}\e[0m\n" ;;
        "green")   printf "\e[92m${text}\e[0m\n" ;;
        "yellow")  printf "\e[93m${text}\e[0m\n" ;;
        "blue")    printf "\e[94m${text}\e[0m\n" ;;
        "magenta") printf "\e[95m${text}\e[0m\n" ;;
        "cyan")    printf "\e[96m${text}\e[0m\n" ;;
        *)         echo "${text}" ;;
    esac
}

check_running_as_root() {
    if [ "$(id -u)" != "0" ]; then
        colorized_echo red "This command must be run as root."
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/lsb-release ]; then
        OS=$(lsb_release -si)
    elif [ -f /etc/os-release ]; then
        OS=$(awk -F= '/^NAME/{print $2}' /etc/os-release | tr -d '"')
    elif [ -f /etc/redhat-release ]; then
        OS=$(cat /etc/redhat-release | awk '{print $1}')
    elif [ -f /etc/arch-release ]; then
        OS="Arch"
    else
        colorized_echo red "Unsupported operating system"
        exit 1
    fi
}

detect_and_update_package_manager() {
    colorized_echo blue "Updating package manager"
    if [[ "$OS" == "Ubuntu"* ]] || [[ "$OS" == "Debian"* ]]; then
        PKG_MANAGER="apt-get"
        $PKG_MANAGER update
    elif [[ "$OS" == "CentOS"* ]] || [[ "$OS" == "AlmaLinux"* ]]; then
        PKG_MANAGER="yum"
        $PKG_MANAGER update -y
        $PKG_MANAGER install -y epel-release
    elif [ "$OS" == "Fedora"* ]; then
        PKG_MANAGER="dnf"
        $PKG_MANAGER update
    elif [ "$OS" == "Arch" ]; then
        PKG_MANAGER="pacman"
        $PKG_MANAGER -Sy
    elif [[ "$OS" == "openSUSE"* ]]; then
        PKG_MANAGER="zypper"
        $PKG_MANAGER refresh
    else
        colorized_echo red "Unsupported operating system"
        exit 1
    fi
}

install_package() {
    if [ -z "$PKG_MANAGER" ]; then
        detect_and_update_package_manager
    fi
    PACKAGE=$1
    colorized_echo blue "Installing $PACKAGE"
    if [[ "$OS" == "Ubuntu"* ]] || [[ "$OS" == "Debian"* ]]; then
        $PKG_MANAGER -y install "$PACKAGE"
    elif [[ "$OS" == "CentOS"* ]] || [[ "$OS" == "AlmaLinux"* ]]; then
        $PKG_MANAGER install -y "$PACKAGE"
    elif [ "$OS" == "Fedora"* ]; then
        $PKG_MANAGER install -y "$PACKAGE"
    elif [ "$OS" == "Arch" ]; then
        $PKG_MANAGER -S --noconfirm "$PACKAGE"
    else
        colorized_echo red "Unsupported operating system"
        exit 1
    fi
}

install_docker() {
    colorized_echo blue "Installing Docker"
    curl -fsSL https://get.docker.com | sh
    colorized_echo green "Docker installed successfully"
}

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE='docker compose'
    elif docker-compose version >/dev/null 2>&1; then
        COMPOSE='docker-compose'
    else
        colorized_echo red "docker compose not found"
        exit 1
    fi
}

identify_the_operating_system_and_architecture() {
    if [[ "$(uname)" == 'Linux' ]]; then
        case "$(uname -m)" in
            'i386' | 'i686')       ARCH='32' ;;
            'amd64' | 'x86_64')    ARCH='64' ;;
            'armv5tel')            ARCH='arm32-v5' ;;
            'armv6l')
                ARCH='arm32-v6'
                grep Features /proc/cpuinfo | grep -qw 'vfp' || ARCH='arm32-v5'
                ;;
            'armv7' | 'armv7l')
                ARCH='arm32-v7a'
                grep Features /proc/cpuinfo | grep -qw 'vfp' || ARCH='arm32-v5'
                ;;
            'armv8' | 'aarch64')   ARCH='arm64-v8a' ;;
            'mips')                ARCH='mips32' ;;
            'mipsle')              ARCH='mips32le' ;;
            'mips64')
                ARCH='mips64'
                lscpu | grep -q "Little Endian" && ARCH='mips64le'
                ;;
            'mips64le')            ARCH='mips64le' ;;
            'ppc64')               ARCH='ppc64' ;;
            'ppc64le')             ARCH='ppc64le' ;;
            'riscv64')             ARCH='riscv64' ;;
            's390x')               ARCH='s390x' ;;
            *)
                echo "error: The architecture is not supported."
                exit 1
                ;;
        esac
    else
        echo "error: This operating system is not supported."
        exit 1
    fi
}

is_marzban_installed() {
    [ -d "$APP_DIR" ]
}

is_marzban_up() {
    if [ -z "$($COMPOSE -f $COMPOSE_FILE ps -q -a 2>/dev/null)" ]; then
        return 1
    else
        return 0
    fi
}

# ─── Install / Uninstall ────────────────────────────────────────────────────

install_marzban_script() {
    colorized_echo blue "Installing marzban script"
    curl -sSL "$SCRIPT_URL" | install -m 755 /dev/stdin /usr/local/bin/marzban
    colorized_echo green "marzban script installed successfully"

    # Also install marzban-cli wrapper
    cat > /usr/local/bin/marzban-cli << 'CLIEOF'
#!/bin/bash
cd /opt/marzban
if docker compose version >/dev/null 2>&1; then
    docker compose exec marzban marzban-cli "$@"
else
    docker-compose exec marzban marzban-cli "$@"
fi
CLIEOF
    chmod +x /usr/local/bin/marzban-cli
    colorized_echo green "marzban-cli script installed successfully"
}

install_marzban() {
    colorized_echo blue "Cloning Marzban Fork repository"

    if ! command -v git >/dev/null 2>&1; then
        detect_os
        install_package git
    fi

    mkdir -p "$DATA_DIR"
    mkdir -p "$APP_DIR"

    if [ -d "$APP_DIR/.git" ]; then
        colorized_echo yellow "Repository already exists, pulling latest changes"
        git -C "$APP_DIR" pull
    else
        git clone "$REPO_URL" "$APP_DIR"
    fi

    # Create .env if not present
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$APP_DIR/.env.example" ]; then
            cp "$APP_DIR/.env.example" "$ENV_FILE"
        else
            cat > "$ENV_FILE" << 'ENVEOF'
UVICORN_HOST = "0.0.0.0"
UVICORN_PORT = 8000

XRAY_EXECUTABLE_PATH = "/usr/local/share/xray/xray"
XRAY_ASSETS_PATH = "/usr/local/share/xray"

SQLALCHEMY_DATABASE_URL = "sqlite:////var/lib/marzban/db.sqlite3"

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 1440
DOCS = false
DEBUG = false
ENVEOF
        fi
        colorized_echo green ".env file created at $ENV_FILE"
    fi

    colorized_echo blue "Building Docker image (this may take a few minutes on first run)"
    $COMPOSE -f "$COMPOSE_FILE" build

    colorized_echo green "Marzban Fork files ready"
}

update_marzban_script() {
    colorized_echo blue "Updating marzban script"
    curl -sSL "$SCRIPT_URL" | install -m 755 /dev/stdin /usr/local/bin/marzban
    colorized_echo green "marzban script updated successfully"
}

update_marzban() {
    colorized_echo blue "Pulling latest code from repository"
    git -C "$APP_DIR" pull
    colorized_echo blue "Rebuilding Docker image"
    $COMPOSE -f "$COMPOSE_FILE" build
}

uninstall_marzban_script() {
    if [ -f "/usr/local/bin/marzban" ]; then
        colorized_echo yellow "Removing marzban script"
        rm "/usr/local/bin/marzban"
    fi
    if [ -f "/usr/local/bin/marzban-cli" ]; then
        colorized_echo yellow "Removing marzban-cli script"
        rm "/usr/local/bin/marzban-cli"
    fi
}

uninstall_marzban() {
    if [ -d "$APP_DIR" ]; then
        colorized_echo yellow "Removing directory: $APP_DIR"
        rm -rf "$APP_DIR"
    fi
}

uninstall_marzban_docker_images() {
    images=$(docker images | grep marzban | awk '{print $3}')
    if [ -n "$images" ]; then
        colorized_echo yellow "Removing Docker images of Marzban"
        for image in $images; do
            if docker rmi "$image" >/dev/null 2>&1; then
                colorized_echo yellow "Image $image removed"
            fi
        done
    fi
}

uninstall_marzban_data_files() {
    if [ -d "$DATA_DIR" ]; then
        colorized_echo yellow "Removing directory: $DATA_DIR"
        rm -rf "$DATA_DIR"
    fi
}

# ─── Service control ────────────────────────────────────────────────────────

up_marzban() {
    $COMPOSE -f "$COMPOSE_FILE" -p "$APP_NAME" up -d --remove-orphans
}

down_marzban() {
    $COMPOSE -f "$COMPOSE_FILE" -p "$APP_NAME" down
}

show_marzban_logs() {
    $COMPOSE -f "$COMPOSE_FILE" -p "$APP_NAME" logs
}

follow_marzban_logs() {
    $COMPOSE -f "$COMPOSE_FILE" -p "$APP_NAME" logs -f
}

marzban_cli() {
    $COMPOSE -f "$COMPOSE_FILE" -p "$APP_NAME" exec -e CLI_PROG_NAME="marzban cli" marzban marzban-cli "$@"
}

# ─── Commands ───────────────────────────────────────────────────────────────

install_command() {
    check_running_as_root

    if is_marzban_installed; then
        colorized_echo red "Marzban is already installed at $APP_DIR"
        read -p "Do you want to override the previous installation? (y/n) "
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            colorized_echo red "Aborted installation"
            exit 1
        fi
    fi

    detect_os
    if ! command -v curl >/dev/null 2>&1; then install_package curl; fi
    if ! command -v git  >/dev/null 2>&1; then install_package git;  fi
    if ! command -v docker >/dev/null 2>&1; then install_docker; fi
    detect_compose
    install_marzban_script
    install_marzban
    up_marzban
    follow_marzban_logs
}

up_command() {
    help() {
        colorized_echo red "Usage: marzban up [options]"
        echo ""
        echo "OPTIONS:"
        echo "  -h, --help        display this help message"
        echo "  -n, --no-logs     do not follow logs after starting"
    }
    local no_logs=false
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            -n|--no-logs) no_logs=true ;;
            -h|--help) help; exit 0 ;;
            *) echo "Error: Invalid option: $1" >&2; help; exit 0 ;;
        esac
        shift
    done

    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    if is_marzban_up; then colorized_echo red "Marzban's already up"; exit 1; fi
    up_marzban
    if [ "$no_logs" = false ]; then follow_marzban_logs; fi
}

down_command() {
    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    if ! is_marzban_up; then colorized_echo red "Marzban's already down"; exit 1; fi
    down_marzban
}

restart_command() {
    help() {
        colorized_echo red "Usage: marzban restart [options]"
        echo ""
        echo "OPTIONS:"
        echo "  -h, --help        display this help message"
        echo "  -n, --no-logs     do not follow logs after restarting"
    }
    local no_logs=false
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            -n|--no-logs) no_logs=true ;;
            -h|--help) help; exit 0 ;;
            *) echo "Error: Invalid option: $1" >&2; help; exit 0 ;;
        esac
        shift
    done

    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    down_marzban
    up_marzban
    if [ "$no_logs" = false ]; then follow_marzban_logs; fi
    colorized_echo green "Marzban successfully restarted!"
}

status_command() {
    if ! is_marzban_installed; then
        echo -n "Status: "; colorized_echo red "Not Installed"; exit 1
    fi
    detect_compose
    if ! is_marzban_up; then
        echo -n "Status: "; colorized_echo blue "Down"; exit 1
    fi
    echo -n "Status: "; colorized_echo green "Up"
    json=$($COMPOSE -f "$COMPOSE_FILE" ps -a --format=json)
    services=$(echo "$json" | grep -oP '"Service":"[^"]*"' | cut -d'"' -f4)
    states=$(echo "$json"   | grep -oP '"State":"[^"]*"'   | cut -d'"' -f4)
    paste <(echo "$services") <(echo "$states") | while IFS=$'\t' read -r svc state; do
        echo -n "- $svc: "
        if [ "$state" == "running" ]; then colorized_echo green "$state"
        else colorized_echo red "$state"; fi
    done
}

logs_command() {
    help() {
        colorized_echo red "Usage: marzban logs [options]"
        echo ""
        echo "OPTIONS:"
        echo "  -h, --help        display this help message"
        echo "  -n, --no-follow   do not follow logs"
    }
    local no_follow=false
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            -n|--no-follow) no_follow=true ;;
            -h|--help) help; exit 0 ;;
            *) echo "Error: Invalid option: $1" >&2; help; exit 0 ;;
        esac
        shift
    done

    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    if ! is_marzban_up; then colorized_echo red "Marzban is not up."; exit 1; fi
    if [ "$no_follow" = true ]; then show_marzban_logs; else follow_marzban_logs; fi
}

cli_command() {
    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    if ! is_marzban_up; then colorized_echo red "Marzban is not up."; exit 1; fi
    marzban_cli "$@"
}

update_command() {
    check_running_as_root
    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    detect_compose
    update_marzban_script
    colorized_echo blue "Pulling latest version"
    update_marzban
    colorized_echo blue "Restarting Marzban's services"
    down_marzban
    up_marzban
    colorized_echo blue "Marzban updated successfully"
}

uninstall_command() {
    check_running_as_root
    if ! is_marzban_installed; then colorized_echo red "Marzban's not installed!"; exit 1; fi
    read -p "Do you really want to uninstall Marzban? (y/n) "
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then colorized_echo red "Aborted"; exit 1; fi
    detect_compose
    if is_marzban_up; then down_marzban; fi
    uninstall_marzban_script
    uninstall_marzban
    uninstall_marzban_docker_images
    read -p "Do you want to remove Marzban's data files too ($DATA_DIR)? (y/n) "
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        uninstall_marzban_data_files
    fi
    colorized_echo green "Marzban uninstalled successfully"
}

check_editor() {
    if [ -z "$EDITOR" ]; then
        if command -v nano >/dev/null 2>&1; then
            EDITOR="nano"
        elif command -v vi >/dev/null 2>&1; then
            EDITOR="vi"
        else
            detect_os; install_package nano; EDITOR="nano"
        fi
    fi
}

edit_command() {
    detect_os; check_editor
    if [ -f "$COMPOSE_FILE" ]; then $EDITOR "$COMPOSE_FILE"
    else colorized_echo red "Compose file not found at $COMPOSE_FILE"; exit 1; fi
}

edit_env_command() {
    detect_os; check_editor
    if [ -f "$ENV_FILE" ]; then $EDITOR "$ENV_FILE"
    else colorized_echo red "Environment file not found at $ENV_FILE"; exit 1; fi
}

# ─── Backup ─────────────────────────────────────────────────────────────────

send_backup_to_telegram() {
    if [ -f "$ENV_FILE" ]; then
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] && export "$key"="$value"
        done < "$ENV_FILE"
    else
        colorized_echo red "Environment file (.env) not found."; exit 1
    fi

    [ "$BACKUP_SERVICE_ENABLED" != "true" ] && {
        colorized_echo yellow "Backup service is not enabled. Skipping Telegram upload."
        return
    }

    local server_ip=$(curl -s ifconfig.me || echo "Unknown IP")
    local latest_backup=$(ls -t "$APP_DIR/backup" | head -n 1)
    local backup_path="$APP_DIR/backup/$latest_backup"
    [ ! -f "$backup_path" ] && { colorized_echo red "No backups found to send."; return; }

    local backup_size=$(du -m "$backup_path" | cut -f1)
    local split_dir="/tmp/marzban_backup_split"
    mkdir -p "$split_dir"

    if [ "$backup_size" -gt 49 ]; then
        colorized_echo yellow "Backup is larger than 49MB. Splitting the archive..."
        split -b 49M "$backup_path" "$split_dir/part_"
    else
        cp "$backup_path" "$split_dir/part_aa"
    fi

    local backup_time=$(date "+%Y-%m-%d %H:%M:%S %Z")
    for part in "$split_dir"/*; do
        local part_name=$(basename "$part")
        local custom_filename="backup_${part_name}.tar.gz"
        local caption="📦 *Backup Information*\n🌐 *Server IP*: \`${server_ip}\`\n📁 *Backup File*: \`${custom_filename}\`\n⏰ *Backup Time*: \`${backup_time}\`"
        curl -s -F chat_id="$BACKUP_TELEGRAM_CHAT_ID" \
            -F document=@"$part;filename=$custom_filename" \
            -F caption="$(echo -e "$caption" | sed 's/-/\\-/g;s/\./\\./g;s/_/\\_/g')" \
            -F parse_mode="MarkdownV2" \
            "https://api.telegram.org/bot$BACKUP_TELEGRAM_BOT_KEY/sendDocument" >/dev/null 2>&1 \
        && colorized_echo green "Backup part $custom_filename successfully sent to Telegram." \
        || colorized_echo red "Failed to send backup part $custom_filename to Telegram."
    done
    rm -rf "$split_dir"
}

send_backup_error_to_telegram() {
    local error_messages=$1
    local log_file=$2
    local server_ip=$(curl -s ifconfig.me || echo "Unknown IP")
    local error_time=$(date "+%Y-%m-%d %H:%M:%S %Z")
    local message="⚠️ *Backup Error Notification*\n🌐 *Server IP*: \`${server_ip}\`\n❌ *Errors*:\n\`${error_messages//_/\\_}\`\n⏰ *Time*: \`${error_time}\`"
    message=$(echo -e "$message" | sed 's/-/\\-/g;s/\./\\./g;s/_/\\_/g;s/(/\\(/g;s/)/\\)/g')
    local max_length=1000
    [ ${#message} -gt $max_length ] && message="${message:0:$((max_length - 50))}...\n\`[Message truncated]\`"
    curl -s -X POST "https://api.telegram.org/bot$BACKUP_TELEGRAM_BOT_KEY/sendMessage" \
        -d chat_id="$BACKUP_TELEGRAM_CHAT_ID" \
        -d parse_mode="MarkdownV2" \
        -d text="$message" >/dev/null 2>&1 \
    && colorized_echo green "Backup error notification sent to Telegram." \
    || colorized_echo red "Failed to send error notification to Telegram."
    if [ -f "$log_file" ]; then
        curl -s -F chat_id="$BACKUP_TELEGRAM_CHAT_ID" \
            -F document=@"$log_file;filename=backup_error.log" \
            -F caption="📜 *Backup Error Log* - ${error_time}" \
            "https://api.telegram.org/bot$BACKUP_TELEGRAM_BOT_KEY/sendDocument" >/dev/null 2>&1
    fi
}

backup_command() {
    local backup_dir="$APP_DIR/backup"
    local temp_dir="/tmp/marzban_backup"
    local timestamp=$(date +"%Y%m%d%H%M%S")
    local backup_file="$backup_dir/backup_$timestamp.tar.gz"
    local error_messages=()
    local log_file="/var/log/marzban_backup_error.log"
    > "$log_file"
    echo "Backup Log - $(date)" > "$log_file"

    if ! command -v rsync >/dev/null 2>&1; then detect_os; install_package rsync; fi

    rm -rf "$backup_dir"; mkdir -p "$backup_dir"; mkdir -p "$temp_dir"

    if [ -f "$ENV_FILE" ]; then
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            key=$(echo "$key" | xargs); value=$(echo "$value" | xargs)
            [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] && export "$key"="$value"
        done < "$ENV_FILE"
    else
        error_messages+=("Environment file (.env) not found.")
        send_backup_error_to_telegram "${error_messages[*]}" "$log_file"; exit 1
    fi

    # Detect DB type
    local db_type=""
    if grep -q "image: mariadb" "$COMPOSE_FILE" 2>/dev/null; then
        db_type="mariadb"
        container_name=$(docker compose -f "$COMPOSE_FILE" ps -q mariadb 2>/dev/null || echo "mariadb")
    elif grep -q "image: mysql" "$COMPOSE_FILE" 2>/dev/null; then
        db_type="mysql"
        container_name=$(docker compose -f "$COMPOSE_FILE" ps -q mysql 2>/dev/null || echo "mysql")
    else
        db_type="sqlite"
        sqlite_file="$DATA_DIR/db.sqlite3"
    fi

    case $db_type in
        mariadb)
            docker exec "$container_name" mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" \
                --all-databases --ignore-database=mysql --ignore-database=performance_schema \
                --ignore-database=information_schema --ignore-database=sys \
                --events --triggers > "$temp_dir/db_backup.sql" 2>>"$log_file" \
            || error_messages+=("MariaDB dump failed.")
            ;;
        mysql)
            docker exec "$container_name" mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" \
                marzban --events --triggers > "$temp_dir/db_backup.sql" 2>>"$log_file" \
            || error_messages+=("MySQL dump failed.")
            ;;
        sqlite)
            if [ -f "$sqlite_file" ]; then
                cp "$sqlite_file" "$temp_dir/db_backup.sqlite" 2>>"$log_file" \
                || error_messages+=("Failed to copy SQLite database.")
            else
                error_messages+=("SQLite database file not found at $sqlite_file.")
            fi
            ;;
    esac

    cp "$APP_DIR/.env" "$temp_dir/" 2>>"$log_file"
    cp "$APP_DIR/docker-compose.yml" "$temp_dir/" 2>>"$log_file"
    rsync -av --exclude 'xray-core' --exclude 'mysql' "$DATA_DIR/" "$temp_dir/marzban_data/" >>"$log_file" 2>&1

    tar -czf "$backup_file" -C "$temp_dir" . || error_messages+=("Failed to create backup archive.")
    rm -rf "$temp_dir"

    if [ ${#error_messages[@]} -gt 0 ]; then
        send_backup_error_to_telegram "${error_messages[*]}" "$log_file"; return
    fi
    colorized_echo green "Backup created: $backup_file"
    send_backup_to_telegram "$backup_file"
}

add_cron_job() {
    local schedule="$1"; local command="$2"
    local temp_cron=$(mktemp)
    crontab -l 2>/dev/null > "$temp_cron" || true
    grep -v "$command" "$temp_cron" > "${temp_cron}.tmp" && mv "${temp_cron}.tmp" "$temp_cron"
    echo "$schedule $command # marzban-backup-service" >> "$temp_cron"
    crontab "$temp_cron" && colorized_echo green "Cron job successfully added." \
        || colorized_echo red "Failed to add cron job."
    rm -f "$temp_cron"
}

remove_backup_service() {
    colorized_echo red "Removing backup service..."
    sed -i '/^# Backup service configuration/d' "$ENV_FILE"
    sed -i '/BACKUP_SERVICE_ENABLED/d' "$ENV_FILE"
    sed -i '/BACKUP_TELEGRAM_BOT_KEY/d' "$ENV_FILE"
    sed -i '/BACKUP_TELEGRAM_CHAT_ID/d' "$ENV_FILE"
    sed -i '/BACKUP_CRON_SCHEDULE/d' "$ENV_FILE"
    local temp_cron=$(mktemp)
    crontab -l 2>/dev/null > "$temp_cron"
    sed -i '/# marzban-backup-service/d' "$temp_cron"
    crontab "$temp_cron" && colorized_echo green "Backup service task removed from crontab." \
        || colorized_echo red "Failed to update crontab."
    rm -f "$temp_cron"
    colorized_echo green "Backup service has been removed."
}

backup_service() {
    local telegram_bot_key="" telegram_chat_id="" cron_schedule="" interval_hours=""

    colorized_echo blue "====================================="
    colorized_echo blue "      Welcome to Backup Service      "
    colorized_echo blue "====================================="

    if grep -q "BACKUP_SERVICE_ENABLED=true" "$ENV_FILE" 2>/dev/null; then
        telegram_bot_key=$(awk -F'=' '/^BACKUP_TELEGRAM_BOT_KEY=/ {print $2}' "$ENV_FILE")
        telegram_chat_id=$(awk -F'=' '/^BACKUP_TELEGRAM_CHAT_ID=/ {print $2}' "$ENV_FILE")
        cron_schedule=$(awk -F'=' '/^BACKUP_CRON_SCHEDULE=/ {print $2}' "$ENV_FILE" | tr -d '"')
        if [[ "$cron_schedule" == "0 0 * * *" ]]; then interval_hours=24
        else interval_hours=$(echo "$cron_schedule" | grep -oP '(?<=\*/)[0-9]+'); fi

        colorized_echo green "Current Backup Configuration:"
        colorized_echo cyan "Telegram Bot API Key: $telegram_bot_key"
        colorized_echo cyan "Telegram Chat ID: $telegram_chat_id"
        colorized_echo cyan "Backup Interval: Every $interval_hours hour(s)"
        echo "Choose an option:"
        echo "1. Reconfigure Backup Service"
        echo "2. Remove Backup Service"
        echo "3. Exit"
        read -p "Enter your choice (1-3): " user_choice
        case $user_choice in
            1) colorized_echo yellow "Starting reconfiguration..."; remove_backup_service ;;
            2) colorized_echo yellow "Removing..."; remove_backup_service; return ;;
            3) colorized_echo yellow "Exiting..."; return ;;
            *) colorized_echo red "Invalid choice. Exiting."; return ;;
        esac
    fi

    while true; do
        printf "Enter your Telegram bot API key: "; read telegram_bot_key
        [ -n "$telegram_bot_key" ] && break
        colorized_echo red "API key cannot be empty."
    done
    while true; do
        printf "Enter your Telegram chat ID: "; read telegram_chat_id
        [ -n "$telegram_chat_id" ] && break
        colorized_echo red "Chat ID cannot be empty."
    done
    while true; do
        printf "Set up the backup interval in hours (1-24):\n"; read interval_hours
        [[ "$interval_hours" =~ ^[0-9]+$ ]] || { colorized_echo red "Invalid input."; continue; }
        if [[ "$interval_hours" -eq 24 ]]; then
            cron_schedule="0 0 * * *"; colorized_echo green "Daily at midnight."; break
        elif [[ "$interval_hours" -ge 1 && "$interval_hours" -le 23 ]]; then
            cron_schedule="0 */$interval_hours * * *"
            colorized_echo green "Every $interval_hours hour(s)."; break
        else colorized_echo red "Enter a number between 1-24."; fi
    done

    sed -i '/^# Backup service configuration/d' "$ENV_FILE"
    sed -i '/BACKUP_SERVICE_ENABLED/d' "$ENV_FILE"
    sed -i '/BACKUP_TELEGRAM_BOT_KEY/d' "$ENV_FILE"
    sed -i '/BACKUP_TELEGRAM_CHAT_ID/d' "$ENV_FILE"
    sed -i '/BACKUP_CRON_SCHEDULE/d' "$ENV_FILE"

    { echo ""; echo "# Backup service configuration"
      echo "BACKUP_SERVICE_ENABLED=true"
      echo "BACKUP_TELEGRAM_BOT_KEY=$telegram_bot_key"
      echo "BACKUP_TELEGRAM_CHAT_ID=$telegram_chat_id"
      echo "BACKUP_CRON_SCHEDULE=\"$cron_schedule\""; } >> "$ENV_FILE"

    colorized_echo green "Backup service configuration saved in $ENV_FILE."
    add_cron_job "$cron_schedule" "$(which bash) -c '$APP_NAME backup'"
    colorized_echo green "Backup service successfully configured."
    colorized_echo blue "====================================="
}

# ─── Core update ────────────────────────────────────────────────────────────

get_xray_core() {
    identify_the_operating_system_and_architecture
    clear

    validate_version() {
        local version="$1"
        local response=$(curl -s "https://api.github.com/repos/XTLS/Xray-core/releases/tags/$version")
        if echo "$response" | grep -q '"message": "Not Found"'; then echo "invalid"
        else echo "valid"; fi
    }

    print_menu() {
        clear
        echo -e "\033[1;32m==============================\033[0m"
        echo -e "\033[1;32m      Xray-core Installer     \033[0m"
        echo -e "\033[1;32m==============================\033[0m"
        echo -e "\033[1;33mAvailable Xray-core versions:\033[0m"
        for ((i=0; i<${#versions[@]}; i++)); do
            echo -e "\033[1;34m$((i + 1)):\033[0m ${versions[i]}"
        done
        echo -e "\033[1;32m==============================\033[0m"
        echo -e "\033[1;35mM:\033[0m Enter a version manually"
        echo -e "\033[1;31mQ:\033[0m Quit"
        echo -e "\033[1;32m==============================\033[0m"
    }

    latest_releases=$(curl -s "https://api.github.com/repos/XTLS/Xray-core/releases?per_page=$LAST_XRAY_CORES")
    versions=($(echo "$latest_releases" | grep -oP '"tag_name": "\K(.*?)(?=")'))

    while true; do
        print_menu
        read -p "Choose a version (1-${#versions[@]}), M to enter manually, Q to quit: " choice
        if [[ "$choice" =~ ^[1-9][0-9]*$ ]] && [ "$choice" -le "${#versions[@]}" ]; then
            choice=$((choice - 1)); selected_version=${versions[choice]}; break
        elif [ "$choice" == "M" ] || [ "$choice" == "m" ]; then
            while true; do
                read -p "Enter version (e.g. v1.2.3): " custom_version
                if [ "$(validate_version "$custom_version")" == "valid" ]; then
                    selected_version="$custom_version"; break 2
                else echo -e "\033[1;31mInvalid version. Try again.\033[0m"; fi
            done
        elif [ "$choice" == "Q" ] || [ "$choice" == "q" ]; then
            echo -e "\033[1;31mExiting.\033[0m"; exit 0
        else
            echo -e "\033[1;31mInvalid choice.\033[0m"; sleep 2
        fi
    done

    echo -e "\033[1;32mSelected version $selected_version\033[0m"

    if ! command -v unzip >/dev/null 2>&1; then detect_os; install_package unzip; fi
    if ! command -v wget  >/dev/null 2>&1; then detect_os; install_package wget;  fi

    mkdir -p "$DATA_DIR/xray-core"
    cd "$DATA_DIR/xray-core"

    xray_filename="Xray-linux-$ARCH.zip"
    xray_download_url="https://github.com/XTLS/Xray-core/releases/download/${selected_version}/${xray_filename}"
    echo -e "\033[1;33mDownloading Xray-core ${selected_version}...\033[0m"
    wget -q -O "${xray_filename}" "${xray_download_url}"
    echo -e "\033[1;33mExtracting...\033[0m"
    unzip -o "${xray_filename}" >/dev/null 2>&1
    rm "${xray_filename}"
}

update_core_command() {
    check_running_as_root
    get_xray_core
    xray_executable_path="XRAY_EXECUTABLE_PATH=\"/var/lib/marzban/xray-core/xray\""
    echo "Changing the Marzban core..."
    if ! grep -q "^XRAY_EXECUTABLE_PATH=" "$ENV_FILE"; then
        echo "${xray_executable_path}" >> "$ENV_FILE"
    else
        sed -i "s~^XRAY_EXECUTABLE_PATH=.*~${xray_executable_path}~" "$ENV_FILE"
    fi
    colorized_echo red "Restarting Marzban..."
    restart_command -n
    colorized_echo blue "Installation of Xray-core version $selected_version completed."
}

# ─── Usage / Main ───────────────────────────────────────────────────────────

usage() {
    local script_name="${0##*/}"
    colorized_echo blue "=============================="
    colorized_echo magenta "        Marzban Fork Help"
    colorized_echo blue "=============================="
    colorized_echo cyan "Usage:"
    echo "  ${script_name} [command]"
    echo
    colorized_echo cyan "Commands:"
    colorized_echo yellow "  up              $(tput sgr0)– Start services"
    colorized_echo yellow "  down            $(tput sgr0)– Stop services"
    colorized_echo yellow "  restart         $(tput sgr0)– Restart services"
    colorized_echo yellow "  status          $(tput sgr0)– Show status"
    colorized_echo yellow "  logs            $(tput sgr0)– Show logs"
    colorized_echo yellow "  cli             $(tput sgr0)– Marzban CLI"
    colorized_echo yellow "  install         $(tput sgr0)– Install Marzban"
    colorized_echo yellow "  update          $(tput sgr0)– Update to latest version"
    colorized_echo yellow "  uninstall       $(tput sgr0)– Uninstall Marzban"
    colorized_echo yellow "  install-script  $(tput sgr0)– Install Marzban script"
    colorized_echo yellow "  backup          $(tput sgr0)– Manual backup launch"
    colorized_echo yellow "  backup-service  $(tput sgr0)– Marzban Backupservice to backup to TG, and a new job in crontab"
    colorized_echo yellow "  core-update     $(tput sgr0)– Update/Change Xray core"
    colorized_echo yellow "  edit            $(tput sgr0)– Edit docker-compose.yml (via nano or vi editor)"
    colorized_echo yellow "  edit-env        $(tput sgr0)– Edit environment file (via nano or vi editor)"
    colorized_echo yellow "  help            $(tput sgr0)– Show this help message"
    echo
    colorized_echo cyan "Directories:"
    colorized_echo magenta "  App directory: $APP_DIR"
    colorized_echo magenta "  Data directory: $DATA_DIR"
    colorized_echo blue "=============================="
    echo
}

case "$1" in
    up)             shift; up_command "$@" ;;
    down)           shift; down_command "$@" ;;
    restart)        shift; restart_command "$@" ;;
    status)         shift; status_command "$@" ;;
    logs)           shift; logs_command "$@" ;;
    cli)            shift; cli_command "$@" ;;
    backup)         shift; backup_command "$@" ;;
    backup-service) shift; backup_service "$@" ;;
    install)        shift; install_command "$@" ;;
    update)         shift; update_command "$@" ;;
    uninstall)      shift; uninstall_command "$@" ;;
    install-script) shift; install_marzban_script "$@" ;;
    core-update)    shift; update_core_command "$@" ;;
    edit)           shift; edit_command "$@" ;;
    edit-env)       shift; edit_env_command "$@" ;;
    help|*)         usage ;;
esac
