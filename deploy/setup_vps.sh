#!/usr/bin/env bash
# =============================================================================
# setup_vps.sh — One-time VPS setup for ShantiVeer HMS on Hostinger
# Run as root on a fresh Ubuntu 22.04 VPS:
#   bash setup_vps.sh
# =============================================================================
set -e

DOMAIN="shantiveerhospital.in"
APP_DIR="/var/www/shantiveer"
DEPLOY_USER="deploy"
REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git"  # ← UPDATE THIS

echo "============================================================"
echo " ShantiVeer HMS — VPS Setup"
echo " Domain : $DOMAIN"
echo " App dir: $APP_DIR"
echo "============================================================"

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/10] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

echo "[2/10] Installing dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    nginx certbot python3-certbot-nginx \
    git curl build-essential \
    pkg-config default-libmysqlclient-dev

# ── 2. Deploy user ────────────────────────────────────────────────────────────
echo "[3/10] Creating deploy user..."
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    echo "User '$DEPLOY_USER' created."
fi

# Allow deploy user to restart the service without a password
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart shantiveer" \
    >> /etc/sudoers.d/shantiveer-deploy
chmod 440 /etc/sudoers.d/shantiveer-deploy

# ── 3. Clone repo ─────────────────────────────────────────────────────────────
echo "[4/10] Cloning repository..."
mkdir -p "$APP_DIR"
chown "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$DEPLOY_USER" git clone "$REPO_URL" "$APP_DIR"
else
    echo "  Repo already cloned, skipping."
fi

# ── 4. Python virtualenv + dependencies ──────────────────────────────────────
echo "[5/10] Setting up Python virtualenv..."
sudo -u "$DEPLOY_USER" bash -c "
    cd $APP_DIR
    python3 -m venv venv
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
"

# ── 5. Production .env ────────────────────────────────────────────────────────
echo "[6/10] Setting up .env ..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chown "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo ""
    echo "  ⚠  IMPORTANT: Edit $APP_DIR/.env and fill in your credentials!"
    echo "     nano $APP_DIR/.env"
    echo ""
else
    echo "  .env already exists, skipping."
fi

# ── 6. Create logs & media dirs ───────────────────────────────────────────────
echo "[7/10] Creating logs and media directories..."
sudo -u "$DEPLOY_USER" mkdir -p "$APP_DIR/logs" "$APP_DIR/media"

# ── 7. Nginx ──────────────────────────────────────────────────────────────────
echo "[8/10] Configuring Nginx..."
cp "$APP_DIR/deploy/nginx/shantiveer.conf" /etc/nginx/sites-available/shantiveer

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Enable our site
ln -sf /etc/nginx/sites-available/shantiveer /etc/nginx/sites-enabled/shantiveer

nginx -t
systemctl reload nginx

# ── 8. SSL certificate ────────────────────────────────────────────────────────
echo "[9/10] Obtaining SSL certificate from Let's Encrypt..."
echo "  Make sure your DNS A record points $DOMAIN → this server's IP first!"
read -p "  DNS is pointing correctly? (y/N): " dns_ready
if [[ "$dns_ready" =~ ^[Yy]$ ]]; then
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos \
        --email "admin@$DOMAIN" --redirect
    echo "  SSL certificate installed."
else
    echo "  Skipping SSL setup. Run manually: certbot --nginx -d $DOMAIN -d www.$DOMAIN"
fi

# ── 9. systemd service ────────────────────────────────────────────────────────
echo "[10/10] Installing systemd service..."
cp "$APP_DIR/deploy/systemd/shantiveer.service" /etc/systemd/system/shantiveer.service
systemctl daemon-reload
systemctl enable shantiveer

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " Next steps:"
echo "  1. Edit /var/www/shantiveer/.env with your DB and email credentials"
echo "  2. Run the first deploy manually:"
echo "     cd $APP_DIR"
echo "     source venv/bin/activate"
echo "     python manage.py migrate"
echo "     python manage.py collectstatic --noinput"
echo "     sudo systemctl start shantiveer"
echo "     sudo systemctl status shantiveer"
echo ""
echo "  3. Add GitHub Secrets (Settings → Secrets → Actions):"
echo "     VPS_HOST     → your VPS IP"
echo "     VPS_USER     → deploy"
echo "     VPS_SSH_KEY  → your private SSH key"
echo "     VPS_PORT     → 22"
echo ""
echo " After that, every git push to main auto-deploys!"
echo "============================================================"
