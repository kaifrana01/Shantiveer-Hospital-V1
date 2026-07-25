#!/bin/bash
# Vercel build script — runs before deployment

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput --clear

echo "=== Build complete ==="
