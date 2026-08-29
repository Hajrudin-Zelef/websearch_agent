#!/bin/bash
# ============================================================================
# WebSearch Agent - Installation Automatique
# ============================================================================
# Usage: curl -fsSL https://raw.githubusercontent.com/Hajrudin-Zelef/websearch_agent/main/install.sh | bash
# Ou:    ./install.sh
# ============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
REPO_URL="https://github.com/Hajrudin-Zelef/websearch_agent.git"
INSTALL_DIR="$HOME/websearch_agent"
SERVICE_NAME="websearch-agent"

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║           WebSearch Agent - Installation Automatique         ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    command -v "$1" &> /dev/null
}

# ============================================================================
# DETECTION DU SYSTEME
# ============================================================================

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            OS="debian"
            PKG_MANAGER="apt-get"
        elif [ -f /etc/redhat-release ]; then
            OS="redhat"
            PKG_MANAGER="yum"
        elif [ -f /etc/arch-release ]; then
            OS="arch"
            PKG_MANAGER="pacman"
        else
            OS="linux"
            PKG_MANAGER="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG_MANAGER="brew"
    else
        OS="unknown"
        PKG_MANAGER="unknown"
    fi
    log_info "Systeme detecte: $OS"
}

# ============================================================================
# INSTALLATION DES DEPENDANCES
# ============================================================================

install_docker() {
    if check_command docker; then
        log_success "Docker deja installe: $(docker --version)"
        return 0
    fi

    log_info "Installation de Docker..."

    if [[ "$OS" == "macos" ]]; then
        if ! check_command brew; then
            log_error "Homebrew requis pour l'installation sur macOS"
            log_info "Installer Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
        brew install --cask docker
        log_success "Docker installe via Homebrew"
    elif [[ "$OS" == "debian" ]]; then
        log_info "Telechargement du script Docker..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sudo sh /tmp/get-docker.sh
        rm -f /tmp/get-docker.sh
        sudo usermod -aG docker "$USER"
        log_success "Docker installe"
        log_warning "Redemarrez votre session pour utiliser Docker sans sudo"
    elif [[ "$OS" == "redhat" ]]; then
        log_info "Telechargement du script Docker..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sudo sh /tmp/get-docker.sh
        rm -f /tmp/get-docker.sh
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "$USER"
        log_success "Docker installe"
    else
        log_info "Installation manuelle de Docker requise"
        log_info "Visitez: https://docs.docker.com/get-docker/"
        exit 1
    fi
}

install_docker_compose() {
    if docker compose version &> /dev/null; then
        log_success "Docker Compose deja disponible"
        return 0
    fi

    log_info "Installation de Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose installe"
}

install_python() {
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python deja installe: $PYTHON_VERSION"
        return 0
    fi

    log_info "Installation de Python..."

    if [[ "$OS" == "debian" ]]; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
    elif [[ "$OS" == "macos" ]]; then
        brew install python@3.13
    elif [[ "$OS" == "redhat" ]]; then
        sudo yum install -y python3 python3-pip
    fi

    log_success "Python installe"
}

# ============================================================================
# CLONAGE ET CONFIGURATION
# ============================================================================

clone_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "Repertoire $INSTALL_DIR deja existant"
        read -p "Voulez-vous le remplacer ? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_info "Utilisation du repertoire existant"
            return 0
        fi
    fi

    log_info "Clonage du depot..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    log_success "Depot clone dans $INSTALL_DIR"
}

setup_env() {
    if [ ! -f .env ]; then
        cp .env.example .env
        chmod 600 .env
        log_success "Fichier .env cree"
    else
        chmod 600 .env
        log_info "Fichier .env deja existant"
    fi

    # Creer le dossier data et custom_domains.json
    mkdir -p data
    if [ ! -f data/custom_domains.json ]; then
        echo '{}' > data/custom_domains.json
        log_success "data/custom_domains.json cree"
    fi
}

# ============================================================================
# CONFIGURATION DES CLES API
# ============================================================================

