import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import BaseCommand, CommandError, call_command
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

class Command(BaseCommand):
    help = 'Optionally seed the demo and create a superuser once from environment secrets.'

    def handle(self, *args, **options):
        if os.environ.get('SEED_DEMO_DATA') == '1':
            call_command('seed_demo_data')
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        if not any([username, password, email]):
            return
        if not username:
            raise CommandError('Set DJANGO_SUPERUSER_USERNAME for admin bootstrap.')
        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing:
            if not (existing.is_superuser and existing.is_staff and existing.is_active):
                raise CommandError('That username already belongs to a non-active-admin account. Choose a new DJANGO_SUPERUSER_USERNAME; existing accounts are never elevated automatically.')
            self.stdout.write('Admin account already exists; password and permissions unchanged.')
            return
        if not password or not email:
            raise CommandError('Set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD to create the admin account.')
        try:
            validate_email(email)
            validate_password(password, User(username=username, email=email))
        except ValidationError as exc:
            raise CommandError('Admin email or password does not meet validation requirements.') from exc
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write('Admin account created. Remove DJANGO_SUPERUSER_PASSWORD from the service environment after successful deployment.')
