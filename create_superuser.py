from django.db import IntegrityError
from django.contrib.auth.models import User
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'system.settings')
django.setup()


try:
    superuser = User.objects.create_superuser(
        username='ceciliamarfia',
        email='cecilia_marfia@hotmail.com',
        password='Hola12345!'
    )
    print('Superuser created successfully!')
except IntegrityError:
    print('Superuser already exists!')
except Exception as e:
    print(f'An error occurred: {str(e)}')
