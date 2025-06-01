from django.core.management.base import BaseCommand
from application.models import Role


class Command(BaseCommand):
    help = 'Crea los roles iniciales en la base de datos'

    def handle(self, *args, **kwargs):
        roles = [Role.CLIENTE, Role.EMPLEADO, Role.DUENO]
        for role_name in roles:
            Role.objects.get_or_create(name=role_name)
            self.stdout.write(self.style.SUCCESS(
                f'Rol "{role_name}" creado exitosamente'))
