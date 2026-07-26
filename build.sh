#!/usr/bin/env bash
set -e

pip install --break-system-packages -r requirements.txt || pip3 install --break-system-packages -r requirements.txt
python manage.py collectstatic --noinput
