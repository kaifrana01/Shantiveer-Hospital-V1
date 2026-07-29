#!/usr/bin/env bash
set -e

pip install --break-system-packages -r requirements.txt || pip3 install --break-system-packages -r requirements.txt
python manage.py collectstatic --noinput
# Create the database cache table if it doesn't exist yet (idempotent).
python manage.py createcachetable
