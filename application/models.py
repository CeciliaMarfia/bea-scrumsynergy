from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError
from django.utils import timezone
import random
import string


class Role(models.Model):
    CLIENTE = 'cliente'
    EMPLEADO = 'empleado'
    DUENO = 'dueno'

    ROLE_CHOICES = [
        (CLIENTE, 'Cliente'),
        (EMPLEADO, 'Empleado'),
        (DUENO, 'Dueño'),
    ]

    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()


class Perfil(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil')
    dni = models.CharField(max_length=20, blank=True, null=True, unique=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    documento_foto = models.ImageField(
        upload_to='documentos/', blank=True, null=True)
    email_verificado = models.BooleanField(default=False)
    token_verificacion = models.CharField(
        max_length=100, blank=True, null=True)
    token_verificacion_expira = models.DateTimeField(null=True, blank=True)
    intentos_fallidos = models.IntegerField(default=0)
    cuenta_bloqueada = models.BooleanField(default=False)
    codigo_verificacion = models.CharField(max_length=6, blank=True, null=True)
    codigo_verificacion_expira = models.DateTimeField(null=True, blank=True)
    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, null=True, default=None)

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

    @property
    def is_dueno(self):
        return self.role and self.role.name == Role.DUENO

    @property
    def is_empleado(self):
        return self.role and self.role.name == Role.EMPLEADO

    @property
    def is_cliente(self):
        return self.role and self.role.name == Role.CLIENTE


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
        # Por defecto, asignar rol de cliente
        default_role, _ = Role.objects.get_or_create(name=Role.CLIENTE)
        Perfil.objects.create(usuario=instance, role=default_role)


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
        ('suspendida', 'Suspendida'),
        ('reservada', 'Reservada'),
        ('alquilada', 'Alquilada'),
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
    descripcion = models.TextField(
        blank=True, null=True, help_text='Descripción detallada de la maquinaria')
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

    def __str__(self):
        return f'{self.nombre} ({self.marca} - {self.modelo})'

    def clean(self):
        super().clean()
        pass

    def esta_disponible(self):
        """
        Verifica si la máquina está disponible para reservar.
        Una máquina está disponible si:
        1. Su estado base es 'disponible'
        2. No tiene reservas activas que se superpongan con la fecha actual o futuras
        """
        # Verificar si el estado base de la máquina es disponible
        if self.estado != 'disponible':
            return False

        # Verificar si hay reservas activas actuales o futuras
        hoy = timezone.now().date()
        reservas_activas = self.reservas.filter(
            estado__in=['pendiente_pago', 'pagada'],
            fecha_fin__gte=hoy
        ).exclude(
            estado='cancelada'
        ).exists()

        return not reservas_activas

    def get_proxima_disponibilidad(self):
        """
        Obtiene la fecha más próxima en que la máquina estará disponible para reservar.
        Si la máquina está reservada hasta el día X, estará disponible el día X + 3
        (considerando los 2 días de mantenimiento).
        """
        hoy = timezone.now().date()

        # Obtener todas las reservas activas futuras ordenadas por fecha de fin
        reservas_futuras = self.reservas.filter(
            estado__in=['pendiente_pago', 'pagada'],
            fecha_fin__gte=hoy
        ).exclude(
            estado='cancelada'
        ).order_by('fecha_inicio')  # Ordenar por fecha_inicio para encontrar el primer hueco disponible

        if not reservas_futuras.exists():
            # Si no hay reservas futuras y la máquina está en mantenimiento
            if self.estado == 'mantenimiento':
                return None
            return hoy

        # Buscar el primer hueco disponible entre las reservas
        fecha_disponible = hoy
        for reserva in reservas_futuras:
            # Si hay un hueco de al menos 3 días entre la fecha disponible y la próxima reserva
            if (reserva.fecha_inicio - fecha_disponible).days >= 3:
                return fecha_disponible
            # Si no hay hueco suficiente, la próxima fecha disponible será 3 días después del fin de esta reserva
            fecha_disponible = reserva.fecha_fin + timezone.timedelta(days=3)

        # Si no encontramos huecos, la fecha disponible será 3 días después de la última reserva
        return fecha_disponible

    def get_imagen_principal(self):
        return self.imagenes.filter(es_principal=True).first()

    def get_promedio_calificaciones(self):
        """
        Calcula el promedio de estrellas de todas las calificaciones.
        """
        calificaciones = self.calificaciones.all()
        if not calificaciones.exists():
            return 0
        total_estrellas = sum(c.estrellas for c in calificaciones)
        return round(total_estrellas / calificaciones.count(), 1)

    def get_cantidad_calificaciones(self):
        """
        Retorna la cantidad total de calificaciones.
        """
        return self.calificaciones.count()

    def get_calificaciones_ordenadas(self):
        """
        Retorna las calificaciones ordenadas por fecha de creación (más recientes primero).
        """
        return self.calificaciones.all().order_by('-fecha_creacion')


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
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permisos_especiales',
        null=True,  # Temporalmente permitimos nulos
        blank=True  # Temporalmente permitimos blancos
    )

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
    empleado_gestor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservas_gestionadas'
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_reserva = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendiente_pago')
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    codigo_retiro = models.CharField(max_length=8, unique=True, blank=True, null=True)

    def __str__(self):
        return f'Reserva #{self.numero_reserva} - {self.maquina.nombre}'

    @property
    def dias(self):
        """
        Calcula el número de días entre la fecha de inicio y fin de la reserva.
        El cálculo es inclusivo, es decir, si la reserva es del 1 al 3, son 3 días.
        """
        if self.fecha_inicio and self.fecha_fin:
            return (self.fecha_fin - self.fecha_inicio).days + 1
        return 0

    def clean(self):
        if self.fecha_inicio and self.fecha_fin:
            hoy = timezone.now().date()

            # Validar que la fecha de inicio no sea anterior a hoy
            if self.fecha_inicio < hoy:
                raise ValidationError({
                    'fecha_inicio': 'La fecha de inicio debe ser igual o posterior a la fecha actual.'
                })

            # Validar que la fecha de fin no sea anterior a la fecha de inicio
            if self.fecha_fin < self.fecha_inicio:
                raise ValidationError({
                    'fecha_fin': 'La fecha de fin no puede ser anterior a la fecha de inicio.'
                })

            # Validar que la reserva no exceda los 7 días
            duracion = (self.fecha_fin - self.fecha_inicio).days + 1
            if duracion > 7:
                raise ValidationError({
                    'fecha_fin': 'La reserva no puede exceder los 7 días.'
                })

            # Verificar si hay otras reservas que se solapan y el período de mantenimiento
            reservas_previas = Reserva.objects.filter(
                maquina=self.maquina,
                # Solo reservas activas
                estado__in=['pendiente_pago', 'pagada'],
                fecha_fin__gte=hoy,  # Solo reservas vigentes o futuras
            ).exclude(
                pk=self.pk if self.pk else None  # Excluir la reserva actual
            ).exclude(
                estado='cancelada'  # Excluir explícitamente las reservas canceladas
            ).order_by('fecha_inicio')

            # Si no hay reservas previas, no hay necesidad de más validaciones
            if not reservas_previas.exists():
                return

            # Verificar cada reserva previa
            for reserva in reservas_previas:
                # Verificar si la nueva reserva se solapa con una reserva existente
                if (
                    # Inicio durante otra reserva
                    (self.fecha_inicio >= reserva.fecha_inicio and self.fecha_inicio <= reserva.fecha_fin) or
                    # Fin durante otra reserva
                    (self.fecha_fin >= reserva.fecha_inicio and self.fecha_fin <= reserva.fecha_fin) or
                    (self.fecha_inicio <= reserva.fecha_inicio and self.fecha_fin >=
                     reserva.fecha_fin)  # Engloba otra reserva
                ):
                    fin_mantenimiento = reserva.fecha_fin + \
                        timezone.timedelta(days=2)
                    raise ValidationError({
                        'fecha_inicio': f'La máquina está reservada del {reserva.fecha_inicio.strftime("%d/%m/%Y")} al {reserva.fecha_fin.strftime("%d/%m/%Y")} y estará en mantenimiento hasta el {fin_mantenimiento.strftime("%d/%m/%Y")}.'
                    })

                # Verificar período de mantenimiento
                fin_mantenimiento = reserva.fecha_fin + \
                    timezone.timedelta(days=2)
                if self.fecha_inicio <= fin_mantenimiento and self.fecha_inicio > reserva.fecha_fin:
                    raise ValidationError({
                        'fecha_inicio': f'La máquina estará en mantenimiento hasta el {fin_mantenimiento.strftime("%d/%m/%Y")}.'
                    })

    def save(self, *args, **kwargs):
        if not self.numero_reserva:
            # Generar número de reserva único
            ultimo_numero = Reserva.objects.order_by('-id').first()
            if ultimo_numero:
                ultimo_id = ultimo_numero.id
            else:
                ultimo_id = 0
            self.numero_reserva = f'RES{timezone.now().strftime("%Y%m")}{str(ultimo_id + 1).zfill(4)}'

        # Generar código de retiro único si no existe
        if not self.codigo_retiro:
            while True:
                # Generar código de 8 caracteres alfanuméricos
                codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                # Verificar que no exista
                if not Reserva.objects.filter(codigo_retiro=codigo).exists():
                    self.codigo_retiro = codigo
                    break

        # Actualizar el estado de la máquina solo si es una nueva reserva o se está cancelando
        if self.pk is None:  # Nueva reserva
            self.maquina.estado = 'reservada'
            self.maquina.save()
        elif self.estado == 'cancelada':  # Cancelación
            # Verificar si hay otras reservas activas para esta máquina
            otras_reservas_activas = Reserva.objects.filter(
                maquina=self.maquina,
                estado__in=['pendiente_pago', 'pagada'],
                fecha_fin__gte=timezone.now().date()
            ).exclude(
                pk=self.pk
            ).exclude(
                estado='cancelada'
            ).exists()

            if not otras_reservas_activas:
                self.maquina.estado = 'disponible'
            self.maquina.save()

        super().save(*args, **kwargs)


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
    numero_tarjeta = models.CharField(max_length=16, null=True, blank=True)  # Número completo de la tarjeta
    ultimos_digitos = models.CharField(max_length=4)
    tipo = models.CharField(max_length=20)
    nombre_titular = models.CharField(max_length=100)
    fecha_vencimiento = models.DateField()
    es_predeterminada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarjeta de Crédito'
        verbose_name_plural = 'Tarjetas de Crédito'
        unique_together = ['usuario', 'ultimos_digitos',
                           'nombre_titular']  # Evita tarjetas duplicadas

    def __str__(self):
        return f'Tarjeta terminada en {self.ultimos_digitos} - {self.nombre_titular}'

    def save(self, *args, **kwargs):
        if self.es_predeterminada:
            # Si esta tarjeta se marca como predeterminada, desmarcar las demás
            TarjetaCredito.objects.filter(
                usuario=self.usuario
            ).exclude(id=self.id).update(es_predeterminada=False)
        super().save(*args, **kwargs)


