UPI ID field migrations planned.

- Added `upi_id` field to:
  - ipd.IPDPayment
  - opd.OPDVisit

Next steps:
- Create migrations for both apps
- Run `python manage.py makemigrations ipd opd`
- Run `python manage.py migrate`

