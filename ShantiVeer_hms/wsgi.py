"""
WSGI config for SantiVeer HMS project.
Loads .env automatically when present (for local dev / simple deployment).
"""
import os
from django.core.wsgi import get_wsgi_application

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShantiVeer_hms.settings')
application = get_wsgi_application()
