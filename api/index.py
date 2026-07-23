"""
Vercel serverless entry point.
Vercel's @vercel/python runtime looks for a callable named 'app'.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShantiVeer_hms.settings')

# get_wsgi_application() calls django.setup() internally
from django.core.wsgi import get_wsgi_application  # noqa: E402
app = get_wsgi_application()

# Run migrations on cold start — idempotent and fast when already up-to-date.
# Vercel env var is set in vercel.json so this only runs in production.
if os.environ.get('VERCEL'):
    try:
        from django.core.management import call_command
        call_command('migrate', '--noinput', verbosity=0)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('migrate on cold start failed: %s', exc)
