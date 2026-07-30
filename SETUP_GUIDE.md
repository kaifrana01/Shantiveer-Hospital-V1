# ShantiVeer HMS — Complete Setup Guide
## New Account / New Deployment (End to End)

---

## PART 1 — Cloudinary (File Storage)

Files uploaded in the app (IPD documents, ultrasound scans, staff photos) are
stored on Cloudinary. Free 25 GB, no credit card required.

### Step 1 — Create Cloudinary Account

1. Go to **https://cloudinary.com**
2. Click **Sign Up Free**
3. Sign up with Google (easiest) or email
4. After login, you land on the **Dashboard**

### Step 2 — Get Your Credentials

On the Cloudinary Dashboard you will see three values. Copy all three:

```
Cloud Name   →  e.g.  bmwph0qe
API Key      →  e.g.  468212852982854
API Secret   →  e.g.  GzcQ-Xlh2StU60iMI3tXXcHAM7s
```

Keep these — you will need them in both local `.env` and Vercel.

### Step 3 — Add to Local .env

Open `.env` in the project root and add:

```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

---

## PART 2 — Database (Aiven MySQL)

The app uses Aiven MySQL (free tier). If setting up a new account:

### Step 1 — Create Aiven Account

1. Go to **https://aiven.io** → Sign Up Free (Google login works)
2. Create a new service → **MySQL**
3. Plan: **Free** → Region: closest to India (e.g. `google-asia-south1`)
4. Service name: `shantiveer-mysql`
5. Click **Create Service** — takes ~2 minutes

### Step 2 — Get Connection Details

From the Aiven service page → **Connection Information**:

```
Host      →  mysql-xxxxx.a.aivencloud.com
Port      →  (shown, usually 5-digit)
Database  →  defaultdb
Username  →  avnadmin
Password  →  (shown — copy it)
```

### Step 3 — Add to Local .env

```env
MYSQL_NAME=defaultdb
MYSQL_USER=avnadmin
MYSQL_PASSWORD=your_aiven_password
MYSQL_HOST=mysql-xxxxx.a.aivencloud.com
MYSQL_PORT=12345
```

### Step 4 — Run Migrations

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py setup_roles
```

---

## PART 3 — Local Development Setup

### Step 1 — Clone and Install

```bash
git clone <your-repo-url>
cd New-Shantiveer-Project
pip install -r requirements.txt
```

### Step 2 — Create .env File

Copy the example and fill in your values:

```bash
copy .env.example .env
```

Your complete `.env` for local dev should look like:

```env
DJANGO_SECRET_KEY=generate-one-with-command-below
DJANGO_DEBUG=True
DJANGO_LOG_LEVEL=WARNING

ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

MYSQL_NAME=defaultdb
MYSQL_USER=avnadmin
MYSQL_PASSWORD=your_aiven_password
MYSQL_HOST=mysql-xxxxx.a.aivencloud.com
MYSQL_PORT=12345

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

HOSPITAL_NAME=ShantiVeer Hospital
HOSPITAL_ADDRESS=Charthwal Main Road, Thana Bhawan
HOSPITAL_PHONE=9876543210
HOSPITAL_UPI_ID=shantiveerhospital@ybl

LOGIN_ATTEMPTS_LIMIT=5
LOGIN_LOCKOUT_DURATION=300
ALLOW_DEMO_SETUP=false
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 3 — Setup Database

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py setup_roles
```

### Step 4 — Create Admin User

```bash
python manage.py createsuperuser
```

### Step 5 — Run Server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000**

---

## PART 4 — Vercel Deployment

### Step 1 — Create Vercel Account

