from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = 'Create/update demo admin user for HMS — DEV ONLY, blocked in production'

    def handle(self, *args, **options):
        # DEV ONLY: blocked unless DEBUG=True or ALLOW_DEMO_SETUP=true
        if not (settings.DEBUG or getattr(settings, 'ALLOW_DEMO_SETUP', False)):
            raise CommandError(
                'setup_demo is a development-only command and cannot be run '
                'with DJANGO_DEBUG=False. Use "python manage.py createsuperuser" '
                'to create an admin account in production.'
            )

        User = get_user_model()
        username = 'admin'
        email = 'kaifrana219@gmail.com'
        password = 'admin@123'

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )

        user.email = email
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} demo admin — username: {username} / password: {password}'
        ))
        self.stdout.write(self.style.WARNING(
            'Remember: this command is blocked in production (DEBUG=False).'
        ))