# Generated by Django 5.2.1 on 2025-06-03 17:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('application', '0004_role_perfil_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='perfil',
            name='dni',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
