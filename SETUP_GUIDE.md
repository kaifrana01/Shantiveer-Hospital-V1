# ShantiVeer HMS — Setup Guide (4-Panel + MySQL)

## Login Credentials

| Role           | Username            | Password     | After Login         |
|----------------|---------------------|--------------|---------------------|
| Administrator  | `admin_hms`         | `Admin@123`  | Full Dashboard      |
| Doctor         | `doctor_hms`        | `Doctor@123` | Dashboard (clinical)|
| Receptionist   | `receptionist_hms`  | `Recept@123` | OPD Registration    |
| Pharmacist     | `pharmacist_hms`    | `Pharma@123` | Pharmacy Inventory  |

---

## What Changed From Original

### 1. Login Page (`templates/accounts/login.html`)
- New **4-role card selector** — user picks a role first, then logs in
- Credential hint box auto-fills the username
- Each role gets its own accent colour (blue / green / purple / amber)
- On form error the previously selected role is restored automatically

### 2. Sidebar (`templates/includes/sidebar_dashboard.html`)
- **Role-aware** — each group sees only relevant menu items:
  - **Admin/superuser** — all modules + Data Backup + Django Admin
  - **Doctor** — Dashboard, OPD Queue, Search Patient, My IPD, Prescriptions, Lab
  - **Receptionist** — Dashboard, OPD Reg, IPD Admission, Bed Allocation, UHID, Payments, Bill, Discharge
  - **Pharmacist** — Dashboard, Inventory, Purchase, Sell, Sale/Purchase Log, Prescriptions
- Coloured role badge strip below the hospital logo
- Sidebar accent colour matches the role

### 3. Base Template (`templates/base_dashboard.html`)
- Injects `role-admin / role-doctor / role-recept / role-pharma` CSS class on `<body>`
- Topbar shows a coloured role chip next to the avatar
- Loads new `role_panels.css`

### 4. Role Panel CSS (`statics/css/role_panels.css`)
- Per-role sidebar accent border
- Per-role sidebar hover/active highlight
- Per-role topbar chip colour
- Per-role form-card border tint

### 5. `accounts/views.py`
- After login → `_role_redirect()` sends each group to its natural page
- Admin/Doctor → `core:dashboard`
- Receptionist → `opd:registration`
- Pharmacist   → `pharmacy:items`

### 6. MySQL Settings (`ShantiVeer_hms/settings_mysql.py`)
- Drop-in replacement for the original PostgreSQL settings
- MySQL connection credentials (DB: `shantiveer_hms`, user: `hms_user`)

### 7. New Management Command
- `python manage.py setup_roles` — creates all 4 demo users idempotently

---

## Installation Steps

### A. MySQL Setup

```bash
# 1. Run the schema script as root
mysql -u root -p < mysql_schema.sql

# 2. Verify
mysql -u hms_user -p'HMS@Secure123' -e "USE shantiveer_hms; SHOW TABLES;"
```

### B. Python Dependencies

```bash
pip install mysqlclient          # MySQL driver
pip install django whitenoise dj-database-url python-dotenv
pip install djangorestframework simple-history
```

### C. Django Setup

```bash
# 3. Point Django at the MySQL settings
export DJANGO_SETTINGS_MODULE=ShantiVeer_hms.settings_mysql    # Linux/Mac
set    DJANGO_SETTINGS_MODULE=ShantiVeer_hms.settings_mysql     # Windows CMD

# 4. Run migrations (creates all tables)
python manage.py migrate

# 5. Create the 4 role users
python manage.py setup_roles

# 6. (Optional) Load demo patient/pharmacy data
python manage.py seed_database

# 7. Start the server
python manage.py runserver
```

### D. Open in Browser

```
http://127.0.0.1:8000/
```

You will see the **4-role login screen**. Click a role card, then sign in.

---

## Panel Access Matrix

| Feature                | Admin | Doctor | Receptionist | Pharmacist |
|------------------------|:-----:|:------:|:------------:|:----------:|
| Dashboard              | ✅    | ✅     | ✅           | ✅         |
| OPD Registration       | ✅    | ✅(view)| ✅          | ❌         |
| IPD Admission          | ✅    | ✅     | ✅           | ❌         |
| Patient Vitals / Diag. | ✅    | ✅     | ❌           | ❌         |
| Prescriptions          | ✅    | ✅     | ❌           | ✅(view)   |
| Lab Investigations     | ✅    | ✅     | ❌           | ❌         |
| Bed Allocation         | ✅    | ❌     | ✅           | ❌         |
| Payments / Billing     | ✅    | ❌     | ✅           | ❌         |
| Discharge              | ✅    | ✅     | ✅           | ❌         |
| Pharmacy (Inventory)   | ✅    | ❌     | ❌           | ✅         |
| Pharmacy (Purchase)    | ✅    | ❌     | ❌           | ✅         |
| Pharmacy (Sale)        | ✅    | ❌     | ❌           | ✅         |
| Income / Daybook       | ✅    | ❌     | ❌           | ❌         |
| Master Data            | ✅    | ❌     | ❌           | ❌         |
| Data Backup            | ✅    | ❌     | ❌           | ❌         |
| Django Admin           | ✅    | ❌     | ❌           | ❌         |
| Change Password        | ✅    | ✅     | ✅           | ✅         |

---

## MySQL DB Details

| Key      | Value                   |
|----------|-------------------------|
| Database | `shantiveer_hms`        |
| User     | `hms_user`              |
| Password | `HMS@Secure123`         |
| Host     | `127.0.0.1`             |
| Port     | `3306`                  |
| Charset  | `utf8mb4`               |

To change, edit `settings_mysql.py` or set environment variables:
`MYSQL_DB`, `MYSQL_USER`, `MYSQL_PASS`, `MYSQL_HOST`, `MYSQL_PORT`
