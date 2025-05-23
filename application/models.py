from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError


class Perfil(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil')
    dni = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    documento_foto = models.ImageField(
        upload_to='documentos/', blank=True, null=True)
    email_verificado = models.BooleanField(default=False)
    token_verificacion = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f'Perfil de {self.usuario.username}'


class HomeVideo(models.Model):
    titulo = models.CharField(max_length=100)
    video = models.FileField(upload_to='home_video/')
    activo = models.BooleanField(default=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Video de inicio'
        verbose_name_plural = 'Videos de inicio'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.activo:
            # Desactivar todos los otros videos
            HomeVideo.objects.exclude(id=self.id).update(activo=False)
        super().save(*args, **kwargs)


# Crear perfil automáticamente cuando se crea un usuario
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)


@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    instance.perfil.save()


class Maquina(models.Model):
    # opciones para el desplegable
    TIPO_CHOICES = [
        ('agricola', 'Agrícola'),
        ('construccion', 'Construcción'),
        ('mineria', 'Minería'),
        ('jardineria', 'Jardinería'),
        ('otros', 'Otros'),
    ]

    TIPO_CANCELACION_CHOICES = [
        ('total', 'Reembolso total (100%)'),
        ('parcial', 'Reembolso parcial (10-90%)'),
        ('sin_reembolso', 'Sin reembolso (0%)'),
    ]

    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    anio = models.PositiveIntegerField()
    ubicacion = models.CharField(max_length=255)
    tipo_cancelacion = models.CharField(
        max_length=20,
        choices=TIPO_CANCELACION_CHOICES,
        default='total'
    )
    politica_cancelacion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    precio_por_dia = models.DecimalField(max_digits=10, decimal_places=2)
    permisos_requeridos = models.TextField()

    def __str__(self):
        return f'{self.nombre} ({self.marca} - {self.modelo})'

    def clean(self):
        super().clean()
        # Verificar que haya al menos una imagen
        if self.pk and not self.imagenes.exists():
            raise ValidationError('Debe cargar al menos una imagen de la maquinaria.')


class ImagenMaquina(models.Model):
    maquina = models.ForeignKey(Maquina, related_name='imagenes', on_delete=models.CASCADE)
    imagen = models.ImageField(upload_to='imagenes_maquinas/')
    es_principal = models.BooleanField(default=False)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagen de maquinaria'
        verbose_name_plural = 'Imágenes de maquinaria'

    def __str__(self):
        return f'Imagen de {self.maquina.nombre} - {"Principal" if self.es_principal else "Secundaria"}'

    def save(self, *args, **kwargs):
        if self.es_principal:
            # Si esta imagen es principal, desmarcar las demás como principales
            ImagenMaquina.objects.filter(maquina=self.maquina).exclude(id=self.id).update(es_principal=False)
        super().save(*args, **kwargs)


class PermisoEspecial(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    archivo = models.FileField(upload_to='permisos/')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre
