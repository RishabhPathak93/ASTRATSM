"""
accounts/management/commands/create_admin.py

Creates the first admin user interactively.
Usage:
  python manage.py create_admin
  python manage.py create_admin --email admin@company.com --name "Alex Morgan"

No dummy data. No hardcoded passwords. Reads from stdin or env vars.
"""
import os
import getpass
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Create the initial admin user (no dummy data).'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='', help='Admin email address')
        parser.add_argument('--name',  type=str, default='', help='Admin full name')

    def handle(self, *args, **options):
        from accounts.models import User

        self.stdout.write(self.style.MIGRATE_HEADING('Nexus CRM — Create Admin User'))
        self.stdout.write('')

        # Email
        email = options['email'] or os.environ.get('ADMIN_EMAIL', '')
        if not email:
            email = input('Email address: ').strip()
        if not email:
            raise CommandError('Email is required.')
        email = email.lower()
        if User.objects.filter(email=email).exists():
            raise CommandError(f'A user with email "{email}" already exists.')

        # Name
        name = options['name'] or os.environ.get('ADMIN_NAME', '')
        if not name:
            name = input('Full name: ').strip()
        if not name:
            raise CommandError('Name is required.')

        # Password
        password = os.environ.get('ADMIN_PASSWORD', '')
        if not password:
            while True:
                password  = getpass.getpass('Password: ')
                password2 = getpass.getpass('Confirm password: ')
                if password != password2:
                    self.stderr.write('Passwords do not match. Try again.')
                    continue
                if len(password) < 8:
                    self.stderr.write('Password must be at least 8 characters.')
                    continue
                break

        try:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                name=name,
                role=User.Role.ADMIN,
            )
        except ValidationError as e:
            raise CommandError(f'Validation error: {e.message_dict}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Admin user created: {user.name} <{user.email}>'))
        self.stdout.write(self.style.WARNING(
            'Log in at /admin/ or POST to /api/v1/auth/login/ with your credentials.'
        ))
