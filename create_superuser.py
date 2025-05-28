from application.models import Perfil
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'system.settings')
django.setup()


try:
    with transaction.atomic():
        # Crear el superusuario
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@mail.com',
            password='admin123'
        )

        # Crear el perfil manualmente si no existe
        Perfil.objects.get_or_create(
            usuario=superuser,
            defaults={
                'email_verificado': True  # Como es superusuario, marcamos el email como verificado
            }
        )

        print('Superuser y perfil creados exitosamente!')
except IntegrityError:
    print('Superuser already exists!')
except Exception as e:
    print(f'An error occurred: {str(e)}')
