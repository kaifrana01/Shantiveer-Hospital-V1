"""
settings_mysql.py  —  ShantiVeer HMS
MySQL variant of settings.py.

HOW TO USE
----------
1.  pip install mysqlclient                   # or: pip install PyMySQL
2.  Create database (see mysql_schema.sql)
3.  Copy this file to the root and point DJANGO_SETTINGS_MODULE at it:
      set DJANGO_SETTINGS_MODULE=ShantiVeer_hms.settings_mysql   (Windows)
      export DJANGO_SETTINGS_MODULE=ShantiVeer_hms.settings_mysql (Linux/Mac)
4.  python manage.py migrate
5.  python manage.py setup_roles
6.  python manage.py seed_database   (optional demo data)
7.  python manage.py runserver
"""

from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'shantiveer-mysql-change-in-production')
DEBUG      = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'
ALLOW_DEMO_SETUP = True

_raw_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]
if DEBUG:
    ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + ['127.0.0.1', 'localhost']))

CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']
X_FRAME_OPTIONS = 'SAMEORIGIN'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY    = True
SESSION_COOKIE_AGE      = 28800   # 8 hours

# ─── Apps ────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'accounts',
    'core',
    'opd',
    'ipd',
    'lab',
    'pharmacy',
    'prescription',
    'uhid',
    'masterdata',
    'income',
    'expenses',
    'simple_history',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'ShantiVeer_hms.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context_processors.hospital_info',
    ]},
}]

WSGI_APPLICATION = 'ShantiVeer_hms.wsgi.application'

# ─── DATABASE — MySQL ─────────────────────────────────────────────────────────
# Edit the values below (or set them as environment variables).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('MYSQL_NAME', 'shantiveer_hms'),
        'USER': os.environ.get('MYSQL_USER', 'root'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
        'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
        'PORT': os.environ.get('MYSQL_PORT', '3306'),
    }
}


# ─── Cache (in-memory for local dev) ─────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'shantiveer-hms',
    }
}

# ─── Password Validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── i18n / timezone ─────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N  = True
USE_TZ    = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL        = '/static/'
STATICFILES_DIRS  = [BASE_DIR / 'statics']
STATIC_ROOT       = BASE_DIR / 'staticfiles_collected'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Auth ────────────────────────────────────────────────────────────────────
LOGIN_URL          = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'accounts:login'
LOGIN_ATTEMPTS_LIMIT   = int(os.environ.get('LOGIN_ATTEMPTS_LIMIT', '5'))
LOGIN_LOCKOUT_DURATION = int(os.environ.get('LOGIN_LOCKOUT_DURATION', '300'))

# ─── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': '200/hour'},
}

# ─── Hospital Info ────────────────────────────────────────────────────────────
HOSPITAL_NAME    = os.environ.get('HOSPITAL_NAME',    'ShantiVeer Charitable Hospital')
HOSPITAL_ADDRESS = os.environ.get('HOSPITAL_ADDRESS', 'Main Road, Meerut, UP')
HOSPITAL_PHONE   = os.environ.get('HOSPITAL_PHONE',   '9821235034')

# ─── Email (console for local dev) ───────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL  = 'noreply@shantiveer.in'
PASSWORD_RESET_TIMEOUT = 86400

# ─── Logging ─────────────────────────────────────────────────────────────────
logs_dir = BASE_DIR / 'logs'
logs_dir.mkdir(exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
        'file':    {'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(logs_dir / 'hms.log'),
                    'maxBytes': 5*1024*1024, 'backupCount': 3, 'formatter': 'verbose'},
    },
    'root':    {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console','file'], 'level': 'WARNING', 'propagate': False},
        'core':   {'handlers': ['console','file'], 'level': 'INFO',    'propagate': False},
    },
}