prompt_api_keys() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Configuration des cles API${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Les cles optionnelles permettent d'activer plus de sources de recherche.${NC}"
    echo -e "${YELLOW}Vous pouvez les configurer plus tard en editant le fichier .env${NC}"
    echo ""

    # Provider
    echo -e "${GREEN}1. Provider LLM${NC}"
    echo "   1) OpenRouter (recommande)"
    echo "   2) DeepSeek"
    read -p "   Choix [1-2] (defaut: 1): " PROVIDER_CHOICE
    PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

    if [ "$PROVIDER_CHOICE" = "2" ]; then
        sed -i "s|^PROVIDER=.*|PROVIDER=deepseek|" .env
        echo "   Recuperer une cle: https://platform.deepseek.com/api_keys"
        read -s -p "   Cle DeepSeek: " DEEPSEEK_KEY
        echo
        if [ -n "$DEEPSEEK_KEY" ]; then
            sed -i "s|^DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=$DEEPSEEK_KEY|" .env
            log_success "Cle DeepSeek configuree"
        fi
    else
        sed -i "s|^PROVIDER=.*|PROVIDER=openrouter|" .env
        echo "   Recuperer une cle: https://openrouter.ai/keys"
        read -s -p "   Cle OpenRouter: " OPENROUTER_KEY
        echo
        if [ -n "$OPENROUTER_KEY" ]; then
            sed -i "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$OPENROUTER_KEY|" .env
            log_success "Cle OpenRouter configuree"
        fi
    fi

    # Admin password
    echo ""
    echo -e "${GREEN}2. Mot de passe admin${NC}"
    read -s -p "   Mot de passe admin (obligatoire): " ADMIN_PWD
    echo
    if [ -n "$ADMIN_PWD" ]; then
        ADMIN_HASH=$(python3 -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('$ADMIN_PWD'))" 2>/dev/null)
        if [ -n "$ADMIN_HASH" ]; then
            sed -i "s|^ADMIN_PASSWORD_HASH=.*|ADMIN_PASSWORD_HASH=$ADMIN_HASH|" .env
            log_success "Mot de passe admin hashé"
        else
            sed -i "s|^#*ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PWD|" .env
            log_warning "Hash Argon2id non disponible, mot de passe en clair"
        fi
    fi

    # 2FA TOTP
    echo ""
    echo -e "${GREEN}3. Secret TOTP 2FA (optionnel)${NC}"
    read -p "   Generer un secret TOTP ? (Y/n): " TOTP_CHOICE
    if [[ ! "$TOTP_CHOICE" =~ ^[Nn]$ ]]; then
        TOTP_SECRET=$(python3 -c "import pyotp; print(pyotp.random_base32())" 2>/dev/null)
        if [ -n "$TOTP_SECRET" ]; then
            TOTP_URL=$(python3 -c "import pyotp; print(pyotp.totp.TOTP('$TOTP_SECRET').provisioning_uri(name='admin', issuer_name='WebSearch Agent'))" 2>/dev/null)
            sed -i "s|^#*ADMIN_TOTP_SECRET=.*|ADMIN_TOTP_SECRET=$TOTP_SECRET|" .env
            log_success "Secret TOTP genere"
            echo -e "  ${CYAN}Secret:${NC} $TOTP_SECRET"
            echo -e "  ${CYAN}URL:${NC} $TOTP_URL"
            echo -e "  ${YELLOW}Scannez le QR code avec Google Authenticator${NC}"
        fi
    else
        read -s -p "   Entrez votre secret TOTP (laisser vide pour ignorer): " TOTP_VAL
        echo
        if [ -n "$TOTP_VAL" ]; then
            sed -i "s|^#*ADMIN_TOTP_SECRET=.*|ADMIN_TOTP_SECRET=$TOTP_VAL|" .env
            log_success "Secret TOTP configure"
        fi
    fi

    # Perplexity
    echo ""
    echo -e "${GREEN}4. Perplexity (optionnel)${NC}"
    echo "   Recuperer une cle: https://perplexity.ai/settings/api"
    read -s -p "   Cle Perplexity (laisser vide pour ignorer): " PERPLEXITY_KEY
    echo

    # Tavily
    echo ""
    echo -e "${GREEN}5. Tavily (optionnel)${NC}"
    echo "   Recuperer une cle: https://tavily.com"
    read -s -p "   Cle Tavily (laisser vide pour ignorer): " TAVILY_KEY
    echo

    # Brave
    echo ""
    echo -e "${GREEN}6. Brave Search (optionnel)${NC}"
    echo "   Recuperer une cle: https://brave.com/search/api/"
    read -s -p "   Cle Brave (laisser vide pour ignorer): " BRAVE_KEY
    echo

    # GitHub
    echo ""
    echo -e "${GREEN}7. GitHub Token (optionnel)${NC}"
    echo "   Recuperer un token: https://github.com/settings/tokens"
    read -s -p "   Token GitHub (laisser vide pour ignorer): " GITHUB_TOKEN_VAL
    echo

    # Appliquer les cles
    [ -n "$PERPLEXITY_KEY" ] && sed -i "s|^PERPLEXITY_API_KEY=.*|PERPLEXITY_API_KEY=$PERPLEXITY_KEY|" .env && log_success "Cle Perplexity configuree"
    [ -n "$TAVILY_KEY" ] && sed -i "s|^TAVILY_API_KEY=.*|TAVILY_API_KEY=$TAVILY_KEY|" .env && log_success "Cle Tavily configuree"
    [ -n "$BRAVE_KEY" ] && sed -i "s|^BRAVE_API_KEY=.*|BRAVE_API_KEY=$BRAVE_KEY|" .env && log_success "Cle Brave configuree"
    [ -n "$GITHUB_TOKEN_VAL" ] && sed -i "s|^GITHUB_TOKEN=.*|GITHUB_TOKEN=$GITHUB_TOKEN_VAL|" .env && log_success "Token GitHub configure"
}