1. Go to **https://vercel.com** → Sign Up (use GitHub)
2. Import your GitHub repository
3. Framework: **Other**
4. Build Command: `bash build.sh`
5. Output Directory: leave blank
6. Click **Deploy** (first deploy will fail — that's fine, env vars not set yet)

### Step 2 — Set Environment Variables

Go to **Vercel → Your Project → Settings → Environment Variables**

Add every variable below. Select **All Environments** (Production, Preview, Development):

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | generate with command above — use a NEW key for production |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `shantiveerhospital.in,www.shantiveerhospital.in` |
| `CSRF_TRUSTED_ORIGINS` | `https://shantiveerhospital.in,https://www.shantiveerhospital.in` |
| `SECURE_SSL_REDIRECT` | `False` |
| `MYSQL_NAME` | `defaultdb` |
| `MYSQL_USER` | `avnadmin` |
| `MYSQL_PASSWORD` | your Aiven password |
| `MYSQL_HOST` | your Aiven host |
| `MYSQL_PORT` | your Aiven port |
| `CLOUDINARY_CLOUD_NAME` | your Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | your Cloudinary API key |
| `CLOUDINARY_API_SECRET` | your Cloudinary API secret |
| `HOSPITAL_NAME` | `ShantiVeer Hospital` |
| `HOSPITAL_ADDRESS` | `Charthwal Main Road, Thana Bhawan` |
| `HOSPITAL_PHONE` | `9876543210` |
| `HOSPITAL_UPI_ID` | your UPI ID |
| `LOGIN_ATTEMPTS_LIMIT` | `5` |
| `LOGIN_LOCKOUT_DURATION` | `300` |
| `ALLOW_DEMO_SETUP` | `false` |

### Step 3 — Redeploy

Go to **Vercel → Deployments → click the latest → Redeploy**

The `build.sh` automatically runs:
- `pip install -r requirements.txt`
- `python manage.py collectstatic`
- `python manage.py createcachetable`

### Step 4 — Run Migrations on Production DB

Vercel doesn't run migrations automatically. Run them once from your local
machine (your local machine connects to the same Aiven MySQL):

```bash
python manage.py migrate
python manage.py setup_roles
```

This only needs to be done once, or when new migrations are added.

### Step 5 — Add Custom Domain (Optional)

1. Vercel → Project → Settings → Domains
2. Add `shantiveerhospital.in` and `www.shantiveerhospital.in`
3. Vercel shows you DNS records — add them to your domain registrar
4. SSL is automatic

---

## PART 5 — Quick Reference Checklist

### New Setup Checklist

- [ ] Cloudinary account created, 3 credentials copied
- [ ] Aiven MySQL created, connection details copied
- [ ] `.env` file created with all values filled in
- [ ] `pip install -r requirements.txt` done
- [ ] `python manage.py migrate` done
- [ ] `python manage.py createcachetable` done
- [ ] `python manage.py setup_roles` done
- [ ] `python manage.py createsuperuser` done
- [ ] Local server runs without errors
- [ ] GitHub repo pushed
- [ ] Vercel project created, all env vars added
- [ ] Vercel redeployed successfully
- [ ] Production site opens at login page
- [ ] Admin login works at `/admin/`

### After Every Code Change

```bash
git add .
git commit -m "your message"
git push
```
Vercel auto-deploys on every push to main.

### After Adding New Models (New Migrations)

```bash
python manage.py makemigrations
python manage.py migrate          # runs on production Aiven DB
git add .
git commit -m "add migrations"
git push
```

---

## PART 6 — Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Table 'django_cache' doesn't exist` | createcachetable not run | `python manage.py createcachetable` |
| `No module named 'cloudinary_storage'` | packages not installed | `pip install -r requirements.txt` |
| `DJANGO_SECRET_KEY not set` | env var missing | Add `DJANGO_SECRET_KEY` to Vercel env vars |
| `CSRF verification failed` | domain not in CSRF_TRUSTED_ORIGINS | Add your domain to `CSRF_TRUSTED_ORIGINS` |
| `Access denied for user` | wrong DB credentials | Check `MYSQL_PASSWORD` and `MYSQL_HOST` |
| Static files not loading on Vercel | collectstatic not run | Redeploy — `build.sh` runs collectstatic |
| Uploaded files lost after deploy | Cloudinary not configured | Add 3 Cloudinary env vars to Vercel |