class Sucursal(models.Model):
    calle = models.CharField(max_length=100)
    numero = models.CharField(max_length=10)
    localidad = models.CharField(max_length=100)
    provincia = models.CharField(max_length=100)
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['calle', 'numero', 'localidad', 'provincia']
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self):
        return f"{self.calle} {self.numero}, {self.localidad}, {self.provincia}"

    def get_direccion_completa(self):
        return f"{self.calle} {self.numero}, {self.localidad}, {self.provincia}"


class Pregunta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='preguntas')
    maquina = models.ForeignKey('Maquina', on_delete=models.CASCADE, related_name='preguntas', null=True, blank=True)
    texto = models.TextField()
    respuesta = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pregunta de {self.usuario.username}: {self.texto[:30]}..."


class Calificacion(models.Model):
    ESTRELLAS_CHOICES = [
        (1, '1 estrella'),
        (2, '2 estrellas'),
        (3, '3 estrellas'),
        (4, '4 estrellas'),
        (5, '5 estrellas'),
    ]

    maquina = models.ForeignKey('Maquina', on_delete=models.CASCADE, related_name='calificaciones')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calificaciones')
    estrellas = models.IntegerField(choices=ESTRELLAS_CHOICES)
    comentario = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'
        # Un usuario solo puede calificar una vez cada máquina
        unique_together = ['usuario', 'maquina']

    def __str__(self):
        return f'Calificación de {self.usuario.username} para {self.maquina.nombre}'


