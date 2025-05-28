from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError
from django.utils import timezone


class Perfil(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil')
    dni = models.CharField(max_length=20)
    direccion = models.TextField()
    fecha_nacimiento = models.DateField()
    celular = models.CharField(max_length=20, blank=True, null=True)
    documento_foto = models.ImageField(upload_to='documentos/')
    email_verificado = models.BooleanField(default=False)
    token_verificacion = models.CharField(
        max_length=100, blank=True, null=True)
    intentos_fallidos = models.IntegerField(default=0)
    cuenta_bloqueada = models.BooleanField(default=False)
    codigo_verificacion = models.CharField(max_length=6, blank=True, null=True)
    codigo_verificacion_expira = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Perfil de {self.usuario.username}'

    def incrementar_intentos_fallidos(self):
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= 3:
            self.cuenta_bloqueada = True
        self.save()

    def reiniciar_intentos_fallidos(self):
        self.intentos_fallidos = 0
        self.save()


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

    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('reservado', 'Reservado'),
        ('alquilado', 'Alquilado'),
        ('mantenimiento', 'En Mantenimiento'),
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
    permisos_requeridos = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='disponible')
    stock = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.nombre} ({self.marca} - {self.modelo})'

    def clean(self):
        super().clean()
        # La validación de imágenes se manejará en el formulario
        pass

    def esta_disponible(self):
        return self.estado == 'disponible' and self.stock > 0

    def get_imagen_principal(self):
        return self.imagenes.filter(es_principal=True).first()


class ImagenMaquina(models.Model):
    maquina = models.ForeignKey(
        Maquina,
        related_name='imagenes',
        on_delete=models.CASCADE
    )
    imagen = models.ImageField(
        upload_to='imagenes_maquinas/',
        verbose_name='Imagen',
        help_text='Formato permitido: JPG, PNG. Tamaño máximo: 5MB'
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name='Imagen principal'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagen de maquinaria'
        verbose_name_plural = 'Imágenes de maquinaria'
        ordering = ['-es_principal', '-fecha_subida']

    def __str__(self):
        return f'Imagen de {self.maquina.nombre} - {"Principal" if self.es_principal else "Secundaria"}'

    def save(self, *args, **kwargs):
        # Si es la primera imagen de la máquina, hacerla principal
        if not self.pk and not self.maquina.imagenes.exists():
            self.es_principal = True
        elif self.es_principal:
            # Si esta imagen es principal, desmarcar las demás
            ImagenMaquina.objects.filter(
                maquina=self.maquina
            ).exclude(id=self.id).update(es_principal=False)
        super().save(*args, **kwargs)


class PermisoEspecial(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    archivo = models.FileField(upload_to='permisos/')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Reserva(models.Model):
    ESTADO_CHOICES = [
        ('pendiente_pago', 'Pendiente de pago'),
        ('pagada', 'Pagada'),
        ('cancelada', 'Cancelada'),
        ('finalizada', 'Finalizada'),
    ]

    numero_reserva = models.CharField(max_length=20, unique=True)
    maquina = models.ForeignKey(
        Maquina, on_delete=models.CASCADE, related_name='reservas')
    cliente = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reservas')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_reserva = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendiente_pago')
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'Reserva #{self.numero_reserva} - {self.maquina.nombre}'

    def save(self, *args, **kwargs):
        if not self.numero_reserva:
            # Generar número de reserva único
            ultimo_numero = Reserva.objects.order_by('-id').first()
            if ultimo_numero:
                ultimo_id = ultimo_numero.id
            else:
                ultimo_id = 0
            self.numero_reserva = f'RES{timezone.now().strftime("%Y%m")}{str(ultimo_id + 1).zfill(4)}'

        if self.pk is None:  # Si es una nueva reserva
            self.maquina.stock -= 1
            if self.maquina.stock == 0:
                self.maquina.estado = 'reservado'
            self.maquina.save()

        super().save(*args, **kwargs)

    def clean(self):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio < timezone.now().date():
                raise ValidationError(
                    'La fecha de inicio no puede ser anterior a la fecha actual.')
            if self.fecha_fin < self.fecha_inicio:
                raise ValidationError(
                    'La fecha de fin no puede ser anterior a la fecha de inicio.')


class Pago(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('exitoso', 'Exitoso'),
        ('fallido', 'Fallido')
    ]

    MOTIVO_FALLO_CHOICES = [
        ('tarjeta_invalida', 'Tarjeta inválida'),
        ('fondos_insuficientes', 'Fondos insuficientes'),
        ('error_conexion', 'Error de conexión con el banco'),
        ('otro', 'Otro error')
    ]

    reserva = models.OneToOneField(
        'Reserva',
        on_delete=models.CASCADE,
        related_name='pago'
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente'
    )
    motivo_fallo = models.CharField(
        max_length=50,
        choices=MOTIVO_FALLO_CHOICES,
        null=True,
        blank=True
    )
    numero_transaccion = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    def __str__(self):
        return f'Pago {self.id} - Reserva {self.reserva.numero_reserva}'

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'


class TarjetaCredito(models.Model):
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='tarjetas')
    ultimos_digitos = models.CharField(max_length=4)
    tipo = models.CharField(max_length=20)
    nombre_titular = models.CharField(max_length=100)
    fecha_vencimiento = models.DateField()
    es_predeterminada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarjeta de Crédito'
        verbose_name_plural = 'Tarjetas de Crédito'

    def __str__(self):
        return f'Tarjeta terminada en {self.ultimos_digitos} - {self.nombre_titular}'

    def save(self, *args, **kwargs):
        if self.es_predeterminada:
            # Si esta tarjeta se marca como predeterminada, desmarcar las demás
            TarjetaCredito.objects.filter(
                usuario=self.usuario
            ).exclude(id=self.id).update(es_predeterminada=False)
        super().save(*args, **kwargs)
