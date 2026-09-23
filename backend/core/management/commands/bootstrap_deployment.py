import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import BaseCommand, CommandError, call_command
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Optionally seed the demo and create a staff account once from environment secrets.'

    def handle(self, *args, **options):
        if os.environ.get('SEED_DEMO_DATA') == '1':
            call_command('seed_demo_data')
        username = os.environ.get('DEMO_STAFF_USERNAME')
        password = os.environ.get('DEMO_STAFF_PASSWORD')
        if not username and not password:
            return
        if not username or not password:
            raise CommandError('Set both DEMO_STAFF_USERNAME and DEMO_STAFF_PASSWORD.')
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write('Staff account already exists; password and permissions unchanged.')
            return
        try:
            validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError('Deployment staff password does not meet password requirements.') from exc
        User.objects.create_user(username=username, password=password, is_staff=True)
        self.stdout.write('Deployment staff account created. Remove DEMO_STAFF_PASSWORD from the service environment.')
