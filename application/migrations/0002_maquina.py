# Generated by Django 5.2.1 on 2025-05-23 18:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('application', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Maquina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=100, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('marca', models.CharField(max_length=100)),
                ('modelo', models.CharField(max_length=100)),
                ('anio', models.PositiveIntegerField()),
                ('ubicacion', models.CharField(max_length=255)),
                ('politica_cancelacion', models.DecimalField(decimal_places=2, help_text='Porcentaje (%) de cancelacion', max_digits=5)),
                ('tipo', models.CharField(choices=[('agricola', 'Agrícola'), ('construccion', 'Construcción'), ('mineria', 'Minería'), ('jardineria', 'Jardinería'), ('otros', 'Otros')], max_length=20)),
                ('precio_por_dia', models.DecimalField(decimal_places=2, max_digits=10)),
                ('permisos_requeridos', models.TextField()),
                ('imagen', models.ImageField(blank=True, null=True, upload_to='imagenes_maquinas/')),
            ],
        ),
    ]
