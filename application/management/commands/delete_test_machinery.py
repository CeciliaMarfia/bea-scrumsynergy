from django.core.management.base import BaseCommand
from application.models import Maquina


class Command(BaseCommand):
    help = 'Delete test machinery with specific details'

    def handle(self, *args, **options):
        try:
            maquina = Maquina.objects.filter(
                marca='pruebita',
                modelo='DePrueba',
                ubicacion='La Plata',
                precio_por_dia=3.00
            ).first()

            if maquina:
                maquina.delete()
                self.stdout.write(self.style.SUCCESS(
                    'Successfully deleted test machinery'))
            else:
                self.stdout.write(self.style.WARNING(
                    'No machinery found with these details'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error deleting machinery: {str(e)}'))
