import mercadopago
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
import os
from django.conf import settings
from .machinery.forms import AltaMaquinariaForm, RegistrarDevolucionForm
from .models import Maquina, HomeVideo, PermisoEspecial, Perfil, Reserva, ImagenMaquina, Pago, TarjetaCredito, Role, Sucursal, Pregunta, Calificacion, ValoracionEmpleado
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .forms import RegistroUsuarioForm, PermisoEspecialForm, EditarPerfilForm, ReservaMaquinariaForm, TarjetaCreditoForm, CambiarPasswordForm, ResponderPreguntaForm, ContactForm, CalificacionForm, AlquilerPresencialForm, ValoracionEmpleadoForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.contrib.auth.tokens import default_token_generator
import random
import string
import uuid
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from .services import BancoService
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import datetime, timedelta
import json
import stripe
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from dotenv import load_dotenv
from django.utils.http import urlencode
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
import os
from django.views.decorators.http import require_http_methods
load_dotenv
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')

# SDK de Mercado Pago
# Agrega credenciales
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)


def home(request):
    # Limpiar mensajes solo si es una petición GET directa (no redirección)
    if request.method == 'GET' and not request.META.get('HTTP_REFERER'):
        list(request._messages)
    video_activo = HomeVideo.objects.filter(activo=True).first()
    return render(request, 'home.html', {'video': video_activo})


def login(request):
    if request.method == 'POST':
        # El campo se llama username en el form pero contiene el email
        email = request.POST.get('username')
        password = request.POST.get('password')

        try:
            # Primero intentamos autenticar al usuario
            user_auth = authenticate(
                request, username=email, password=password)

            # Si la autenticación falla, verificamos si el usuario existe
            if user_auth is None:
                try:
                    user = User.objects.get(email=email)
                    # El usuario existe pero la contraseña es incorrecta
                    user.perfil.incrementar_intentos_fallidos()
                    mensaje = 'Usuario o contraseña incorrectos'
                    if user.perfil.cuenta_bloqueada:
                        mensaje = 'Por motivos de seguridad, tu cuenta ha sido temporalmente suspendida. Por favor, contacta con soporte para más información.'
                    return render(request, 'login.html', {
                        'error_message': mensaje
                    })
                except User.DoesNotExist:
                    # El usuario no existe
                    return render(request, 'login.html', {
                        'error_message': 'Usuario o contraseña incorrectos'
                    })

            # Si llegamos aquí, la autenticación fue exitosa
            # Verificar si la cuenta está bloqueada
            if user_auth.perfil.cuenta_bloqueada:
                return render(request, 'login.html', {
                    'error_message': 'Por motivos de seguridad, tu cuenta ha sido temporalmente suspendida. Por favor, contacta con soporte para más información.'
                })

            # Verificar si el email está verificado
            if not user_auth.perfil.email_verificado:
                return render(request, 'login.html', {
                    'error_message': 'Por favor, verifica tu correo electrónico antes de iniciar sesión.',
                    'show_verification_resend': True,
                    'unverified_email': email
                })

            # Generar código de verificación de 6 dígitos
            codigo = ''.join(random.choices(string.digits, k=6))
            user_auth.perfil.codigo_verificacion = codigo
            user_auth.perfil.codigo_verificacion_expira = timezone.now() + \
                timezone.timedelta(minutes=5)
            user_auth.perfil.reiniciar_intentos_fallidos()
            user_auth.perfil.save()

            # Enviar código por email
            subject = 'Código de verificación - Bob el Alquilador'
            html_message = render_to_string('emails/codigo_verificacion.html', {
                'user': user_auth,
                'codigo': codigo,
            })
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user_auth.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                # Guardar el usuario en la sesión temporalmente
                request.session['temp_user_id'] = user_auth.id
                return redirect('verificar_codigo')
            except Exception as e:
                print(f"Error al enviar correo de verificación: {str(e)}")
                return render(request, 'login.html', {
                    'error_message': 'Error al enviar el código de verificación. Por favor, intenta nuevamente.'
                })

        except Exception as e:
            print(f"Error durante el inicio de sesión: {str(e)}")
            return render(request, 'login.html', {
                'error_message': 'Ha ocurrido un error. Por favor, intenta nuevamente.'
            })

    return render(request, 'login.html')


def verificar_codigo(request):
    user_id = request.session.get('temp_user_id')
    if not user_id:
        return redirect('login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo')

        if not user.perfil.codigo_verificacion or timezone.now() > user.perfil.codigo_verificacion_expira:
            messages.error(
                request, 'El código ha expirado. Por favor, inicia sesión nuevamente.')
            return redirect('login')

        if codigo_ingresado == user.perfil.codigo_verificacion:
            # Limpiar código y sesión temporal
            user.perfil.codigo_verificacion = None
            user.perfil.codigo_verificacion_expira = None
            user.perfil.save()
            del request.session['temp_user_id']

            # Iniciar sesión
            auth_login(request, user)
            messages.success(
                request, f'¡Bienvenido/a de nuevo, {user.first_name}!')
            return redirect('home')
        else:
            messages.error(
                request, 'Código incorrecto. Por favor, intenta nuevamente.')

    return render(request, 'verificar_codigo.html')


