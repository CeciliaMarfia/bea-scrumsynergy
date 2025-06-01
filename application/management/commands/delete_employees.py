from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from application.models import Role


class Command(BaseCommand):
    help = 'Elimina todos los usuarios con rol de empleado'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Obtener todos los usuarios que son empleados
                empleados = User.objects.filter(
                    perfil__role__name=Role.EMPLEADO)
                count = empleados.count()

                # Eliminar los empleados
                empleados.delete()

                self.stdout.write(self.style.SUCCESS(
                    f'Se eliminaron {count} empleados exitosamente'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error al eliminar empleados: {str(e)}'))