# ============================================================================
# INSTALLATION DOCKER
# ============================================================================

start_docker_services() {
    log_info "Demarrage des services Docker..."

    docker compose up -d

    log_info "Attente du demarrage..."
    sleep 10

    # Verifier que le serveur repond
    for i in {1..30}; do
        if curl -s http://localhost:4500/health | grep -q "ok"; then
            log_success "Serveur demarre!"
            return 0
        fi
        sleep 2
    done

    log_warning "Le serveur met du temps a demarrer. Verifiez les logs:"
    log_info "docker compose logs -f"
}

# ============================================================================
# INSTALLATION MANUELLE (SANS DOCKER)
# ============================================================================

setup_manual() {
    log_info "Installation manuelle..."

    install_python

    python3 -m venv venv
    source venv/bin/activate

    pip install --upgrade pip
    pip install -r requirements.txt

    log_success "Dependances installees"
}

start_manual() {
    log_info "Demarrage du serveur..."

    source venv/bin/activate
    nohup uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools > server.log 2>&1 &
    echo $! > server.pid

    log_success "Serveur demarre (PID: $(cat server.pid))"
    log_info "Logs: tail -f server.log"
}

# ============================================================================
# INSTALLATION SYSTEMD
# ============================================================================

install_systemd() {
    if [[ "$OS" == "macos" ]]; then
        log_info "Systemd non disponible sur macOS"
        return 0
    fi

    log_info "Installation du service systemd (system-level)..."

    if [ -f "$INSTALL_DIR/websearch-agent.service" ]; then
        sudo cp "$INSTALL_DIR/websearch-agent.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable ${SERVICE_NAME}
        sudo systemctl start ${SERVICE_NAME}
        log_success "Service systemd installe et demarre"
        log_info "Statut: sudo systemctl status ${SERVICE_NAME}"
        log_info "Logs: sudo journalctl -u ${SERVICE_NAME} -f"
    else
        log_warning "Fichier websearch-agent.service non trouve"
        log_info "Creer le service manuellement ou copier depuis le VPS"
    fi
}

# ============================================================================
# MENU PRINCIPAL
# ============================================================================

show_menu() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Mode d'installation${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  1) Docker (recommande)"
    echo "  2) Manuel (Python + pip)"
    echo "  3) Docker + systemd"
    echo ""
    read -p "  Votre choix [1-3]: " CHOIX
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    print_banner
    detect_os
    show_menu

    case $CHOIX in
        1)
            log_info "Installation avec Docker..."
            install_docker
            install_docker_compose
            clone_repo
            setup_env
            prompt_api_keys
            start_docker_services
            ;;
        2)
            log_info "Installation manuelle..."
            clone_repo
            setup_env
            prompt_api_keys
            setup_manual
            start_manual
            ;;
        3)
            log_info "Installation Docker + systemd..."
            install_docker
            install_docker_compose
            clone_repo
            setup_env
            prompt_api_keys
            start_docker_services
            install_systemd
            ;;
        *)
            log_error "Choix invalide"
            exit 1
            ;;
    esac

    # Resumer
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║              Installation terminee avec succes!               ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}API:${NC}      http://localhost:4500"
    echo -e "  ${CYAN}Admin:${NC}    http://localhost:4500/admin"
    echo -e "  ${CYAN}Health:${NC}   http://localhost:4500/health"
    echo -e "  ${CYAN}Dossier:${NC}  $INSTALL_DIR"
    echo ""
    echo -e "  ${YELLOW}Commandes utiles:${NC}"
    echo -e "    Tester:    ${GREEN}curl -X POST http://localhost:4500/chat -H 'Content-Type: application/json' -d '{\"message\": \"test\"}'${NC}"
    echo -e "    Logs:      ${GREEN}docker compose logs -f${NC}"
    echo -e "    Arreter:   ${GREEN}docker compose down${NC}"
    echo -e "    Redemarrer: ${GREEN}docker compose restart${NC}"
    echo ""
}

# Lancer
main "$@"
