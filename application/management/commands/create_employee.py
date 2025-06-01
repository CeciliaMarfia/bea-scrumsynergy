from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from application.models import Role
from datetime import date


class Command(BaseCommand):
    help = 'Crea un usuario empleado con credenciales predefinidas'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Crear o obtener el rol de empleado
                employee_role, _ = Role.objects.get_or_create(
                    name=Role.EMPLEADO)

                # Datos del empleado
                employee_email = 'woulleizegijau-6101@yopmail.com'

                if not User.objects.filter(email=employee_email).exists():
                    employee = User.objects.create_user(
                        username=employee_email,
                        email=employee_email,
                        password='Empleado123!',  # Contraseña temporal que deberá cambiar
                        first_name='Sofia',
                        last_name='Lopez',
                    )

                    # Actualizar el perfil del empleado
                    employee.perfil.role = employee_role
                    employee.perfil.email_verificado = True
                    employee.perfil.dni = '03034567'
                    employee.perfil.direccion = 'Ensenada'
                    employee.perfil.fecha_nacimiento = date(
                        1990, 1, 1)  # Fecha ejemplo
                    employee.perfil.save()

                    self.stdout.write(self.style.SUCCESS(
                        'Empleado creado exitosamente\n' +
                        f'Email: {employee_email}\n' +
                        'Contraseña temporal: Empleado123!'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        'Ya existe un usuario con ese email'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error al crear empleado: {str(e)}'))
