# Generated by Django 5.2.1 on 2025-06-04 16:45

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('application', '0008_reserva_empleado_gestor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='tarjetacredito',
            unique_together={('usuario', 'ultimos_digitos', 'nombre_titular')},
        ),
    ]
