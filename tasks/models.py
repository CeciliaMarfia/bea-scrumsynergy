from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    dni = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f'Perfil de {self.usuario.username}'

# Crear perfil automáticamente cuando se crea un usuario
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    instance.perfil.save()

class Maquina(models.Model):
    codigo = models.CharField(max_length=100, unique=True)  # ⬅️ AGREGADO
    nombre = models.CharField(max_length=100)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    año = models.PositiveIntegerField()
    ubicacion = models.CharField(max_length=255)
    politica_cancelacion = models.DecimalField(max_digits=5, decimal_places=2, help_text='Porcentaje (%) de penalización')
    tipo = models.CharField(max_length=100)
    precio_por_dia = models.DecimalField(max_digits=10, decimal_places=2)
    permisos_requeridos = models.TextField()
    imagen = models.ImageField(upload_to='imagenes_maquinas/', blank=True, null=True)

    def __str__(self):
        return f'{self.nombre} ({self.marca} - {self.modelo})'
