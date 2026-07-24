# ShantiVeer HMS — Hospital Management System

A Django-based Hospital Management System with OPD, IPD, Lab, Pharmacy, Prescriptions, Bed Management, and Automatic Backup.

---

## Quick Start (Local Development)

```bash
# 1. Clone and enter project
cd ShantiVeer_HMS_2

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit environment file
copy .env.example .env
# Edit .env — set DJANGO_DEBUG=True and set DATABASE_URL to your Neon PostgreSQL connection string

# 5. Run migrations
python manage.py migrate

# 6. Seed demo data (optional)
python manage.py seed_database

# 7. Create superuser
python manage.py createsuperuser

# 8. Run development server
python manage.py runserver
```

Visit: http://127.0.0.1:8000

---

## Deploy to Hostinger VPS (via GitHub)

Deployment is fully automated — every `git push` to `main` triggers a deploy to your VPS at `shantiveerhospital.in`.

### Step 1 — One-time VPS setup

SSH into your Hostinger VPS as root and run:

```bash
# Download and run the setup script
bash <(curl -s https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/deploy/setup_vps.sh)
```

Or upload `deploy/setup_vps.sh` and run it:

```bash
bash deploy/setup_vps.sh
```

This will:
- Install Python, Nginx, Certbot, mysqlclient dependencies
- Create a `deploy` user to run the app
- Clone the repo to `/var/www/shantiveer`
- Set up the Python virtualenv
- Configure Nginx + obtain a free Let's Encrypt SSL certificate
- Install the systemd service (auto-starts on reboot)

### Step 2 — Edit production `.env` on the VPS

```bash
nano /var/www/shantiveer/.env
```

Update these values:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `shantiveerhospital.in,www.shantiveerhospital.in` |
| `CSRF_TRUSTED_ORIGINS` | `https://shantiveerhospital.in,https://www.shantiveerhospital.in` |
| `MYSQL_NAME` | Your DB name |
| `MYSQL_USER` | Your DB user |
| `MYSQL_PASSWORD` | Your DB password |
| `MYSQL_HOST` | `127.0.0.1` (or Aiven host) |
| `EMAIL_HOST` | `smtp.hostinger.com` |
| `EMAIL_HOST_USER` | `noreply@shantiveerhospital.in` |
| `EMAIL_HOST_PASSWORD` | Your Hostinger email password |

### Step 3 — Run first migration and create superuser

```bash
cd /var/www/shantiveer
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
sudo systemctl start shantiveer
```

### Step 4 — Add GitHub Secrets for auto-deploy

Go to your GitHub repo → **Settings → Secrets and variables → Actions** → New secret:

| Secret | Value |
|---|---|
| `VPS_HOST` | Your VPS IP address |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Contents of your private SSH key |
| `VPS_PORT` | `22` |

> Generate an SSH key pair for deployments:
> ```bash
> ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/shantiveer_deploy
> # Add public key to VPS:
> cat ~/.ssh/shantiveer_deploy.pub >> /var/www/shantiveer/.ssh/authorized_keys
> # Add private key to GitHub Secrets as VPS_SSH_KEY
> cat ~/.ssh/shantiveer_deploy
> ```

### Step 5 — Push to deploy

```bash
git add .
git commit -m "your changes"
git push origin main
# GitHub Actions automatically SSHs into the VPS and deploys
```

Monitor deploy status under **Actions** tab in your GitHub repo.

---

## Automatic Backup (self-hosted only)

The backup system creates a ZIP of the database stored in `backups/`.

### Setup via Cron (Linux)
```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/project && python manage.py run_scheduled_backup >> logs/backup.log 2>&1
```

---

## Module Overview

| Module | URL Prefix | Description |
|--------|-----------|-------------|
| OPD | `/opd/` | Outpatient registrations & visits |
| IPD | `/ipd/` | Inpatient admissions & management |
| Lab | `/lab/` | Lab tests & investigation reports |
| Pharmacy | `/pharmacy/` | Stock, purchases & sales |
| Prescription | `/prescription/` | Doctor prescriptions |
| UHID | `/uhid/` | Patient master records |
| Income | `/income/` | Daybook & billing |
| Masterdata | `/master/` | Doctor list & lab interpretations |
| Backup | `/backup/` | DB backup & schedule (self-hosted only) |

---

## Security Features

- Username & password authentication on every login
- Brute-force login protection (rate limiting by IP)
- CSRF protection on all forms
- Path traversal protection on backup downloads
- Security headers (HSTS, X-Frame-Options, etc.) in production
- Session expiry after 8 hours