class ValoracionEmpleado(models.Model):
    ESTRELLAS_CHOICES = [
        (1, '1 estrella'),
        (2, '2 estrellas'),
        (3, '3 estrellas'),
        (4, '4 estrellas'),
        (5, '5 estrellas'),
    ]

    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='valoraciones_recibidas')
    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='valoraciones_empleados')
    reserva = models.ForeignKey('Reserva', on_delete=models.CASCADE, related_name='valoraciones_empleado')
    estrellas = models.IntegerField(choices=ESTRELLAS_CHOICES)
    comentario = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Valoración de Empleado'
        verbose_name_plural = 'Valoraciones de Empleados'
        # Un cliente solo puede valorar una vez cada empleado por reserva
        unique_together = ['cliente', 'empleado', 'reserva']

    def __str__(self):
        return f'Valoración de {self.cliente.username} para {self.empleado.get_full_name()}'

    def get_promedio_valoraciones(self):
        """Obtiene el promedio de valoraciones del empleado"""
        valoraciones = ValoracionEmpleado.objects.filter(empleado=self.empleado)
        if valoraciones.exists():
            return valoraciones.aggregate(models.Avg('estrellas'))['estrellas__avg']
        return 0

    def get_cantidad_valoraciones(self):
        """Obtiene la cantidad de valoraciones del empleado"""
        return ValoracionEmpleado.objects.filter(empleado=self.empleado).count()

    def get_valoraciones_ordenadas(self):
        """Obtiene las valoraciones del empleado ordenadas por fecha"""
        return ValoracionEmpleado.objects.filter(empleado=self.empleado).order_by('-fecha_creacion')
