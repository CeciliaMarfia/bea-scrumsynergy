from django.db import migrations, models


def marcar_alquileres(apps, schema_editor):
    # Hasta ahora los alquileres se distinguían solo por el prefijo ALQ del número.
    Reserva = apps.get_model('application', 'Reserva')
    for alquiler in Reserva.objects.filter(numero_reserva__startswith='ALQ'):
        alquiler.tipo = 'alquiler'
        alquiler.fecha_retiro = alquiler.fecha_reserva
        alquiler.save(update_fields=['tipo', 'fecha_retiro'])


class Migration(migrations.Migration):

    dependencies = [
        ('application', '0006_merge_20250707_1338'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='tipo',
            field=models.CharField(choices=[('reserva', 'Reserva'), ('alquiler', 'Alquiler')], default='reserva', max_length=10),
        ),
        migrations.AddField(
            model_name='reserva',
            name='fecha_retiro',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(marcar_alquileres, migrations.RunPython.noop),
    ]
