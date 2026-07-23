from pathlib import Path
import os

# Load .env file if python-dotenv is installed (development convenience)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'ShantiVeer-hms-dev-key-change-in-production')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOW_DEMO_SETUP = os.environ.get('ALLOW_DEMO_SETUP', 'false').lower() == 'true'

_raw_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]

if DEBUG:
    ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + ['127.0.0.1', 'localhost']))

# Allow all Vercel subdomains
ALLOWED_HOSTS += ['.vercel.app']

# CSRF: trust Vercel HTTPS origins
CSRF_TRUSTED_ORIGINS = [
    h for h in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if h.strip()
]
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app']

# Security headers (production only)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    X_FRAME_OPTIONS = 'SAMEORIGIN'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 28800  # 8 hours

# SameSite=Lax blocks the cookie from being sent on cross-site requests
# (CSRF via third-party forms, malicious iframes, etc.) while still
# allowing normal top-level navigation within the hospital's own domain.
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Defense-in-depth: keep idle sessions fresh and bounded.
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ─── WhiteNoise — always enabled (it's in requirements.txt) ──────────────────
_WHITENOISE = True

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
    'ultrasound',
    'pharmacy',
    'prescription',
    'uhid',
    'masterdata',
    'income',
    'expenses',
    'history',
    'simple_history',
]

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

if _WHITENOISE:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE += [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'ShantiVeer_hms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.hospital_info',
                'core.context_processors.role_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ShantiVeer_hms.wsgi.application'

# ─── Database — PostgreSQL only (via DATABASE_URL) ───────────────────────────
# SQLite has been removed. DATABASE_URL must always be set.
# For local dev: copy the Neon connection string into your .env file.
# Example: DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require

# _database_url = os.environ.get('DATABASE_URL', '')

# if not _database_url:
#     raise RuntimeError(
#         'DATABASE_URL environment variable is not set.\n'
#         'Set it in your .env file (local dev) or in Vercel environment variables.\n'
#         'Get a free PostgreSQL database at https://neon.tech'
#     )

# try:
#     import dj_database_url
# except ImportError:
#     raise ImportError(
#         'dj-database-url is not installed. Run: pip install dj-database-url psycopg2-binary'
#     )

# Dev-friendly fallback:
# - Default tries MySQL as configured in this project.
# - If MySQL isn't reachable (connection refused / server down / auth issues)
#   and USE_SQLITE_FOR_DEV is enabled (default: true for local development),
#   we fall back to SQLite so manage.py commands can run.
_USE_SQLITE_FOR_DEV = os.environ.get('USE_SQLITE_FOR_DEV', 'true').lower() == 'true'


MYSQL_DATABASE = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('MYSQL_NAME', 'shantiveer_hms'),
        'USER': os.environ.get('MYSQL_USER', 'root'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
        'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
        'PORT': os.environ.get('MYSQL_PORT', '3306'),
    }
}

if _USE_SQLITE_FOR_DEV:
    try:
        import socket
        from django.db import connections

        host = MYSQL_DATABASE['default']['HOST']
        port = int(MYSQL_DATABASE['default']['PORT'])
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()

        # Confirm credentials too by attempting a real connection.
        DATABASES = MYSQL_DATABASE
        connections.databases = DATABASES  # ensure Django uses these settings
        with connections['default'].cursor():
            pass

    except Exception:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(BASE_DIR / 'db.sqlite3'),
            }
        }

else:
    DATABASES = MYSQL_DATABASE



# ─── Cache ───────────────────────────────────────────────────────────────────
# Set REDIS_URL (Upstash free tier) for brute-force login protection
# to persist correctly across Vercel serverless invocations.
_redis_url = os.environ.get('REDIS_URL', '')

if _redis_url:
    try:
        import django_redis  # noqa: F401
        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': _redis_url,
                'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
            }
        }
    except ImportError:
        import warnings
        warnings.warn(
            'REDIS_URL is set but django-redis is not installed. '
            'Falling back to LocMemCache. Run: pip install django-redis',
            RuntimeWarning,
            stacklevel=1,
        )
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'shantiveer-hms-cache',
            }
        }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'shantiveer-hms-cache',
        }
    }

# ─── Password Validation ─────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'statics']
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'

# WhiteNoise serves compressed, hashed static files
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Authentication ───────────────────────────────────────────────────────────
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

LOGIN_ATTEMPTS_LIMIT = int(os.environ.get('LOGIN_ATTEMPTS_LIMIT', '5'))
LOGIN_LOCKOUT_DURATION = int(os.environ.get('LOGIN_LOCKOUT_DURATION', '300'))

# ─── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '200/hour',
        # Dashboard/aggregation endpoints run several Sum() queries across
        # large tables — throttle them tighter than general API traffic so
        # a runaway auto-refresh loop (or a malicious client) can't be used
        # to hammer the database.
        'dashboard': '120/min',
    },
}

# ─── Hospital Info ────────────────────────────────────────────────────────────
HOSPITAL_NAME = os.environ.get('HOSPITAL_NAME', 'ShantiVeer Hospital')
HOSPITAL_ADDRESS = os.environ.get('HOSPITAL_ADDRESS', 'Charthwal Main Road, Thana Bhawan')
HOSPITAL_PHONE = os.environ.get('HOSPITAL_PHONE', '9876543210')

# ─── Email ────────────────────────────────────────────────────────────────────
_default_email_backend = (
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', _default_email_backend)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', '')
PASSWORD_RESET_TIMEOUT = 86400

if not DEBUG and not EMAIL_HOST_USER:
    import warnings
    warnings.warn(
        'EMAIL_HOST_USER is not set. Password reset emails '
        'will not work in production.',
        RuntimeWarning,
        stacklevel=1,
    )

# ─── Logging ─────────────────────────────────────────────────────────────────
_is_vercel = bool(os.environ.get('VERCEL', ''))

_log_handlers = ['console']
_handler_config: dict = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
}

if not _is_vercel:
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    _log_handlers.append('file')
    _handler_config['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': str(logs_dir / 'hms.log'),
        'maxBytes': 5 * 1024 * 1024,
        'backupCount': 5,
        'formatter': 'verbose',
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': _handler_config,
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': _log_handlers,
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'core': {
            'handlers': _log_handlers,
            'level': 'INFO',
            'propagate': False,
        },
    },
}