def signup(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            # Crear usuario pero no autenticar automáticamente
            user = form.save()

            # Generar token de verificación
            token = str(uuid.uuid4())
            user.perfil.token_verificacion = token
            # Establecer la expiración del token a 5 minutos desde ahora
            user.perfil.token_verificacion_expira = timezone.now() + \
                timezone.timedelta(minutes=5)
            user.perfil.save()

            # Obtener el dominio actual
            current_site = get_current_site(request)
            # Construir la URL de verificación
            verification_url = f"http://{current_site.domain}{reverse('verificar_email', args=[token])}"

            # Enviar correo de verificación
            subject = 'Verifica tu cuenta - Bob el Alquilador'
            html_message = render_to_string('emails/verificacion.html', {
                'user': user,
                'verification_url': verification_url,
            })
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(
                    request,
                    'Tu cuenta ha sido creada. Por favor, revisa tu correo electrónico para verificar tu cuenta. El enlace expirará en 24 horas.'
                )
                return render(request, 'login.html', {
                    'show_verification_resend': True,
                    'unverified_email': user.email,
                    'registration_success': True
                })
            except Exception as e:
                print(f"Error al enviar correo de verificación: {str(e)}")
                messages.error(
                    request,
                    'Hubo un problema al enviar el correo de verificación. Por favor, contacta al soporte.'
                )
                return render(request, 'login.html', {
                    'show_verification_resend': True,
                    'unverified_email': user.email
                })

            return redirect('login')
    else:
        form = RegistroUsuarioForm()

    return render(request, 'signup.html', {'form': form})


def verificar_email(request, token):
    try:
        perfil = Perfil.objects.get(token_verificacion=token)

        # Verificar si el token ha expirado
        if perfil.token_verificacion_expira and timezone.now() > perfil.token_verificacion_expira:
            messages.error(
                request, 'El enlace de verificación ha expirado. Por favor, solicita uno nuevo.')
            return render(request, 'login.html', {
                'show_verification_resend': True,
                'unverified_email': perfil.usuario.email
            })

        if not perfil.email_verificado:
            perfil.email_verificado = True
            perfil.token_verificacion = None  # Invalidar el token después de usarlo
            perfil.token_verificacion_expira = None
            perfil.save()
            messages.success(
                request, '¡Tu cuenta ha sido verificada exitosamente! Ahora puedes iniciar sesión.')
        else:
            messages.info(
                request, 'Esta cuenta ya ha sido verificada anteriormente.')
    except Perfil.DoesNotExist:
        messages.error(request, 'El enlace de verificación no es válido.')

    return redirect('login')

# -- Codigo HU "Alta Maquinaria" --


DATA_PATH = os.path.join(settings.BASE_DIR, 'templatesMachine', 'machinery')


def is_owner(user):
    return user.is_authenticated and user.perfil.is_dueno


def is_owner_or_employee(user):
    return user.is_authenticated and (user.perfil.is_dueno or user.perfil.is_empleado)


@login_required
@user_passes_test(is_owner)
def registrar_empleado(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(
            request.POST, request.FILES, is_employee=True)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Asegurarnos de que el rol de empleado se asigne correctamente
                role, _ = Role.objects.get_or_create(name=Role.EMPLEADO)
                user.perfil.role = role

                # Generar token de verificación
                token = str(uuid.uuid4())
                user.perfil.token_verificacion = token
                user.perfil.token_verificacion_expira = timezone.now() + \
                    timezone.timedelta(minutes=5)
                user.perfil.save()

                # Obtener el dominio actual y construir la URL de verificación
                current_site = get_current_site(request)
                verification_url = f"http://{current_site.domain}{reverse('verificar_email', args=[token])}"

                # Enviar correo de verificación
                subject = 'Verifica tu cuenta - Bob el Alquilador'
                html_message = render_to_string('emails/verificacion.html', {
                    'user': user,
                    'verification_url': verification_url,
                })
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject,
                        plain_message,
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        'Empleado registrado exitosamente. Se ha enviado un correo de verificación.'
                    )
                except Exception as e:
                    messages.warning(
                        request,
                        'Empleado registrado, pero hubo un problema al enviar el correo de verificación.'
                    )
                return redirect('lista_empleados')
    else:
        form = RegistroUsuarioForm(is_employee=True)

    return render(request, 'registration/registrar_empleado.html', {'form': form})


@login_required
@user_passes_test(is_owner)
def lista_empleados(request):
    # Filtrar usuarios que tengan el rol de empleado y estén verificados
    empleados = User.objects.filter(
        perfil__role__name=Role.EMPLEADO,
        perfil__email_verificado=True
    ).order_by('first_name', 'last_name')
    return render(request, 'registration/lista_empleados.html', {'empleados': empleados})


@login_required
@user_passes_test(is_owner)
def eliminar_empleado(request, empleado_id):
    empleado = get_object_or_404(
        User, id=empleado_id, perfil__role__name=Role.EMPLEADO)
    if request.method == 'POST':
        empleado.delete()
        messages.success(request, 'Empleado eliminado exitosamente.')
    return redirect('lista_empleados')


@login_required
@user_passes_test(is_owner)
def registrar_maquinaria(request):
    if request.method == 'POST':
        form = AltaMaquinariaForm(request.POST, request.FILES)
        if form.is_valid():
            maquina = form.save()
            messages.success(request, 'Maquinaria registrada exitosamente.')
            return redirect('home')
        # Si no es válido, sigue y renderiza el formulario con errores
    else:
        form = AltaMaquinariaForm()
    return render(request, 'templatesMachine/machinery_registration.html', {'form': form})


@login_required
@user_passes_test(is_owner_or_employee)
def historial_reservas(request):
    # Filtrar solo reservas activas (pendientes de pago y pagadas)
    reservas = Reserva.objects.filter(
        estado__in=['pendiente_pago', 'pagada']
    ).order_by('fecha_inicio')  # Ordenar por fecha de inicio
    return render(request, 'reservas/historial.html', {'reservas': reservas})


@login_required
@user_passes_test(is_owner_or_employee)
def registrar_cliente(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Asegurarnos de que el rol de cliente se asigne correctamente
                role, _ = Role.objects.get_or_create(name=Role.CLIENTE)
                user.perfil.role = role
                user.perfil.email_verificado = True  # El empleado verifica al cliente
                user.perfil.save()

                messages.success(request, 'Cliente registrado exitosamente.')
                return redirect('lista_clientes')
    else:
        form = RegistroUsuarioForm()

    return render(request, 'registration/registrar_cliente.html', {'form': form})


@login_required
@user_passes_test(is_owner_or_employee)
def lista_clientes(request):
    # Filtrar usuarios que tengan el rol de cliente y estén verificados
    clientes = User.objects.filter(
        perfil__role__name=Role.CLIENTE,
        perfil__email_verificado=True
    ).order_by('first_name', 'last_name')
    return render(request, 'registration/lista_clientes.html', {'clientes': clientes})


@login_required
@user_passes_test(is_owner_or_employee)
def ver_perfil_cliente(request, cliente_id):
    cliente = get_object_or_404(
        User, id=cliente_id, perfil__role__name=Role.CLIENTE)
    # Get all reservations ordered by date using the correct related name
    reservas = cliente.reservas.all().order_by('-fecha_reserva')
    # Get all permisos especiales for the client
    permisos = cliente.permisos_especiales.all().order_by('-fecha_creacion')
    return render(request, 'registration/ver_perfil_cliente.html', {
        'cliente': cliente,
        'reservas': reservas,
        'permisos': permisos
    })

# -- fin codigo --


@login_required
def logout(request):
    auth_logout(request)
    messages.success(request, '¡Has cerrado sesión exitosamente!')
    return redirect('home')


@login_required
def agregar_permiso(request):
    if request.method == 'POST':
        form = PermisoEspecialForm(request.POST, request.FILES)
        if form.is_valid():
            permiso = form.save(commit=False)
            permiso.usuario = request.user
            permiso.save()
            messages.success(request, 'Permiso agregado exitosamente.')
            return redirect('perfil')
    else:
        form = PermisoEspecialForm()
    return render(request, 'permisos/agregar_permiso.html', {'form': form})


@login_required
def lista_permisos(request):
    permisos = PermisoEspecial.objects.all().order_by('-fecha_creacion')
    return render(request, 'permisos/lista_permisos.html', {'permisos': permisos})


@login_required
def perfil(request):
    permisos = PermisoEspecial.objects.all().order_by('-fecha_creacion')
    user = request.user
    # Asegurarse de que el perfil existe
    perfil, created = Perfil.objects.get_or_create(usuario=user)
    return render(request, 'perfil.html', {
        'permisos': permisos,
        'user': user,
        'perfil': perfil
    })


@login_required
def editar_perfil(request):
    if request.method == 'POST':
        if 'cambiar_password' in request.POST:
            password_form = CambiarPasswordForm(request.user, request.POST)
            profile_form = EditarPerfilForm(
                instance=request.user, user=request.user)
            if password_form.is_valid():
                password_form.save()
                messages.success(
                    request, 'Tu contraseña ha sido actualizada exitosamente.')
                return redirect('perfil')
        else:
            password_form = CambiarPasswordForm(request.user)
            profile_form = EditarPerfilForm(
                request.POST, request.FILES, instance=request.user, user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Perfil actualizado exitosamente.')
                return redirect('perfil')
            else:
                # Si hay errores, mostrarlos como mensajes
                for field, errors in profile_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{error}')
    else:
        password_form = CambiarPasswordForm(request.user)
        profile_form = EditarPerfilForm(
            instance=request.user, user=request.user)

    return render(request, 'editar_perfil.html', {
        'form': profile_form,
        'password_form': password_form
    })


@login_required
def eliminar_permiso(request, permiso_id):
    permiso = get_object_or_404(PermisoEspecial, id=permiso_id)
    nombre_permiso = permiso.nombre
    permiso.delete()
    messages.success(
        request, f'El permiso "{nombre_permiso}" ha sido eliminado.')
    return redirect('perfil')


class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    success_url = reverse_lazy('password_reset_done')
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'

    def generate_random_password(self, length=12):
        """Genera una contraseña aleatoria segura."""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            password = ''.join(random.choice(characters)
                               for i in range(length))
            # Verifica que la contraseña cumple con los requisitos mínimos
            if (any(c.islower() for c in password)
                    and any(c.isupper() for c in password)
                    and any(c.isdigit() for c in password)
                    and any(c in "!@#$%^&*" for c in password)):
                return password

    def form_valid(self, form):
        """
        Genera una contraseña aleatoria y la envía por correo electrónico.
        Siempre muestra el mismo mensaje de éxito, independientemente de si el correo existe o no.
        """
        email = form.cleaned_data["email"]
        try:
            user = User.objects.get(email=email)
            # Genera una nueva contraseña aleatoria
            new_password = self.generate_random_password()
            # Establece la nueva contraseña
            user.set_password(new_password)
            user.save()

            # Preparar el correo
            subject = "Nueva contraseña - Bob el Alquilador"

            # Versión HTML del correo
            html_message = render_to_string('registration/password_reset_email.html', {
                'user': user,
                'new_password': new_password,
            })

            # Versión de texto plano del correo (como respaldo)
            plain_message = strip_tags(html_message)

            # Enviar el correo priorizando la versión HTML
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[email]
            )
            email_message.attach_alternative(html_message, "text/html")
            email_message.mixed_subtype = 'related'
            email_message.send()

        except User.DoesNotExist:
            # No hacemos nada si el usuario no existe
            pass
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")  # Para debugging

        # Redirigir a la página de éxito sin llamar al super().form_valid()
        return redirect(self.success_url)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'


def reenviar_verificacion(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            if not user.perfil.email_verificado:
                # Generar nuevo token de verificación
                token = str(uuid.uuid4())
                user.perfil.token_verificacion = token
                # Establecer la expiración del token a 5 minutos desde ahora
                user.perfil.token_verificacion_expira = timezone.now() + \
                    timezone.timedelta(minutes=5)
                user.perfil.save()

                # Obtener el dominio actual
                current_site = get_current_site(request)
                # Construir la URL de verificación
                verification_url = f"http://{current_site.domain}{reverse('verificar_email', args=[token])}"

                # Enviar correo de verificación
                subject = 'Verifica tu cuenta - Bob el Alquilador'
                html_message = render_to_string('emails/verificacion.html', {
                    'user': user,
                    'verification_url': verification_url,
                })
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject,
                        plain_message,
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        'Hemos enviado un nuevo correo de verificación. Por favor, revisa tu bandeja de entrada. El enlace expirará en 24 horas.'
                    )
                except Exception as e:
                    print(f"Error al enviar correo de verificación: {str(e)}")
                    messages.error(
                        request,
                        'Hubo un problema al enviar el correo de verificación. Por favor, intenta nuevamente más tarde.'
                    )
            else:
                messages.info(request, 'Esta cuenta ya ha sido verificada.')
        except User.DoesNotExist:
            messages.error(
                request, 'No existe una cuenta con ese correo electrónico.')

    return redirect('login')


@login_required
def reservar_maquinaria(request, maquina_id):
    maquina = get_object_or_404(Maquina, id=maquina_id)
    proxima_disponibilidad = maquina.get_proxima_disponibilidad()

    if request.method == 'POST':
        form = ReservaMaquinariaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.cliente = request.user
            reserva.maquina = maquina

            # Si quien crea la reserva es un empleado, registrarlo como gestor
            if request.user.perfil.is_empleado:
                reserva.empleado_gestor = request.user

            # Calcular el monto total
            dias = (form.cleaned_data['fecha_fin'] -
                    form.cleaned_data['fecha_inicio']).days + 1
            reserva.monto_total = maquina.precio_por_dia * dias

            try:
                with transaction.atomic():
                    reserva.save()
                    # Cambiar el estado de la máquina a 'reservada'
                    maquina.estado = 'reservada'
                    maquina.save()
                    messages.success(
                        request, f'Reserva creada exitosamente. Número de reserva: {reserva.numero_reserva}')
                    return redirect('mis_reservas')
            except Exception as e:
                messages.error(
                    request, 'Error al crear la reserva. Por favor, intente nuevamente.')
                return redirect('detalle_maquinaria', maquina_id=maquina.id)
    else:
        initial_data = {
            'maquina': maquina,
            'fecha_inicio': proxima_disponibilidad
        }
        form = ReservaMaquinariaForm(initial=initial_data)

    return render(request, 'reserva/reservar_maquinaria.html', {
        'form': form,
        'maquina': maquina,
        'proxima_disponibilidad': proxima_disponibilidad
    })


def lista_maquinaria(request):
    # Obtener todas las máquinas excepto las suspendidas
    maquinas = Maquina.objects.exclude(estado='suspendida')

    # Nueva funcionalidad: búsqueda por nombre
    busqueda_nombre = request.GET.get('busqueda_nombre', '').strip()
    resultados_busqueda = None
    mensaje_busqueda = None
    if busqueda_nombre:
        resultados_busqueda = Maquina.objects.exclude(estado='suspendida').filter(
            nombre__icontains=busqueda_nombre)
        if not resultados_busqueda.exists():
            mensaje_busqueda = f"No hay resultados para '{busqueda_nombre}'"

    # Aplicar filtros si se proporcionan
    tipo = request.GET.get('tipo')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')
    ubicacion = request.GET.get('ubicacion')

    if tipo:
        maquinas = maquinas.filter(tipo=tipo)
    if precio_min:
        maquinas = maquinas.filter(precio_por_dia__gte=precio_min)
    if precio_max:
        maquinas = maquinas.filter(precio_por_dia__lte=precio_max)
    if ubicacion:
        maquinas = maquinas.filter(ubicacion__icontains=ubicacion)

    # Obtener valores únicos para los filtros
    tipos = Maquina.TIPO_CHOICES
    ubicaciones = Maquina.objects.exclude(estado='suspendida').values_list(
        'ubicacion', flat=True).distinct()

    # Calcular conteos para los filtros (ahora excluye máquinas suspendidas)
    tipos_con_conteo = {}
    for tipo_value, tipo_label in tipos:
        tipos_con_conteo[tipo_value] = Maquina.objects.exclude(estado='suspendida').filter(
            tipo=tipo_value).count()

    ubicaciones_con_conteo = {}
    for ubi in ubicaciones:
        if ubi:  # Solo si la ubicación no es None o vacía
            ubicaciones_con_conteo[ubi] = Maquina.objects.exclude(estado='suspendida').filter(
                ubicacion=ubi).count()

    # Calcular próxima disponibilidad para cada máquina
    hoy = timezone.now().date()
    maquinas_info = []
    for maquina in maquinas:
        proxima_disponibilidad = None
        if not maquina.esta_disponible():
            proxima_disponibilidad = maquina.get_proxima_disponibilidad()

        maquinas_info.append({
            'maquina': maquina,
            'proxima_disponibilidad': proxima_disponibilidad
        })

    # Para los resultados de búsqueda, armar la misma estructura que maquinas_info
    resultados_info = []
    if resultados_busqueda is not None:
        for maquina in resultados_busqueda:
            proxima_disponibilidad = None
            if not maquina.esta_disponible():
                proxima_disponibilidad = maquina.get_proxima_disponibilidad()
            resultados_info.append({
                'maquina': maquina,
                'proxima_disponibilidad': proxima_disponibilidad
            })

    context = {
        'maquinas_info': maquinas_info,
        'tipos': tipos,
        'ubicaciones': ubicaciones,
        'tipos_con_conteo': tipos_con_conteo,
        'ubicaciones_con_conteo': ubicaciones_con_conteo,
        'filtros': {
            'tipo': tipo,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'ubicacion': ubicacion,
        },
        'user_authenticated': request.user.is_authenticated,
        'busqueda_nombre': busqueda_nombre,
        'resultados_info': resultados_info,
        'mensaje_busqueda': mensaje_busqueda,
    }

    return render(request, 'listados/lista_maquinaria.html', context)


@login_required
def mis_reservas(request):
    # Obtener solo las reservas reales (excluyendo errores)
    reservas = Reserva.objects.filter(
        cliente=request.user,
        numero_reserva__isnull=False  # Asegurarse de que tenga número de reserva
    ).order_by('-fecha_reserva')

    return render(request, 'reserva/mis_reservas.html', {
        'reservas': reservas
    })


def detalle_maquinaria(request, maquina_id):
    try:
        maquina = Maquina.objects.get(id=maquina_id)
        
        # Si la máquina está suspendida y el usuario no es dueño, redirigir al catálogo
        if maquina.estado == 'suspendida' and not (request.user.is_authenticated and request.user.perfil.is_dueno):
            messages.warning(request, 'Esta máquina no está disponible actualmente.')
            return redirect('lista_maquinaria')

        proxima_disponibilidad = None
        if not maquina.esta_disponible():
            proxima_disponibilidad = maquina.get_proxima_disponibilidad()

        context = {
            'maquina': maquina,
            'proxima_disponibilidad': proxima_disponibilidad,
        }
        return render(request, 'listados/detalle_maquinaria.html', context)
    except Maquina.DoesNotExist:
        messages.error(request, 'La máquina solicitada no existe.')
        return redirect('lista_maquinaria')


@login_required
def cancelar_reserva(request, numero_reserva):
    # Si es empleado o dueño, puede cancelar cualquier reserva
    if is_owner_or_employee(request.user):
        reserva = get_object_or_404(Reserva, numero_reserva=numero_reserva)
    else:
        # Si es cliente, solo puede cancelar sus propias reservas
        reserva = get_object_or_404(
            Reserva, numero_reserva=numero_reserva, cliente=request.user)

    if request.method == 'POST':
        if reserva.estado not in ['cancelada', 'finalizada']:
            try:
                with transaction.atomic():
                    # Guardar el estado anterior para saber si estaba pagada
                    estaba_pagada = reserva.estado == 'pagada'

                    # Actualizar el estado de la reserva
                    reserva.estado = 'cancelada'
                    reserva.save()

                    # Actualizar el estado de la máquina
                    maquina = reserva.maquina
                    maquina.estado = 'disponible'
                    maquina.save()

                    # Preparar y enviar el correo electrónico
                    subject = 'Cancelación de Reserva - Bob el Alquilador'

                    # Determinar quién canceló la reserva
                    cancelador = "usted mismo"
                    if is_owner_or_employee(request.user) and request.user != reserva.cliente:
                        cancelador = "un representante de Bob el Alquilador"

                    context = {
                        'cliente': reserva.cliente,
                        'numero_reserva': reserva.numero_reserva,
                        'maquina': reserva.maquina.nombre,
                        'fecha_inicio': reserva.fecha_inicio,
                        'fecha_fin': reserva.fecha_fin,
                        'estaba_pagada': estaba_pagada,
                        'cancelador': cancelador
                    }

                    html_message = render_to_string(
                        'emails/cancelacion_reserva.html', context)
                    plain_message = strip_tags(html_message)

                    send_mail(
                        subject,
                        plain_message,
                        settings.EMAIL_HOST_USER,
                        [reserva.cliente.email],
                        html_message=html_message,
                        fail_silently=False,
                    )

                    messages.error(
                        request, f'La reserva con código {numero_reserva} ha sido cancelada.')
            except Exception as e:
                messages.error(
                    request, 'Hubo un error al cancelar la reserva. Por favor, intente nuevamente.')
        else:
            messages.error(request, 'Esta reserva no puede ser cancelada.')

    # Siempre redirigir a mis_reservas, independientemente del tipo de usuario
    return redirect('mis_reservas')


@login_required
def eliminar_perfil(request):
    from application.models import Reserva
    if request.method == 'POST':
        user = request.user
        # Verificar reservas pendientes o activas
        reservas_pendientes = Reserva.objects.filter(
            cliente=user, estado__in=['pendiente_pago', 'pagada'])
        if reservas_pendientes.exists():
            messages.error(
                request, 'No puedes eliminar tu perfil porque tienes reservas o alquileres pendientes.')
            return redirect('perfil')
        auth_logout(request)
        user.delete()
        messages.success(request, 'Tu cuenta ha sido eliminada exitosamente.')
        return redirect('home')
    return redirect('perfil')


@require_POST
def procesar_pago(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    numero_tarjeta = request.POST.get('numero_tarjeta')

    # Crear registro de pago inicial
    pago = Pago.objects.create(
        reserva=reserva,
        monto=reserva.monto_total,
        estado='pendiente'
    )

    # Procesar el pago con el banco
    resultado = BancoService.procesar_pago(numero_tarjeta, reserva.monto_total)

    if resultado['exitoso']:
        # Actualizar el pago como exitoso
        pago.estado = 'exitoso'
        pago.numero_transaccion = resultado['numero_transaccion']
        pago.save()

        messages.success(request, '¡Pago procesado exitosamente!')
        return redirect('detalle_reserva', reserva_id=reserva.id)
    else:
        # Actualizar el pago como fallido
        pago.estado = 'fallido'
        pago.motivo_fallo = resultado.get('error', 'otro')
        pago.save()

        messages.error(request, resultado['mensaje'])
        return redirect('pagar_reserva', reserva_id=reserva.id)


@login_required
def pagar_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    tarjetas = TarjetaCredito.objects.filter(usuario=request.user).order_by(
        '-es_predeterminada', '-fecha_creacion')
    form = TarjetaCreditoForm()

    if request.method == 'POST':
        if 'agregar_tarjeta' in request.POST:
            form = TarjetaCreditoForm(request.POST)
            if form.is_valid():
                # Verificar si ya existe una tarjeta con los mismos últimos 4 dígitos y titular
                numero_tarjeta = form.cleaned_data.get('numero_tarjeta')
                nombre_titular = form.cleaned_data.get('nombre_titular')
                ultimos_digitos = numero_tarjeta[-4:]

                tarjeta_existente = TarjetaCredito.objects.filter(
                    usuario=request.user,
                    ultimos_digitos=ultimos_digitos,
                    nombre_titular=nombre_titular
                ).exists()

                if tarjeta_existente:
                    form.add_error(None, 'Ya tienes registrada esta tarjeta.')
                    context = {
                        'reserva': reserva,
                        'tarjetas': tarjetas,
                        'form': form,
                        'preference_id': generar_preference_mercadopago(request, reserva_id)["id"],
                        'show_card_form': True  # Para mantener el formulario visible
                    }
                    return render(request, 'reservas/pagar_reserva.html', context)

                tarjeta = form.save(commit=False)
                tarjeta.usuario = request.user
                tarjeta.save()
                context = {
                    'reserva': reserva,
                    'tarjetas': TarjetaCredito.objects.filter(usuario=request.user).order_by('-es_predeterminada', '-fecha_creacion'),
                    'form': TarjetaCreditoForm(),
                    'preference_id': generar_preference_mercadopago(request, reserva_id)["id"],
                    'success_message': 'Tarjeta agregada exitosamente.'
                }
                return render(request, 'reservas/pagar_reserva.html', context)
        elif 'usar_tarjeta' in request.POST:
            tarjeta_id = request.POST.get('tarjeta_id')
            if tarjeta_id:
                try:
                    tarjeta = TarjetaCredito.objects.get(
                        id=tarjeta_id, usuario=request.user)

                    # Obtener el número completo de la tarjeta
                    numero_tarjeta = tarjeta.numero_tarjeta

                    # Validación específica según el número de tarjeta
                    if numero_tarjeta == '1111111111111111':
                        messages.error(
                            request, 'La tarjeta tiene fondos insuficientes')
                        return redirect('pagar_reserva', reserva_id=reserva.id)
                    elif numero_tarjeta == '2222222222222222':
                        messages.error(
                            request, 'Falló la conexión con el banco')
                        return redirect('pagar_reserva', reserva_id=reserva.id)
                    elif numero_tarjeta == '3333333333333333':
                        # Pago exitoso
                        reserva.estado = 'pagada'
                        reserva.save()
                        messages.success(request, 'Pago realizado con éxito')
                        return redirect('mis_reservas')
                    else:
                        # Para cualquier otra tarjeta, simular pago exitoso
                        reserva.estado = 'pagada'
                        reserva.save()
                        messages.success(
                            request, 'Pago realizado exitosamente')
                        return redirect('mis_reservas')

                except TarjetaCredito.DoesNotExist:
                    messages.error(request, 'Tarjeta no encontrada')
            else:
                messages.error(request, 'Selecciona una tarjeta válida')
        elif 'eliminar_tarjeta' in request.POST:
            tarjeta_id = request.POST.get('tarjeta_id')
            try:
                tarjeta = TarjetaCredito.objects.get(
                    id=tarjeta_id, usuario=request.user)
                tarjeta.delete()
                messages.success(
                    request, 'La tarjeta se eliminó correctamente.')
                return redirect('pagar_reserva', reserva_id=reserva.id)
            except TarjetaCredito.DoesNotExist:
                messages.error(
                    request, 'No se pudo eliminar la tarjeta. Intente nuevamente.')
                return redirect('pagar_reserva', reserva_id=reserva.id)

    preference = generar_preference_mercadopago(request, reserva_id)
    print(preference)
    context = {
        'reserva': reserva,
        'tarjetas': tarjetas,
        'form': form,
        'preference_id': preference["id"],
    }
    return render(request, 'reservas/pagar_reserva.html', context)


@login_required
def detalle_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)
    return render(request, 'reservas/detalle_reserva.html', {
        'reserva': reserva
    })


@login_required
@user_passes_test(is_owner)
def ver_perfil_empleado(request, empleado_id):
    empleado = get_object_or_404(
        User, id=empleado_id, perfil__role__name=Role.EMPLEADO)
    # Obtener todas las reservas gestionadas por el empleado
    reservas_gestionadas = empleado.reservas_gestionadas.all().order_by('-fecha_reserva')
    return render(request, 'registration/perfil_empleado.html', {
        'empleado': empleado,
        'reservas_gestionadas': reservas_gestionadas
    })


def crear_preference(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)

    # Aquí podrías agregar lógica real de Mercado Pago en el futuro

    # Crea un ítem en la preferencia
    preference_data = {
        "items": [
            {
                "title": "Mi producto",
                "quantity": 1,
                "unit_price": max(int(reserva.monto_total), 1),
            }
        ],
        "back_urls": {
            "success": request.build_absolute_uri(reverse('payment_success')),
            "failure": request.build_absolute_uri(reverse('payment_failure')),
            "pending": request.build_absolute_uri(reverse('payment_pending'))
        },
        "auto_return": "approved",
    }

    preference_response = sdk.preference().create(preference_data)
    return preference_response["response"]


def generar_preference_mercadopago(request, reserva_id):
    # Tu función que crea la preferencia
    preference = crear_preference(request, reserva_id)
    print(preference)
    print("hola")
    return preference


@login_required
def payment_success(request):
    # Obtener el payment_id y merchant_order_id de la URL
    payment_id = request.GET.get('payment_id')
    merchant_order_id = request.GET.get('merchant_order_id')

    if payment_id and merchant_order_id:
        try:
            # Aquí podrías verificar el pago con la API de MercadoPago si lo necesitas

            # Actualizar el estado de la reserva a 'pagada'
            reserva = Reserva.objects.filter(estado='pendiente_pago').last()
            if reserva:
                reserva.estado = 'pagada'
                reserva.save()

                # Crear registro de pago exitoso
                Pago.objects.create(
                    reserva=reserva,
                    monto=reserva.monto_total,
                    estado='exitoso',
                    numero_transaccion=payment_id
                )

                messages.success(
                    request, '¡Pago realizado con éxito! Tu reserva ha sido confirmada.')
            else:
                messages.warning(
                    request, 'No se encontró la reserva asociada al pago.')
        except Exception as e:
            messages.error(
                request, 'Ocurrió un error al procesar el pago. Por favor, contacta al soporte.')
    else:
        messages.warning(request, 'No se recibieron los datos del pago.')

    return redirect('mis_reservas')


@login_required
def payment_failure(request):
    messages.error(
        request, 'El pago no pudo ser procesado. Por favor, intenta nuevamente.')
    return redirect('mis_reservas')


@login_required
def payment_pending(request):
    messages.warning(request, 'Tu pago está pendiente de confirmación.')
    return redirect('mis_reservas')


def limpiar_datos(request):
    """
    Vista para eliminar todas las tarjetas, reservas, maquinarias, sucursales y perfiles del sistema.
    """

    # Eliminar todas las tarjetas
    TarjetaCredito.objects.all().delete()

    # Eliminar todas las reservas
    Reserva.objects.all().delete()

    # Eliminar todas las maquinarias y sus imágenes asociadas
    Maquina.objects.all().delete()

    # Eliminar todas las sucursales
    Sucursal.objects.all().delete()

    # Eliminar todos los usuarios (empleados y clientes) excepto el dueño
    User.objects.filter(perfil__role__name__in=[
        Role.EMPLEADO, Role.CLIENTE]).delete()

    messages.success(
        request, 'Se han eliminado todas las tarjetas, reservas, maquinarias, sucursales y perfiles de usuarios exitosamente.')
    return redirect('home')


def sobre_nosotros(request):
    """
    Vista para mostrar la página Sobre Nosotros.
    """
    return render(request, 'sobre_nosotros.html')


def lista_ubicaciones(request):
    sucursales = Sucursal.objects.all()

    # Crear el mapa (inicialmente centrado en Argentina, pero lo ajustaremos después)
    m = folium.Map(location=[-34.6037, -58.3816], zoom_start=5)

    # Lista para almacenar las coordenadas de las sucursales con latitud y longitud
    locations = []

    # Agregar marcadores para cada sucursal
    for sucursal in sucursales:
        if sucursal.latitud and sucursal.longitud:
            # Añadir las coordenadas a la lista
            locations.append([sucursal.latitud, sucursal.longitud])

            # Crear el popup con la información de la sucursal
            popup_html = f"""
                <div style='width: 200px;'>
                    <h4 style='margin-bottom: 10px;'>{sucursal.get_direccion_completa()}</h4>
                    <p style='margin: 5px 0;'>
                        <strong>Estado:</strong> {'Activa' if sucursal.activa else 'Inactiva'}
                    </p>
                </div>
            """

            # Agregar el marcador al mapa
            folium.Marker(
                location=[sucursal.latitud, sucursal.longitud],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=sucursal.get_direccion_completa(),
                icon=folium.Icon(
                    color='green' if sucursal.activa else 'red',
                    icon='info-sign'
                )
            ).add_to(m)

    # Si hay ubicaciones, ajustar los límites del mapa para que todas sean visibles
    if locations:
        m.fit_bounds(locations)

    # Convertir el mapa a HTML
    m = m._repr_html_()

    return render(request, 'listados/lista_ubicaciones.html', {
        'sucursales': sucursales,
        'map': m
    })


@login_required
def administrar_sucursales(request):
    """
    Vista para que Roberto y María administren las sucursales.
    """
    # Verificar si el usuario es Roberto o María
    if not (request.user.first_name == 'Roberto' or request.user.first_name == 'María'):
        messages.error(
            request, 'No tienes permiso para acceder a esta página.')
        return redirect('home')

    sucursales = Sucursal.objects.all().order_by('numero')
    return render(request, 'admin/administrar_sucursales.html', {
        'sucursales': sucursales
    })


@login_required
def agregar_sucursal(request):
    calle = ''
    localidad = ''

    if request.method == 'POST':
        calle = request.POST.get('calle', '').strip()
        localidad = request.POST.get('localidad', '').strip()

        if not calle or not localidad:
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})

        if calle.isdigit() or localidad.isdigit() or len(calle) < 3 or len(localidad) < 3:
            messages.error(
                request, 'Calle y/o localidad inválidas')  # (mínimo 3 letras, no solo números).
            return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})

        if Sucursal.objects.filter(calle=calle, localidad=localidad).exists():
            messages.error(
                request, 'Ya existe una sucursal registrada en esa dirección.')
            return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})

        direccion_geocodificar = f"{calle}, {localidad}, Buenos Aires, Argentina"
        geolocator = Nominatim(user_agent="bea_scrumsynergy")

        try:
            location = geolocator.geocode(
                direccion_geocodificar, country_codes='ar', timeout=5)

            if not location or "Argentina" not in location.address:
                messages.error(
                    request, 'No se pudo encontrar la ubicación en Argentina. Verificá los datos.')
                return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})

            nueva_sucursal = Sucursal.objects.create(
                calle=calle,
                localidad=localidad,
                latitud=location.latitude,
                longitud=location.longitude,
                activa=True
            )
            messages.success(request, 'Sucursal agregada correctamente.')
            return redirect('administrar_sucursales')

        except (GeocoderTimedOut, GeocoderUnavailable, requests.exceptions.ReadTimeout):
            messages.error(
                request, 'El servicio de mapas está demorando o no responde. Intentá nuevamente.')
            return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})

    return render(request, 'admin/agregar_sucursal.html', {'calle': calle, 'localidad': localidad})


