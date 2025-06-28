from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from application.models import Role, Perfil, Maquina
from datetime import date


class Command(BaseCommand):
    help = 'Create owner user with default credentials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corregir-estados',
            action='store_true',
            help='Corregir estados incorrectos de las máquinas',
        )

    def handle(self, *args, **kwargs):
        if kwargs['corregir_estados']:
            self.handle_corregir_estados(*args, **kwargs)
            return

        try:
            with transaction.atomic():
                # Crear el usuario dueño
                owner_user = User.objects.create_user(
                    username='owner',
                    email='owner@example.com',
                    password='owner123',
                    first_name='Owner',
                    last_name='User'
                )

                # Crear el rol de dueño si no existe
                owner_role, created = Role.objects.get_or_create(name=Role.DUENO)

                # Crear el perfil del dueño
                owner_profile = Perfil.objects.create(
                    usuario=owner_user,
                    role=owner_role,
                    email_verificado=True
                )

                self.stdout.write(
                    self.style.SUCCESS('Owner user created successfully!')
                )
                self.stdout.write(
                    self.style.SUCCESS('Username: owner')
                )
                self.stdout.write(
                    self.style.SUCCESS('Password: owner123')
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error creating owner user: {str(e)}'))

    def handle_corregir_estados(self, *args, **options):
        cambios = 0
        for maquina in Maquina.objects.all():
            estado_original = maquina.estado
            if estado_original != estado_original.lower():
                maquina.estado = estado_original.lower()
                maquina.save()
                cambios += 1
                self.stdout.write(self.style.SUCCESS(f"Corregido: {estado_original} -> {maquina.estado} (ID: {maquina.id})"))
        if cambios == 0:
            self.stdout.write(self.style.SUCCESS('No se encontraron estados incorrectos.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Se corrigieron {cambios} máquinas.'))
