from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from application.models import Role, Perfil, Maquina
from datetime import date


class Command(BaseCommand):
    help = 'Creates the owner user with predefined credentials'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create or get the owner role
                owner_role, _ = Role.objects.get_or_create(name=Role.DUENO)

                # Create the owner user if it doesn't exist
                owner_email = 'cecilia.marfia172084@alumnos.info.unlp.edu.ar'
                if not User.objects.filter(email=owner_email).exists():
                    owner = User.objects.create_user(
                        username=owner_email,
                        email=owner_email,
                        password='owner123',  # You should change this password after first login
                        first_name='Roberto',
                        last_name='Paredes',
                        is_staff=True,  # Give admin site access
                    )

                    # Update the owner's profile
                    owner.perfil.role = owner_role
                    owner.perfil.email_verificado = True
                    owner.perfil.fecha_nacimiento = date(
                        1980, 1, 1)  # Example birth date
                    owner.perfil.save()

                    self.stdout.write(self.style.SUCCESS(
                        'Owner user created successfully'))
                else:
                    self.stdout.write(self.style.WARNING(
                        'Owner user already exists'))

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
