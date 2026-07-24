"""
python manage.py setup_roles

Creates 4 HMS demo users and assigns them to correct permission groups.
Safe to run multiple times (idempotent — updates existing users).

WARNING: This command sets known demo passwords. NEVER run it on a
production server. It will refuse to run if DJANGO_DEBUG=False unless
you explicitly pass --force.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.conf import settings

USERS = [
    dict(username='admin_hms',        password='Admin@123',   fn='Admin',   ln='User',    email='admin@shantiveer.in',       staff=True,  super_=True,  group=None),
    dict(username='doctor_hms',       password='Doctor@123',  fn='Dr Anil', ln='Sharma',  email='doctor@shantiveer.in',      staff=False, super_=False, group='Doctor'),
    dict(username='receptionist_hms', password='Recept@123',  fn='Priya',   ln='Nair',    email='reception@shantiveer.in',   staff=False, super_=False, group='Receptionist'),
    dict(username='pharmacist_hms',   password='Pharma@123',  fn='Ravi',    ln='Mishra',  email='pharmacy@shantiveer.in',    staff=False, super_=False, group='Pharmacist'),
]

class Command(BaseCommand):
    help = 'Create 4 HMS demo role users (admin / doctor / receptionist / pharmacist)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow running in production (DJANGO_DEBUG=False). Use with caution.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options.get('force'):
            raise CommandError(
                'Refusing to run setup_roles in production (DJANGO_DEBUG=False).\n'
                'This command sets well-known demo passwords that are a security risk.\n'
                'If you really want to run it, pass --force. Then immediately change all passwords.'
            )

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
        self.stdout.write(self.style.WARNING(
            '  ⚠  CHANGE ALL PASSWORDS IMMEDIATELY after first login!'
        ))
