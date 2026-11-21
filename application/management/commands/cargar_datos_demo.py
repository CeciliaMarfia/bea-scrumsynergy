import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from application.models import ImagenMaquina, Maquina, Reserva, Role, Sucursal

CLAVE = 'Bob12345!'


class Command(BaseCommand):
    help = 'Carga usuarios, maquinaria, reservas y alquileres de ejemplo para probar el sistema'

    def crear_usuario(self, email, nombre, apellido, rol):
        usuario = User.objects.create_user(
            username=email, email=email, password=CLAVE, first_name=nombre, last_name=apellido)
        usuario.perfil.role, _ = Role.objects.get_or_create(name=rol)
        usuario.perfil.email_verificado = True
        usuario.perfil.save()
        return usuario

    def crear_maquina(self, codigo, nombre, marca, modelo, tipo, precio, imagen):
        maquina = Maquina.objects.create(
            codigo=codigo, nombre=nombre, marca=marca, modelo=modelo, anio=2021,
            ubicacion='Calle 7 1234, La Plata, Buenos Aires', tipo=tipo,
            precio_por_dia=Decimal(precio), tipo_cancelacion='total',
            descripcion=f'{nombre} en excelente estado, con mantenimiento al día.')
        ImagenMaquina.objects.create(
            maquina=maquina, imagen=f'imagenes_maquinas/{imagen}', es_principal=True)
        return maquina

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username='dueno@bob.com').exists():
            self.stdout.write(self.style.WARNING('Los datos de ejemplo ya estaban cargados.'))
            return

        for rol, _ in Role.ROLE_CHOICES:
            Role.objects.get_or_create(name=rol)

        Sucursal.objects.get_or_create(
            calle='Calle 7', numero='1234', localidad='La Plata', provincia='Buenos Aires',
            defaults={'latitud': -34.9214, 'longitud': -57.9545})

        self.crear_usuario('dueno@bob.com', 'Roberto', 'Paredes', Role.DUENO)
        empleado = self.crear_usuario('empleado@bob.com', 'Laura', 'Gómez', Role.EMPLEADO)
        ana = self.crear_usuario('ana@mail.com', 'Ana', 'López', Role.CLIENTE)
        beto = self.crear_usuario('beto@mail.com', 'Beto', 'Díaz', Role.CLIENTE)

        tractor = self.crear_maquina('M001', 'Tractor John Deere', 'John Deere', '5075E',
                                     'agricola', '45000', 'Tractor_2.jpg')
        sembradora = self.crear_maquina('M002', 'Sembradora', 'Agrometal', 'TX Mega',
                                        'agricola', '30000', 'Sembradora_2.jpg')
        excavadora = self.crear_maquina('M003', 'Excavadora', 'Caterpillar', '320',
                                        'mineria', '90000', 'Mineria_2.jpg')
        cortadora = self.crear_maquina('M004', 'Cortadora de césped', 'Husqvarna', 'LC 140',
                                       'jardineria', '8000', 'Jardinería-1.1.jpg')

        hoy = timezone.localdate()
        dia = datetime.timedelta(days=1)

        def reserva(maquina, cliente, inicio, fin, estado, **extra):
            return Reserva.objects.create(
                maquina=maquina, cliente=cliente, fecha_inicio=inicio, fecha_fin=fin,
                estado=estado, monto_total=maquina.precio_por_dia * ((fin - inicio).days + 1), **extra)

        para_retirar = reserva(tractor, ana, hoy, hoy + 2 * dia, 'pagada')
        futura = reserva(sembradora, ana, hoy + 10 * dia, hoy + 12 * dia, 'pagada')
        sin_pagar = reserva(cortadora, ana, hoy + 5 * dia, hoy + 6 * dia, 'pendiente_pago')
        alquiler = reserva(excavadora, beto, hoy - dia, hoy + 2 * dia, 'pagada',
                           tipo=Reserva.TIPO_ALQUILER, fecha_retiro=timezone.now() - dia,
                           empleado_gestor=empleado)

        self.stdout.write(self.style.SUCCESS('\nDatos de ejemplo cargados.\n'))
        self.stdout.write(f'Contraseña de todos los usuarios: {CLAVE}')
        self.stdout.write('  Dueño:    dueno@bob.com')
        self.stdout.write('  Empleado: empleado@bob.com')
        self.stdout.write('  Clientes: ana@mail.com, beto@mail.com\n')
        self.stdout.write(f'Reserva pagada de Ana que empieza hoy ({tractor.nombre}): código de retiro {para_retirar.codigo_retiro}')
        self.stdout.write(f'Reserva pagada de Ana que empieza en 10 días ({sembradora.nombre}): código de retiro {futura.codigo_retiro}')
        self.stdout.write(f'Reserva de Ana pendiente de pago ({cortadora.nombre}): {sin_pagar.numero_reserva}')
        self.stdout.write(f'Alquiler en curso de Beto ({excavadora.nombre}): código de máquina {excavadora.codigo}')
