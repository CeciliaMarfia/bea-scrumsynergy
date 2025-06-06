import mercadopago
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
import os
from django.conf import settings
from .machinery.forms import AltaMaquinariaForm
from .models import Maquina, HomeVideo, PermisoEspecial, Perfil, Reserva, ImagenMaquina, Pago, TarjetaCredito, Role
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .forms import RegistroUsuarioForm, PermisoEspecialForm, EditarPerfilForm, ReservaMaquinariaForm, TarjetaCreditoForm, CambiarPasswordForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
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

import os

MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')

# SDK de Mercado Pago
# Agrega credenciales
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)


def home(request):
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
    # Obtener todas las máquinas (no solo las disponibles)
    maquinas = Maquina.objects.all()

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
    ubicaciones = Maquina.objects.values_list(
        'ubicacion', flat=True).distinct()

    # Calcular conteos para los filtros (ahora incluye todas las máquinas)
    tipos_con_conteo = {}
    for tipo_value, tipo_label in tipos:
        tipos_con_conteo[tipo_value] = Maquina.objects.filter(
            tipo=tipo_value).count()

    ubicaciones_con_conteo = {}
    for ubi in ubicaciones:
        if ubi:  # Solo si la ubicación no es None o vacía
            ubicaciones_con_conteo[ubi] = Maquina.objects.filter(
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
        'user_authenticated': request.user.is_authenticated
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
    maquina = get_object_or_404(Maquina, id=maquina_id)

    # Obtener la próxima disponibilidad usando el nuevo método
    proxima_disponibilidad = maquina.get_proxima_disponibilidad()

    return render(request, 'listados/detalle_maquinaria.html', {
        'maquina': maquina,
        'proxima_disponibilidad': proxima_disponibilidad
    })


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
    if request.method == 'POST':
        user = request.user
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
                    # Aquí iría la lógica de procesamiento del pago
                    reserva.estado = 'pagada'
                    reserva.save()
                    messages.success(request, 'Pago realizado exitosamente')
                    return redirect('mis_reservas')
                except TarjetaCredito.DoesNotExist:
                    messages.error(request, 'Tarjeta no encontrada')
            else:
                messages.error(request, 'Selecciona una tarjeta válida')
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
    Vista para eliminar todas las tarjetas, reservas, maquinarias y perfiles del sistema.
    """
    # Eliminar todas las tarjetas
    TarjetaCredito.objects.all().delete()

    # Eliminar todas las reservas
    Reserva.objects.all().delete()

    # Eliminar todas las maquinarias y sus imágenes asociadas
    Maquina.objects.all().delete()

    # Eliminar todos los usuarios (empleados y clientes) excepto el dueño
    User.objects.filter(perfil__role__name__in=[
                        Role.EMPLEADO, Role.CLIENTE]).delete()

    messages.success(
        request, 'Se han eliminado todas las tarjetas, reservas, maquinarias y perfiles de usuarios exitosamente.')
    return redirect('home')
