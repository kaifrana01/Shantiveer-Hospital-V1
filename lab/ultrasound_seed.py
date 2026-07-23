"""Helper to seed default ultrasound option catalog.

This is intentionally a lightweight standalone script so you can run it
from Django shell/management later.

Typical usage in Django shell:

  from lab.ultrasound_seed import seed_ultrasound_catalog
  seed_ultrasound_catalog()
"""

from decimal import Decimal

from .models import UltrasoundTestMaster


DEFAULT_OPTIONS = [
    'USG Whole Abdomen',
    'USG Upper Abdomen',
    'USG Lower Abdomen',
    'USG KUB (Kidney, Ureter, Bladder)',
    'USG Pelvis',
    'USG Pregnancy (Obstetric)',
    'USG NT Scan',
    'USG Anomaly Scan',
    'USG Growth Scan',
    'TVS (Transvaginal Scan)',
    'TRUS (Prostate)',
    'Breast USG',
    'Thyroid USG',
    'Scrotal USG',
    'Soft Tissue USG',
    'Color Doppler Upper Limb',
    'Color Doppler Lower Limb',
    'Carotid Doppler',
    'Echocardiography (2D Echo)',
]


def seed_ultrasound_catalog(*, default_rate=Decimal('0.00')):
    for name in DEFAULT_OPTIONS:
        obj, created = UltrasoundTestMaster.objects.get_or_create(
            name=name,
            defaults={'rate': default_rate, 'is_active': True},
        )
        if not created:
            # keep existing rate, but ensure active
            if not obj.is_active:
                obj.is_active = True
                obj.save(update_fields=['is_active'])