@login_required
def editar_sucursal(request, sucursal_id):
    """
    Vista para editar una sucursal existente.
    """
    if not (request.user.first_name == 'Roberto' or request.user.first_name == 'María'):
        messages.error(request, 'No tienes permiso para realizar esta acción.')
        return redirect('home')

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    if request.method == 'POST':
        sucursal.numero = request.POST.get('numero')
        sucursal.localidad = request.POST.get('localidad')
        sucursal.direccion = request.POST.get('direccion')
        sucursal.activa = request.POST.get('activa') == 'on'

        try:
            sucursal.save()
            messages.success(request, 'Sucursal actualizada exitosamente.')
            return redirect('administrar_sucursales')
        except Exception as e:
            messages.error(
                request, f'Error al actualizar la sucursal: {str(e)}')

    return render(request, 'admin/editar_sucursal.html', {
        'sucursal': sucursal
    })


@login_required
def eliminar_sucursal(request, sucursal_id):
    if not (request.user.first_name == 'Roberto' or request.user.first_name == 'María'):
        messages.error(request, 'No tienes permiso para realizar esta acción.')
        return redirect('home')

    try:
        sucursal = Sucursal.objects.get(id=sucursal_id)
        sucursal.delete()
        messages.success(request, 'Sucursal eliminada exitosamente.')
    except Sucursal.DoesNotExist:
        messages.error(request, 'La sucursal no existe.')
    except Exception as e:
        messages.error(request, 'Ocurrió un error al eliminar la sucursal.')

    return redirect('administrar_sucursales')


