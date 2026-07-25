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
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise RuntimeError(
        'DJANGO_SECRET_KEY environment variable is not set. '
        'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

ALLOW_DEMO_SETUP = os.environ.get('ALLOW_DEMO_SETUP', 'false').lower() == 'true'

_raw_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]

# Vercel deployments use *.vercel.app domains — always allow them
ALLOWED_HOSTS += ['.vercel.app']

if DEBUG:
    ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + ['127.0.0.1', 'localhost']))

CSRF_TRUSTED_ORIGINS = [
    h for h in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if h.strip()
]
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = ['https://shantiveerhospital.in', 'https://www.shantiveerhospital.in']

# Security headers (always set sensible defaults; tighten in production)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Default True in production — set to False when behind Nginx/reverse proxy
    # that terminates SSL itself, to avoid redirect loops.
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    X_FRAME_OPTIONS = 'SAMEORIGIN'
    SECURE_SSL_REDIRECT = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 28800  # 8 hours
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ─── WhiteNoise ───────────────────────────────────────────────────────────────
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

# ─── Database ─────────────────────────────────────────────────────────────────
# Primary path: DATABASE_URL (PostgreSQL via Neon, or any postgres URL).
# Fallback path: MySQL env vars (for self-hosted / local MySQL).
# Dev fallback: SQLite when neither is reachable (USE_SQLITE_FOR_DEV=true).

_database_url = os.environ.get('DATABASE_URL', '')

if _database_url:
    try:
        import dj_database_url
    except ImportError:
        raise ImportError(
            'dj-database-url is not installed. Run: pip install dj-database-url psycopg2-binary'
        )
    DATABASES = {
        'default': dj_database_url.config(
            default=_database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    }
else:
    # MySQL path — used for local dev and self-hosted production
    _mysql_options = {
        'charset': 'utf8mb4',
    }

    # Only enforce SSL in production (not local dev).
    # mysqlclient uses an 'ssl' dict — empty dict enables SSL without cert pinning.
    # Pass MYSQL_CA_CERT env var to specify a CA certificate path for strict verification.
    if not DEBUG:
        _mysql_ca = os.environ.get('MYSQL_CA_CERT', '')
        _mysql_options['ssl'] = {'ca': _mysql_ca} if _mysql_ca else {}

    _MYSQL_DATABASE = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_NAME', 'defaultdb'),
            'USER': os.environ.get('MYSQL_USER', 'avnadmin'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': _mysql_options,
        }
    }

    DATABASES = _MYSQL_DATABASE

# ─── Cache ───────────────────────────────────────────────────────────────────
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

# WhiteNoise serves compressed, hashed static files in production.
# In DEBUG mode use the default storage so runserver serves files normally.
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
else:
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
        'dashboard': '120/min',
        'alerts': '30/min',   # polling endpoint — 1 call per 2s max per user
    },
}

# ─── Hospital Info ────────────────────────────────────────────────────────────
HOSPITAL_NAME = os.environ.get('HOSPITAL_NAME', 'ShantiVeer Hospital')
HOSPITAL_ADDRESS = os.environ.get('HOSPITAL_ADDRESS', 'Charthwal Main Road, Thana Bhawan')
HOSPITAL_PHONE = os.environ.get('HOSPITAL_PHONE', '9876543210')
HOSPITAL_UPI_ID = os.environ.get('HOSPITAL_UPI_ID', '')

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
_log_handlers = ['console']
_handler_config: dict = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
}

# Only write to file if the filesystem is writable (not on Vercel/serverless).
# Vercel has a read-only filesystem — file logging is skipped there.
_is_vercel = os.environ.get('VERCEL', '') or os.environ.get('VERCEL_ENV', '')
if not _is_vercel:
    logs_dir = BASE_DIR / 'logs'
    try:
        logs_dir.mkdir(exist_ok=True)
        _log_handlers.append('file')
        _handler_config['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(logs_dir / 'hms.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        }
    except OSError:
        pass  # Filesystem not writable — console-only logging

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
