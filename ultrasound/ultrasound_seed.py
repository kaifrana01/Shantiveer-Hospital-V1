"""
Seed script for UltrasoundTestMaster.

Run:
    python manage.py shell < ultrasound/ultrasound_seed.py
Or paste into Django shell.
"""
from ultrasound.models import UltrasoundTestMaster

TESTS = [
    ('USG Whole Abdomen',        600),
    ('USG KUB',                  500),
    ('USG Pelvis',               500),
    ('USG Obstetric / Pregnancy',600),
    ('NT Scan',                  800),
    ('Anomaly Scan',            1200),
    ('Growth Scan',              700),
    ('Thyroid USG',              500),
    ('Breast USG',               600),
    ('Scrotal USG',              600),
    ('Neck USG',                 500),
    ('Color Doppler',           1200),
    ('Venous Doppler',          1000),
    ('Arterial Doppler',        1100),
    ('2D Echo',                 1500),
    ('USG Guided Aspiration',   1500),
    ('Small Parts USG',          600),
]

created = 0
for name, rate in TESTS:
    _, c = UltrasoundTestMaster.objects.get_or_create(name=name, defaults={'rate': rate})
    if c:
        created += 1

print(f"Seeded {created} new tests ({len(TESTS) - created} already existed).")
