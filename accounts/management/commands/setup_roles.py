"""
python manage.py setup_roles

Lists the RBAC groups that should exist in the database and verifies
they are present.  Use Django's built-in management commands or the
admin UI to create real users and assign them to groups.

  python manage.py createsuperuser          # create an admin account
  python manage.py shell                    # assign groups manually

This command no longer creates any demo users.  Demo users with
well-known passwords are a security risk and should never exist in a
production database.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

# The canonical list of RBAC groups defined in core/rbac.py.
EXPECTED_GROUPS = [
    'Admin',
    'Doctor',
    'Nurse',
    'Receptionist',
    'Pharmacist',
    'LabTech',
    'Accountant',
    'BillingClerk',
]


class Command(BaseCommand):
    help = 'Verify RBAC groups exist in the database (no users are created)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('\n=== ShantiVeer HMS — RBAC Group Check ===\n'))

        missing = []
        for name in EXPECTED_GROUPS:
            exists = Group.objects.filter(name=name).exists()
            if exists:
                self.stdout.write(self.style.SUCCESS(f'  ✓  {name}'))
            else:
                self.stdout.write(self.style.ERROR(f'  ✗  {name}  ← MISSING'))
                missing.append(name)

        self.stdout.write('')
        if missing:
            self.stdout.write(self.style.WARNING(
                f'  {len(missing)} group(s) missing. Run migrations to create them:\n'
                '    python manage.py migrate\n'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '  All RBAC groups are present.\n'
                '  Assign users to groups via the Django admin or:\n'
                '    python manage.py shell\n'
                '    >>> from django.contrib.auth.models import User, Group\n'
                '    >>> u = User.objects.get(username="your_user")\n'
                '    >>> u.groups.set([Group.objects.get(name="Doctor")])\n'
            ))