@login_required
def cambiar_password(request):
    if request.method == 'POST':
        form = CambiarPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(
                request, 'Tu contraseña ha sido cambiada exitosamente.')
            return redirect('perfil')
    else:
        form = CambiarPasswordForm(request.user)
    return render(request, 'registration/cambiar_password.html', {'form': form})


def politicas_privacidad(request):
    """
    Vista para mostrar la página de políticas de privacidad.
    """
    return render(request, 'politicas_privacidad.html')


@login_required
def preguntas_cliente(request):
    if not request.user.perfil.is_cliente:
        messages.error(
            request, 'Solo los clientes pueden acceder a esta sección.')
        return redirect('home')

    if request.method == 'POST':
        texto = request.POST.get('texto', '').strip()
        if not texto:
            messages.error(
                request, 'El campo de pregunta no puede estar vacío.')
        else:
            Pregunta.objects.create(usuario=request.user, texto=texto)
            messages.success(request, '¡Pregunta añadida correctamente!')
            return redirect('preguntas_cliente')

    # Mostrar mensaje de éxito si viene por GET
    msg = request.GET.get('msg')
    if msg:
        messages.success(request, msg)

    preguntas = Pregunta.objects.filter(
        usuario=request.user).order_by('-fecha_creacion')
    return render(request, 'preguntas/preguntas_cliente.html', {'preguntas': preguntas})


