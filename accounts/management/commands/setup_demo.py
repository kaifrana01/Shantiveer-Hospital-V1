"""
setup_demo — REMOVED

This command previously created a demo admin account with a well-known
password, which is a security risk.  It has been replaced with a notice
directing you to the standard Django account creation workflow.

Use the following instead:

    python manage.py createsuperuser

This creates an admin account securely with a password you choose.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Deprecated — use "python manage.py createsuperuser" instead'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n'
            '  setup_demo has been removed for security reasons.\n'
            '  Demo accounts with well-known passwords must not exist\n'
            '  in any deployed environment.\n'
            '\n'
            '  To create an admin account run:\n'
            '    python manage.py createsuperuser\n'
        ))
