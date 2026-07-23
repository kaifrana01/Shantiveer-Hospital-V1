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

## Deploy to Vercel (via GitHub)

### Step 1 — Set up a free PostgreSQL database (Neon)

> SQLite does not work on Vercel — it has no persistent filesystem.

1. Go to [https://neon.tech](https://neon.tech) and create a free account
2. Create a new project → copy the **Connection String** (starts with `postgres://...`)

### Step 2 — Set up a free Redis cache (Upstash)

> Required for brute-force protection to work across serverless invocations.

1. Go to [https://upstash.com](https://upstash.com) and create a free account
2. Create a new Redis database → copy the **REDIS_URL** (starts with `rediss://...`)

### Step 3 — Push your code to GitHub

```bash
git init                          # if not already a git repo
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 4 — Connect to Vercel

1. Go to [https://vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repository
3. Framework Preset: **Other**
4. Build Command: `bash build_vercel.sh`
5. Output Directory: `staticfiles_collected`

### Step 5 — Set Environment Variables in Vercel

In your Vercel project → **Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A long random key (generate with command below) |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `yourapp.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://yourapp.vercel.app` |
| `DATABASE_URL` | Your Neon PostgreSQL connection string |
| `REDIS_URL` | Your Upstash Redis URL |
| `EMAIL_HOST_USER` | Your Gmail address |
| `EMAIL_HOST_PASSWORD` | Your Gmail App Password |
| `DEFAULT_FROM_EMAIL` | Your Gmail address |
| `HOSPITAL_NAME` | Your hospital name |
| `HOSPITAL_ADDRESS` | Your hospital address |
| `HOSPITAL_PHONE` | Your phone number |
| `VERCEL` | `1` |

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 6 — Deploy

Click **Deploy** in Vercel. The `build_vercel.sh` script will:
1. Install all Python dependencies
2. Run `collectstatic`
3. Run `migrate` against your Neon database

### Step 7 — Create superuser

After deployment, run this once using Vercel CLI or your local machine pointed at the production database:

```bash
# Option A: locally with production DATABASE_URL
DATABASE_URL="your-neon-url" python manage.py createsuperuser

# Option B: Vercel CLI
vercel env pull .env.production
python manage.py createsuperuser
```

---

## Traditional Server Deployment (Gunicorn)

```bash
bash deploy.sh   # runs: pip install, migrate, collectstatic, check

gunicorn ShantiVeer_hms.wsgi:application \
  --workers 3 \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

---

## Automatic Backup (SQLite / self-hosted only)

The backup system creates a ZIP of the database stored in `backups/`. Not available on Vercel (no persistent filesystem).

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