@login_required
def editar_pregunta(request, pregunta_id):
    pregunta = get_object_or_404(
        Pregunta, id=pregunta_id, usuario=request.user)
    if pregunta.respuesta:
        messages.error(
            request, 'No puedes editar una pregunta que ya tiene respuesta.')
        return redirect('preguntas_cliente')
    if request.method == 'POST':
        texto = request.POST.get('texto', '').strip()
        if not texto:
            messages.error(
                request, 'El campo de pregunta no puede estar vacío.')
        else:
            pregunta.texto = texto
            pregunta.save()
            messages.success(request, 'Pregunta actualizada correctamente.')
            return redirect('preguntas_cliente')
    return render(request, 'preguntas/editar_pregunta.html', {'pregunta': pregunta})


@login_required
def eliminar_pregunta(request, pregunta_id):
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)
    puede_eliminar = (
        (pregunta.usuario == request.user and not pregunta.respuesta) or
        (request.user.perfil.is_empleado or request.user.perfil.is_dueno)
    )
    if not puede_eliminar:
        messages.error(
            request, 'No tienes permiso para eliminar esta consulta.')
        return redirect('preguntas_cliente')
    if request.method == 'POST':
        pregunta.delete()
        params = urlencode({'msg': 'Pregunta eliminada correctamente.'})
        if request.user.perfil.is_empleado or request.user.perfil.is_dueno:
            return redirect(f"{reverse('gestionar_preguntas')}?{params}")
        return redirect(f"{reverse('preguntas_cliente')}?{params}")
    return render(request, 'preguntas/eliminar_pregunta.html', {'pregunta': pregunta})


@login_required
def gestionar_preguntas(request):
    if not (request.user.perfil.is_empleado or request.user.perfil.is_dueno):
        messages.error(
            request, 'No tienes permiso para acceder a esta sección.')
        return redirect('home')
    # Mostrar mensaje de éxito si viene por GET
    msg = request.GET.get('msg')
    if msg:
        messages.success(request, msg)
    preguntas = Pregunta.objects.all().order_by('-fecha_creacion')
    return render(request, 'preguntas/gestionar_preguntas.html', {'preguntas': preguntas})


@login_required
def registrar_devolucion(request):
    # Verificar que el usuario sea empleado o dueño
    if not (request.user.perfil.is_empleado or request.user.perfil.is_dueno):
        raise PermissionDenied(
            "No tienes permisos para acceder a esta página.")

    if request.method == 'POST':
        form = RegistrarDevolucionForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data['codigo']
            fecha_devolucion = form.cleaned_data['fecha_devolucion']
            try:
                maquina = Maquina.objects.get(codigo=codigo)
            except Maquina.DoesNotExist:
                messages.error(request, 'Máquina no encontrada.')
                return render(request, 'registrar_devolucion.html', {'form': form})

            if maquina.estado != 'alquilado':
                messages.error(
                    request, 'La máquina no se encuentra en estado "alquilada".')
                return render(request, 'registrar_devolucion.html', {'form': form})

            # Buscar la reserva activa
            reserva = Reserva.objects.filter(
                maquina=maquina, estado='pagada').order_by('-fecha_fin').first()
            if not reserva:
                messages.error(
                    request, 'No se encontró una reserva activa para esta máquina.')
                return render(request, 'registrar_devolucion.html', {'form': form})

            # Verificar si la devolución es en término
            if fecha_devolucion <= reserva.fecha_fin:
                # Escenario 1: Devolución en término
                maquina.estado = 'en_revision'
                maquina.save()
                reserva.estado = 'finalizada'
                reserva.save()
                messages.success(
                    request, 'Devolución registrada con éxito. La maquinaria pasa a estado de revisión.')
            else:
                # Escenario 2: Devolución fuera de término
                maquina.estado = 'en_revision'
                maquina.save()
                reserva.estado = 'finalizada'
                reserva.save()
                # Aplica recargo (ejemplo: 10% del monto total por día de retraso)
                dias_retraso = (fecha_devolucion - reserva.fecha_fin).days
                recargo = Decimal('0.10') * reserva.monto_total * dias_retraso
                messages.warning(
                    request, f'Devolución fuera de término. Se aplica un recargo de ${recargo:.2f} por {dias_retraso} días de retraso.')
            return redirect('registrar_devolucion')
    else:
        form = RegistrarDevolucionForm()
    return render(request, 'registrar_devolucion.html', {'form': form})


