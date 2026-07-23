"""
python manage.py setup_roles

Creates 4 HMS demo users and assigns them to correct permission groups.
Safe to run multiple times (idempotent — updates existing users).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

USERS = [
    dict(username='admin_hms',        password='Admin@123',   fn='Admin',   ln='User',    email='admin@shantiveer.in',       staff=True,  super_=True,  group=None),
    dict(username='doctor_hms',       password='Doctor@123',  fn='Dr Anil', ln='Sharma',  email='doctor@shantiveer.in',      staff=False, super_=False, group='Doctor'),
    dict(username='receptionist_hms', password='Recept@123',  fn='Priya',   ln='Nair',    email='reception@shantiveer.in',   staff=False, super_=False, group='Receptionist'),
    dict(username='pharmacist_hms',   password='Pharma@123',  fn='Ravi',    ln='Mishra',  email='pharmacy@shantiveer.in',    staff=False, super_=False, group='Pharmacist'),
]

class Command(BaseCommand):
    help = 'Create 4 HMS demo role users (admin / doctor / receptionist / pharmacist)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('\n=== ShantiVeer HMS — Role Setup ===\n'))
        for cfg in USERS:
            user, created = User.objects.get_or_create(username=cfg['username'])
            user.set_password(cfg['password'])
            user.first_name  = cfg['fn']
            user.last_name   = cfg['ln']
            user.email       = cfg['email']
            user.is_staff    = cfg['staff']
            user.is_superuser = cfg['super_']
            user.save()
            if cfg['group']:
                try:
                    grp = Group.objects.get(name=cfg['group'])
                    user.groups.set([grp])
                except Group.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠  Group '{cfg['group']}' missing — run migrations first."))
            verb = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(
                f"  ✓  {verb}: {cfg['username']:25s} | pass: {cfg['password']:14s} | role: {cfg['group'] or 'superuser'}"))

        self.stdout.write('\n' + self.style.SUCCESS('=== Credentials Summary ==='))
        self.stdout.write('  Role            Username               Password')
        self.stdout.write('  ─────────────── ────────────────────── ─────────────')
        self.stdout.write('  Administrator   admin_hms              Admin@123')
        self.stdout.write('  Doctor          doctor_hms             Doctor@123')
        self.stdout.write('  Receptionist    receptionist_hms       Recept@123')
        self.stdout.write('  Pharmacist      pharmacist_hms         Pharma@123')
        self.stdout.write('')