@login_required
def responder_pregunta(request, pregunta_id):
    if not (request.user.perfil.is_empleado or request.user.perfil.is_dueno):
        messages.error(request, 'No tienes permiso para responder preguntas.')
        return redirect('gestionar_preguntas')
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)
    if pregunta.respuesta:
        if pregunta.maquina:
            return redirect('detalle_maquinaria', maquina_id=pregunta.maquina.id)
        else:
            return redirect('gestionar_preguntas')
    if request.method == 'POST':
        form = ResponderPreguntaForm(request.POST, instance=pregunta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Respuesta registrada con éxito.')
            if pregunta.maquina:
                return redirect(f"{reverse('detalle_maquinaria', args=[pregunta.maquina.id])}#preguntas")
            else:
                return redirect('gestionar_preguntas')
    else:
        form = ResponderPreguntaForm(instance=pregunta)
    return render(request, 'preguntas/responder_pregunta.html', {'form': form, 'pregunta': pregunta})


@login_required
@user_passes_test(lambda u: u.perfil.is_dueno or u.perfil.is_empleado)
def lista_maquinaria_admin(request):
    # Obtener todas las máquinas
    maquinas = Maquina.objects.all().order_by('codigo')
    return render(request, 'listados/lista_maquinaria_admin.html', {'maquinas': maquinas})


@login_required
@user_passes_test(is_owner)
def editar_maquinaria(request, maquina_id):
    maquina = get_object_or_404(Maquina, id=maquina_id)

    if request.method == 'POST':
        print("DEBUG: Procesando POST request para editar maquinaria")
        print(f"DEBUG: FILES en request: {request.FILES}")
        print(f"DEBUG: POST data: {request.POST}")

        # Actualizar los campos de la maquinaria
        maquina.nombre = request.POST.get('nombre')
        maquina.marca = request.POST.get('marca')
        maquina.modelo = request.POST.get('modelo')
        maquina.anio = request.POST.get('anio')
        maquina.ubicacion = request.POST.get('ubicacion')
        maquina.tipo = request.POST.get('tipo')
        maquina.estado = request.POST.get('estado')
        maquina.descripcion = request.POST.get('descripcion')
        maquina.tipo_cancelacion = request.POST.get('tipo_cancelacion')

        # Manejar el porcentaje de reembolso según la política de cancelación
        if maquina.tipo_cancelacion == 'parcial':
            politica_cancelacion = request.POST.get('politica_cancelacion')
            try:
                porcentaje = float(politica_cancelacion)
                if porcentaje < 10 or porcentaje > 90:
                    messages.error(
                        request, 'El porcentaje de reembolso debe estar entre 10% y 90%.')
                    return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})
                maquina.politica_cancelacion = porcentaje
            except (ValueError, TypeError):
                messages.error(
                    request, 'Por favor ingrese un porcentaje válido para el reembolso.')
                return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})
        else:
            maquina.politica_cancelacion = None

        # Convertir precio_por_dia a Decimal
        try:
            precio = request.POST.get('precio_por_dia')
            if precio:
                maquina.precio_por_dia = Decimal(precio)
            else:
                messages.error(request, 'El precio por día es requerido.')
                return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, 'Por favor ingrese un precio válido.')
            return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

        maquina.permisos_requeridos = request.POST.get('permisos_requeridos')

        try:
            print("DEBUG: Validando modelo de maquinaria")
            maquina.full_clean()  # Validar el modelo
            maquina.save()
            print("DEBUG: Maquinaria guardada exitosamente")

            # Manejar imágenes nuevas
            nuevas_imagenes = request.FILES.getlist('nuevas_imagenes')
            print(f"DEBUG: Nuevas imágenes recibidas: {len(nuevas_imagenes)}")

            for imagen in nuevas_imagenes:
                print(
                    f"DEBUG: Procesando imagen: {imagen.name}, tamaño: {imagen.size}, tipo: {imagen.content_type}")
                try:
                    # Validar tamaño
                    if imagen.size > 5 * 1024 * 1024:  # 5MB
                        messages.error(
                            request, f'La imagen {imagen.name} excede el tamaño máximo permitido de 5MB.')
                        return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

                    # Validar tipo de archivo y extensión
                    allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
                    allowed_extensions = ['.jpg', '.jpeg', '.png']

                    # Verificar el content type
                    if imagen.content_type.lower() not in allowed_types:
                        messages.error(
                            request, f'El archivo {imagen.name} no es un formato válido. Solo se permiten archivos JPG, JPEG y PNG.')
                        return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

                    # Verificar la extensión
                    extension = os.path.splitext(imagen.name.lower())[1]
                    if extension not in allowed_extensions:
                        messages.error(
                            request, f'La extensión del archivo {imagen.name} no está permitida. Solo se permiten archivos .jpg, .jpeg y .png')
                        return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

                    ImagenMaquina.objects.create(
                        maquina=maquina,
                        imagen=imagen,
                        es_principal=False
                    )
                    print(f"DEBUG: Imagen {imagen.name} guardada exitosamente")
                except Exception as e:
                    print(
                        f"ERROR: Error al guardar imagen {imagen.name}: {str(e)}")
                    messages.error(
                        request, f'Error al guardar la imagen {imagen.name}')
                    return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

            # Actualizar imagen principal si se seleccionó una
            imagen_principal_id = request.POST.get('imagen_principal')
            print(
                f"DEBUG: ID de imagen principal seleccionada: {imagen_principal_id}")

            if imagen_principal_id:
                # Primero quitamos el flag de principal de todas las imágenes
                maquina.imagenes.all().update(es_principal=False)
                # Luego marcamos la seleccionada como principal
                ImagenMaquina.objects.filter(
                    id=imagen_principal_id).update(es_principal=True)
                print("DEBUG: Imagen principal actualizada")

            # Verificar que haya al menos una imagen
            if not maquina.imagenes.exists() and not nuevas_imagenes:
                messages.error(
                    request, 'Debe subir al menos una imagen para la maquinaria.')
                return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

            # Si no hay imagen principal seleccionada pero hay imágenes, hacer principal la primera
            if not imagen_principal_id and maquina.imagenes.exists():
                primera_imagen = maquina.imagenes.first()
                primera_imagen.es_principal = True
                primera_imagen.save()
                print("DEBUG: Primera imagen establecida como principal")

            messages.success(request, 'Maquinaria actualizada exitosamente.')
            return redirect('lista_maquinaria_admin')
        except ValidationError as e:
            print(f"ERROR: Error de validación: {str(e)}")
            messages.error(
                request, f'Error al actualizar la maquinaria: {str(e)}')
            return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})
        except Exception as e:
            print(f"ERROR: Error inesperado: {str(e)}")
            messages.error(
                request, f'Error inesperado al actualizar la maquinaria: {str(e)}')
            return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})

    return render(request, 'listados/editar_maquinaria.html', {'maquina': maquina})


@login_required
@user_passes_test(is_owner)
def eliminar_imagen(request, imagen_id):
    if request.method == 'POST':
        try:
            imagen = ImagenMaquina.objects.get(id=imagen_id)
            maquina = imagen.maquina

            # Verificar si es la última imagen
            if maquina.imagenes.count() <= 1:
                return JsonResponse({
                    'success': False,
                    'error': 'No se puede eliminar la última imagen. La maquinaria debe tener al menos una imagen.'
                })

            # Si es la imagen principal y hay otras imágenes, hacer principal a otra
            if imagen.es_principal:
                nueva_principal = maquina.imagenes.exclude(
                    id=imagen_id).first()
                nueva_principal.es_principal = True
                nueva_principal.save()

            # Eliminar la imagen
            imagen.delete()

            return JsonResponse({'success': True})
        except ImagenMaquina.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Imagen no encontrada'
            })
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido'
    })


@login_required
def mis_alquileres(request):
    # Alquileres activos
    alquileres = Reserva.objects.filter(
        cliente=request.user,
        estado__in=['pendiente_pago', 'pagada']
    ).order_by('-fecha_inicio')
    # Alquileres cancelados
    alquileres_cancelados = Reserva.objects.filter(
        cliente=request.user,
        estado='cancelada'
    ).order_by('-fecha_inicio')
    return render(request, 'reservas/mis_alquileres.html', {
        'reservas': alquileres,
        'alquileres_cancelados': alquileres_cancelados
    })


@login_required
def alquilar_maquinaria(request):
    if request.method == 'POST':
        id_maquinaria = request.POST.get('id_maquinaria')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        # Aquí irá la lógica de alquiler, por ahora solo mostramos los datos
        messages.info(
            request, f'ID ingresado: {id_maquinaria}, Fecha inicio: {fecha_inicio}, Fecha fin: {fecha_fin}')
        return redirect('alquilar_maquinaria')
    return render(request, 'reservas/alquilar_maquinaria.html')


@login_required
def alquilar_maquinaria_detalle(request, id_maquina):
    from .forms import ReservaMaquinariaForm
    maquina = get_object_or_404(Maquina, id=id_maquina)
    proxima_disponibilidad = maquina.get_proxima_disponibilidad()

    if maquina.estado == 'en_revision' or maquina.estado == 'mantenimiento':
        messages.error(
            request, 'La máquina está suspendida temporalmente y no puede ser alquilada.')
        return redirect('detalle_maquinaria', maquina_id=maquina.id)

    if request.method == 'POST':
        # Creamos el formulario manualmente porque el template no lo renderiza como {{ form }}
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        data = {
            'maquina': maquina.id,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }
        form = ReservaMaquinariaForm(data)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.cliente = request.user
            reserva.maquina = maquina
            if request.user.perfil.is_empleado:
                reserva.empleado_gestor = request.user
            dias = (form.cleaned_data['fecha_fin'] -
                    form.cleaned_data['fecha_inicio']).days + 1
            reserva.monto_total = maquina.precio_por_dia * dias
            try:
                with transaction.atomic():
                    reserva.save()
                    # Cambiar el estado de la máquina a 'reservada'
                    maquina.estado = 'reservada'
                    maquina.save()
                    messages.success(
                        request, f'Alquiler creado exitosamente. Número de alquiler: {reserva.numero_reserva}')
                    return redirect('mis_alquileres')
            except Exception as e:
                messages.error(
                    request, 'Error al crear el alquiler. Por favor, intente nuevamente.')
                return redirect('detalle_maquinaria', maquina_id=maquina.id)
        else:
            # Solo mostrar errores generales como mensajes
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        initial_data = {
            'maquina': maquina.id,
            'fecha_inicio': proxima_disponibilidad
        }
        form = ReservaMaquinariaForm(initial=initial_data)

    return render(request, 'reservas/alquilar_maquinaria_detalle.html', {
        'maquina': maquina,
        'proxima_disponibilidad': proxima_disponibilidad
    })


def preguntas_frecuentes(request):
    preguntas = [
        {
            'icono': '📅',
            'pregunta': '¿Cómo reservo una máquina?',
            'respuesta': 'Podés hacer tu reserva directamente desde nuestra web o llamando al número publicado. Indicá la máquina que necesitás y el tiempo de alquiler.'
        },
        {
            'icono': '⏳',
            'pregunta': '¿Cuál es el período Maximo de alquiler?',
            'respuesta': 'El período mínimo de alquiler es de 7 días.'
        },
        {
            'icono': '🚚',
            'pregunta': '¿Realizan envíos a domicilio?',
            'respuesta': '¡No!, por el momento no contamos con envios.'
        },
        {
            'icono': '💳',
            'pregunta': '¿Qué formas de pago aceptan?',
            'respuesta': 'Aceptamos pagos en efectivo, Mercado pago, tarjetas de crédito.'
        },
        {
            'icono': '🛠️',
            'pregunta': '¿Qué pasa si la máquina se rompe durante el uso?',
            'respuesta': 'Todas nuestras máquinas están revisadas antes del alquiler. Si surge un problema, comunicate con nosotros y lo resolveremos lo antes posible.'
        },
        {
            'icono': '🪪',
            'pregunta': '¿Qué documentación necesito para alquilar?',
            'respuesta': 'Solo necesitás presentar tu DNI y en caso de requerir permiso especial, el permiso debe estar cargad en tu perfil o llevarlo impreso cuando retires tu maquinaria.'
        },
        {
            'icono': '🛠️',
            'pregunta': '¿Puedo operar la maquinaria sin licencia?',
            'respuesta': 'Depende del tipo de equipo. Para maquinaria pesada como Pala hidráulica, se requiere una licencia especial. Para herramientas más simples, no es necesario.'
        },
    ]
    return render(request, 'preguntas/preguntas_frecuentes.html', {'preguntas': preguntas})


def contacto(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            nombre = form.cleaned_data['nombre']
            apellidos = form.cleaned_data['apellidos']
            correo = form.cleaned_data['correo_electronico']
            telefono = form.cleaned_data['telefono']
            consulta = form.cleaned_data['consulta']

            # Construir el mensaje
            mensaje = f"""
            Nuevo mensaje de contacto:

            Nombre: {nombre} {apellidos}
            Correo: {correo}
            Teléfono: {telefono}

            Consulta:
            {consulta}
            """

            # Enviar el correo
            try:
                send_mail(
                    subject='Nuevo mensaje de contacto - Bob el Alquilador',
                    message=mensaje,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=['morearias456@gmail.com'],
                    fail_silently=False,
                )
                messages.success(
                    request, 'Tu mensaje ha sido enviado correctamente. Nos pondremos en contacto contigo pronto.')
                return redirect('contacto')
            except Exception as e:
                messages.error(
                    request, 'Hubo un error al enviar el mensaje. Por favor, intenta nuevamente.')
    else:
        form = ContactForm()

    return render(request, 'contacto.html', {'form': form})


@login_required
def calificar_maquina(request, maquina_id):
    maquina = get_object_or_404(Maquina, id=maquina_id)

    # Verificar si el usuario ya ha calificado esta máquina
    calificacion_existente = Calificacion.objects.filter(
        usuario=request.user, maquina=maquina).first()

    if request.method == 'POST':
        if calificacion_existente:
            form = CalificacionForm(
                request.POST, instance=calificacion_existente)
            mensaje = '¡Gracias por actualizar tu calificación!'
        else:
            form = CalificacionForm(request.POST)
            mensaje = '¡Gracias por tu calificación!'

        if form.is_valid():
            calificacion = form.save(commit=False)
            calificacion.usuario = request.user
            calificacion.maquina = maquina
            calificacion.save()
            messages.success(request, mensaje)
            # Redirigir según el origen
            if request.GET.get('from') == 'alquileres':
                return redirect('mis_alquileres')
            return redirect('detalle_maquinaria', maquina_id=maquina.id)
    else:
        form = CalificacionForm(
            instance=calificacion_existente) if calificacion_existente else CalificacionForm()

    return render(request, 'listados/calificar_maquina.html', {
        'form': form,
        'maquina': maquina,
        'calificacion_existente': calificacion_existente
    })


@login_required
@user_passes_test(lambda u: u.perfil.is_empleado or u.perfil.is_dueno)
def alquiler_presencial_detalle(request, id_maquina):
    from .forms import AlquilerPresencialForm
    maquina = get_object_or_404(Maquina, id=id_maquina)
    proxima_disponibilidad = maquina.get_proxima_disponibilidad()

    # Verificar si la máquina está suspendida (en revisión o mantenimiento)
    if maquina.estado == 'en_revision' or maquina.estado == 'mantenimiento':
        messages.error(
            request, 'La máquina está suspendida temporalmente y no puede ser alquilada.')
        return redirect('detalle_maquinaria', maquina_id=maquina.id)

    if request.method == 'POST':
        # Creamos el formulario manualmente porque el template no lo renderiza como {{ form }}
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        email_cliente = request.POST.get('email_cliente')

        data = {
            'maquina': maquina.id,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'email_cliente': email_cliente
        }
        form = AlquilerPresencialForm(data)
        if form.is_valid():
            # Obtener el cliente por email
            cliente = User.objects.get(email=email_cliente)

            # Validaciones adicionales de fechas
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']
            hoy = timezone.now().date()

            # Validar que la fecha de inicio no sea anterior a hoy
            if fecha_inicio < hoy:
                messages.error(
                    request, 'La fecha de inicio debe ser igual o posterior a la fecha actual.')
                return render(request, 'reservas/alquiler_presencial_detalle.html', {
                    'maquina': maquina,
                    'proxima_disponibilidad': proxima_disponibilidad,
                    'form': form
                })

            # Validar que la fecha de fin no sea anterior a la fecha de inicio
            if fecha_fin < fecha_inicio:
                messages.error(
                    request, 'La fecha de fin no puede ser anterior a la fecha de inicio.')
                return render(request, 'reservas/alquiler_presencial_detalle.html', {
                    'maquina': maquina,
                    'proxima_disponibilidad': proxima_disponibilidad,
                    'form': form
                })

            # Validar que la reserva no exceda los 7 días
            duracion = (fecha_fin - fecha_inicio).days + 1
            if duracion > 7:
                messages.error(
                    request, 'La reserva no puede exceder los 7 días.')
                return render(request, 'reservas/alquiler_presencial_detalle.html', {
                    'maquina': maquina,
                    'proxima_disponibilidad': proxima_disponibilidad,
                    'form': form
                })

            # Verificar si hay otras reservas que se solapan
            reservas_previas = Reserva.objects.filter(
                maquina=maquina,
                estado__in=['pendiente_pago', 'pagada'],
                fecha_fin__gte=hoy,
            ).exclude(
                estado='cancelada'
            ).order_by('fecha_inicio')

            # Verificar cada reserva previa
            for reserva_prev in reservas_previas:
                # Verificar si la nueva reserva se solapa con una reserva existente
                if (
                    (fecha_inicio >= reserva_prev.fecha_inicio and fecha_inicio <= reserva_prev.fecha_fin) or
                    (fecha_fin >= reserva_prev.fecha_inicio and fecha_fin <= reserva_prev.fecha_fin) or
                    (fecha_inicio <= reserva_prev.fecha_inicio and fecha_fin >=
                     reserva_prev.fecha_fin)
                ):
                    fin_mantenimiento = reserva_prev.fecha_fin + \
                        timezone.timedelta(days=2)
                    messages.error(
                        request, f'La máquina está reservada del {reserva_prev.fecha_inicio.strftime("%d/%m/%Y")} al {reserva_prev.fecha_fin.strftime("%d/%m/%Y")} y estará en mantenimiento hasta el {fin_mantenimiento.strftime("%d/%m/%Y")}.')
                    return render(request, 'reservas/alquiler_presencial_detalle.html', {
                        'maquina': maquina,
                        'proxima_disponibilidad': proxima_disponibilidad,
                        'form': form
                    })

                # Verificar período de mantenimiento
                fin_mantenimiento = reserva_prev.fecha_fin + \
                    timezone.timedelta(days=2)
                if fecha_inicio <= fin_mantenimiento and fecha_inicio > reserva_prev.fecha_fin:
                    messages.error(
                        request, f'La máquina estará en mantenimiento hasta el {fin_mantenimiento.strftime("%d/%m/%Y")}.')
                    return render(request, 'reservas/alquiler_presencial_detalle.html', {
                        'maquina': maquina,
                        'proxima_disponibilidad': proxima_disponibilidad,
                        'form': form
                    })

            reserva = form.save(commit=False)
            reserva.cliente = cliente
            reserva.maquina = maquina
            reserva.empleado_gestor = request.user  # Registrar el empleado que gestiona

            # Calcular el monto total
            dias = (form.cleaned_data['fecha_fin'] -
                    form.cleaned_data['fecha_inicio']).days + 1
            reserva.monto_total = maquina.precio_por_dia * dias

            try:
                with transaction.atomic():
                    reserva.save()
                    # Marcar la reserva como pagada directamente (pago presencial)
                    reserva.estado = 'pagada'
                    reserva.save()
                    # Cambiar el estado de la máquina a 'alquilado'
                    reserva.maquina.estado = 'alquilado'
                    reserva.maquina.save()
                    # Enviar email de confirmación al cliente
                    subject = f'Confirmación de Alquiler Presencial - {reserva.numero_reserva}'
                    
                    # Generar la URL completa para valorar empleado
                    from django.contrib.sites.shortcuts import get_current_site
                    from django.urls import reverse
                    
                    # Usar el dominio configurado en settings o localhost para desarrollo
                    try:
                        current_site = get_current_site(request)
                        domain = current_site.domain
                        if not domain or domain == 'example.com':
                            domain = '127.0.0.1:8000'
                    except:
                        domain = '127.0.0.1:8000'
                    
                    valorar_url = f"http://{domain}/valorar-empleado/{reserva.id}/"
                    
                    html_message = render_to_string('emails/confirmacion_alquiler_presencial.html', {
                        'reserva': reserva,
                        'valorar_url': valorar_url,
                    })
                    plain_message = strip_tags(html_message)

                    try:
                        send_mail(
                            subject,
                            plain_message,
                            settings.EMAIL_HOST_USER,
                            [cliente.email],
                            html_message=html_message,
                            fail_silently=False,
                        )
                    except Exception as e:
                        print(
                            f"Error al enviar email de confirmación: {str(e)}")
                        # No fallar la transacción si el email no se envía
                    return render(request, 'reservas/alquiler_presencial_detalle.html', {
                        'maquina': maquina,
                        'proxima_disponibilidad': maquina.get_proxima_disponibilidad(),
                        'form': AlquilerPresencialForm(initial={'maquina': maquina.id, 'fecha_inicio': maquina.get_proxima_disponibilidad()}),
                        'alquiler_exitoso': True,
                        'reserva_creada': reserva
                    })
            except Exception as e:
                messages.error(
                    request, 'Error al crear el alquiler presencial. Por favor, intente nuevamente.')
                return redirect('detalle_maquinaria', maquina_id=maquina.id)
        else:
            # Solo mostrar errores generales como mensajes
            for error in form.non_field_errors():
                messages.error(request, error)
            # Mostrar errores de campos específicos
            for field, errors in form.errors.items():
                if field != '__all__':
                    for error in errors:
                        messages.error(
                            request, f'{form.fields[field].label}: {error}')
    else:
        initial_data = {
            'maquina': maquina.id,
            'fecha_inicio': proxima_disponibilidad
        }
        form = AlquilerPresencialForm(initial=initial_data)

    return render(request, 'reservas/alquiler_presencial_detalle.html', {
        'maquina': maquina,
        'proxima_disponibilidad': proxima_disponibilidad,
        'form': form
    })


@login_required
@user_passes_test(lambda u: u.perfil.is_empleado or u.perfil.is_dueno)
def pagar_reserva_presencial(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)

    # Verificar que el empleado actual es el gestor de esta reserva
    if reserva.empleado_gestor != request.user:
        messages.error(
            request, 'No tienes permisos para gestionar esta reserva.')
        return redirect('historial_reservas')

    tarjetas = TarjetaCredito.objects.filter(usuario=request.user).order_by(
        '-es_predeterminada', '-fecha_creacion')
    form = TarjetaCreditoForm()

    if request.method == 'POST':
        if 'agregar_tarjeta' in request.POST:
            form = TarjetaCreditoForm(request.POST)
            if form.is_valid():
                # Verificar si ya existe una tarjeta con los mismos últimos 4 dígitos y titular
                numero_tarjeta = form.cleaned_data.get('numero_tarjeta')
                nombre_titular = form.cleaned_data.get('nombre_titular')
                ultimos_digitos = numero_tarjeta[-4:]

                tarjeta_existente = TarjetaCredito.objects.filter(
                    usuario=request.user,
                    ultimos_digitos=ultimos_digitos,
                    nombre_titular=nombre_titular
                ).exists()

                if tarjeta_existente:
                    form.add_error(None, 'Ya tienes registrada esta tarjeta.')
                    context = {
                        'reserva': reserva,
                        'tarjetas': tarjetas,
                        'form': form,
                        'preference_id': generar_preference_mercadopago(request, reserva_id)["id"],
                        'show_card_form': True
                    }
                    return render(request, 'reservas/pagar_reserva_presencial.html', context)

                tarjeta = form.save(commit=False)
                tarjeta.usuario = request.user
                tarjeta.save()
                context = {
                    'reserva': reserva,
                    'tarjetas': TarjetaCredito.objects.filter(usuario=request.user).order_by('-es_predeterminada', '-fecha_creacion'),
                    'form': TarjetaCreditoForm(),
                    'preference_id': generar_preference_mercadopago(request, reserva_id)["id"],
                    'success_message': 'Tarjeta agregada exitosamente.'
                }
                return render(request, 'reservas/pagar_reserva_presencial.html', context)
        elif 'usar_tarjeta' in request.POST:
            tarjeta_id = request.POST.get('tarjeta_id')
            if tarjeta_id:
                try:
                    tarjeta = TarjetaCredito.objects.get(
                        id=tarjeta_id, usuario=request.user)

                    # Obtener el número completo de la tarjeta
                    numero_tarjeta = tarjeta.numero_tarjeta

                    # Validación específica según el número de tarjeta
                    if numero_tarjeta == '1111111111111111':
                        messages.error(
                            request, 'La tarjeta tiene fondos insuficientes')
                        return redirect('pagar_reserva_presencial', reserva_id=reserva.id)
                    elif numero_tarjeta == '2222222222222222':
                        messages.error(
                            request, 'Falló la conexión con el banco')
                        return redirect('pagar_reserva_presencial', reserva_id=reserva.id)
                    elif numero_tarjeta == '3333333333333333':
                        # Pago exitoso
                        reserva.estado = 'pagada'
                        reserva.save()
                        messages.success(
                            request, f'Pago realizado con éxito para el cliente {reserva.cliente.get_full_name()}')
                        return redirect('historial_reservas')
                    else:
                        # Para cualquier otra tarjeta, simular pago exitoso
                        reserva.estado = 'pagada'
                        reserva.save()
                        messages.success(
                            request, f'Pago realizado exitosamente para el cliente {reserva.cliente.get_full_name()}')
                        return redirect('historial_reservas')

                except TarjetaCredito.DoesNotExist:
                    messages.error(request, 'Tarjeta no encontrada')
            else:
                messages.error(request, 'Selecciona una tarjeta válida')
        elif 'eliminar_tarjeta' in request.POST:
            tarjeta_id = request.POST.get('tarjeta_id')
            try:
                tarjeta = TarjetaCredito.objects.get(
                    id=tarjeta_id, usuario=request.user)
                tarjeta.delete()
                messages.success(
                    request, 'La tarjeta se eliminó correctamente.')
                return redirect('pagar_reserva', reserva_id=reserva.id)
            except TarjetaCredito.DoesNotExist:
                messages.error(
                    request, 'No se pudo eliminar la tarjeta. Intente nuevamente.')
                return redirect('pagar_reserva', reserva_id=reserva.id)

    preference = generar_preference_mercadopago(request, reserva_id)
    context = {
        'reserva': reserva,
        'tarjetas': tarjetas,
        'form': form,
        'preference_id': preference["id"],
    }
    return render(request, 'reservas/pagar_reserva_presencial.html', context)


@login_required
@user_passes_test(lambda u: u.perfil.is_empleado or u.perfil.is_dueno)
def seleccionar_maquinaria_alquiler_presencial(request):
    """Vista para que empleados/dueños seleccionen maquinaria para alquiler presencial"""
    # Obtener todas las máquinas disponibles (no suspendidas)
    maquinas = Maquina.objects.exclude(
        estado__in=['suspendida', 'mantenimiento']
    ).order_by('nombre')

    # Filtrar por búsqueda si se proporciona
    busqueda = request.GET.get('busqueda', '').strip()
    if busqueda:
        maquinas = maquinas.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo__icontains=busqueda) |
            Q(marca__icontains=busqueda) |
            Q(modelo__icontains=busqueda)
        )

    # Filtrar por tipo si se proporciona
    tipo = request.GET.get('tipo')
    if tipo:
        maquinas = maquinas.filter(tipo=tipo)

    # Calcular disponibilidad para cada máquina
    maquinas_info = []
    for maquina in maquinas:
        proxima_disponibilidad = None
        if not maquina.esta_disponible():
            proxima_disponibilidad = maquina.get_proxima_disponibilidad()

        maquinas_info.append({
            'maquina': maquina,
            'proxima_disponibilidad': proxima_disponibilidad,
            'disponible_ahora': maquina.esta_disponible()
        })

    context = {
        'maquinas_info': maquinas_info,
        'tipos': Maquina.TIPO_CHOICES,
        'busqueda': busqueda,
        'tipo_seleccionado': tipo,
    }

    return render(request, 'reservas/seleccionar_maquinaria_alquiler_presencial.html', context)


@login_required
def cancelar_alquiler(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)
    estado_original = reserva.estado
    reserva.estado = 'cancelada'
    reserva.save()
    # Email
    asunto = f"Cancelación de alquiler {reserva.numero_reserva}"
    mensaje = render_to_string('emails/cancelacion_reserva.html', {
        'reserva': reserva,
        'reembolso': estado_original == 'pagada',
        'maquina': reserva.maquina,
        'cliente': reserva.cliente,
        'monto': reserva.monto_total,
        'fecha_inicio': reserva.fecha_inicio,
        'fecha_fin': reserva.fecha_fin,
    })
    send_mail(
        asunto,
        '',
        settings.DEFAULT_FROM_EMAIL,
        [reserva.cliente.email],
        html_message=mensaje
    )
    messages.error(
        request, f'Se canceló el alquiler {reserva.numero_reserva} con éxito.')
    return redirect('mis_alquileres')


@login_required
@user_passes_test(is_owner_or_employee)
def historial_alquileres(request):
    # Filtrar solo alquileres activos (máquinas con estado 'alquilado')
    alquileres = Reserva.objects.filter(
        maquina__estado='alquilado',
        estado__in=['pendiente_pago', 'pagada']
    ).order_by('fecha_inicio')  # Ordenar por fecha de inicio
    return render(request, 'reservas/historial_alquileres.html', {'alquileres': alquileres})


@login_required
def valorar_empleado(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)
    
    # Verificar que la reserva tenga un empleado gestor
    if not reserva.empleado_gestor:
        messages.error(request, 'Esta reserva no tiene un empleado asignado para valorar.')
        return redirect('mis_alquileres')
    
    # Verificar que la reserva esté pagada
    if reserva.estado != 'pagada':
        messages.error(request, 'Solo puedes valorar empleados de alquileres pagados.')
        return redirect('mis_alquileres')
    
    # Verificar si el usuario ya ha valorado este empleado para esta reserva
    valoracion_existente = ValoracionEmpleado.objects.filter(
        cliente=request.user, 
        empleado=reserva.empleado_gestor,
        reserva=reserva
    ).first()

    # Si ya existe una valoración, mostrar la página con la información pero sin permitir modificar
    if valoracion_existente:
        return render(request, 'valoraciones/valorar_empleado.html', {
            'empleado': reserva.empleado_gestor,
            'reserva': reserva,
            'valoracion_existente': valoracion_existente
        })

    if request.method == 'POST':
        form = ValoracionEmpleadoForm(request.POST)
        if form.is_valid():
            try:
                valoracion = form.save(commit=False)
                valoracion.cliente = request.user
                valoracion.empleado = reserva.empleado_gestor
                valoracion.reserva = reserva
                valoracion.save()
                
                print(f"DEBUG: Valoración guardada exitosamente - ID: {valoracion.id}")
                print(f"DEBUG: Cliente: {valoracion.cliente.username}")
                print(f"DEBUG: Empleado: {valoracion.empleado.username}")
                print(f"DEBUG: Reserva: {valoracion.reserva.numero_reserva}")
                print(f"DEBUG: Estrellas: {valoracion.estrellas}")
                
                messages.success(request, '¡Gracias por tu valoración!')
                return redirect('mis_alquileres')
            except Exception as e:
                print(f"ERROR al guardar valoración: {str(e)}")
                messages.error(request, f'Error al guardar la valoración: {str(e)}')
        else:
            print(f"ERROR en formulario: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = ValoracionEmpleadoForm()

    return render(request, 'valoraciones/valorar_empleado.html', {
        'form': form,
        'empleado': reserva.empleado_gestor,
        'reserva': reserva,
        'valoracion_existente': valoracion_existente
    })


@login_required
@user_passes_test(lambda u: u.perfil.is_dueno or u.perfil.is_empleado)
@require_http_methods(["POST"])
def actualizar_estado_maquina(request, maquina_id):
    try:
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
        
        maquina = Maquina.objects.get(id=maquina_id)
        maquina.estado = nuevo_estado
        maquina.save()
        
        return JsonResponse({'status': 'success'})
    except Maquina.DoesNotExist:
        return JsonResponse({'error': 'Máquina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(lambda u: u.perfil.is_dueno or u.perfil.is_empleado)
def historial_maquinaria(request, maquina_id):
    from .models import Maquina, Reserva
    maquina = get_object_or_404(Maquina, id=maquina_id)
    alquileres = Reserva.objects.filter(maquina=maquina).order_by('-fecha_inicio')
    return render(request, 'reservas/historial_maquinaria.html', {
        'alquileres': alquileres,
        'maquina': maquina
    })
