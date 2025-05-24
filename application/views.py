from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
import os
from django.conf import settings
from .machinery.forms import AltaMaquinariaForm
from .models import Maquina, HomeVideo, PermisoEspecial, Perfil, Reserva
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .forms import RegistroUsuarioForm, PermisoEspecialForm, EditarPerfilForm, ReservaMaquinariaForm
from django.contrib.auth.decorators import login_required
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

# Create your views here.


def home(request):
    video_activo = HomeVideo.objects.filter(activo=True).first()
    return render(request, 'home.html', {'video': video_activo})


def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = User.objects.get(username=username)
            if not user.perfil.email_verificado:
                return render(request, 'login.html', {
                    'error_message': 'Por favor, verifica tu correo electrónico antes de iniciar sesión.',
                    'show_verification_resend': True,
                    'unverified_email': username
                })
        except User.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido/a de nuevo, {user.first_name}!')
            return redirect('home')
        else:
            return render(request, 'login.html', {
                'error_message': 'Usuario o contraseña incorrectos'
            })

    return render(request, 'login.html')


def signup(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            # Crear usuario pero no autenticar automáticamente
            user = form.save()
            
            # Generar token de verificación
            token = str(uuid.uuid4())
            user.perfil.token_verificacion = token
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
                    'Tu cuenta ha sido creada. Por favor, revisa tu correo electrónico para verificar tu cuenta.'
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
        if not perfil.email_verificado:
            perfil.email_verificado = True
            perfil.token_verificacion = None  # Invalidar el token después de usarlo
            perfil.save()
            messages.success(request, '¡Tu cuenta ha sido verificada exitosamente! Ahora puedes iniciar sesión.')
        else:
            messages.info(request, 'Esta cuenta ya ha sido verificada anteriormente.')
    except Perfil.DoesNotExist:
        messages.error(request, 'El enlace de verificación no es válido.')
    
    return redirect('login')

# -- Codigo HU "Alta Maquinaria" --


DATA_PATH = os.path.join(settings.BASE_DIR, 'templatesMachine', 'machinery')


def machinery_registration(request):
    if request.method == 'POST':
        form = AltaMaquinariaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                maquina = form.save()
                return render(request, 'templatesMachine/machinery_success.html')
            except Exception as e:
                form.add_error(None, f'Error al guardar la maquinaria: {str(e)}')
    else:
        form = AltaMaquinariaForm()

    return render(request, 'templatesMachine/machinery_registration.html', {'form': form})

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
            permiso = form.save()
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
    return render(request, 'perfil.html', {
        'permisos': permisos
    })


@login_required
def editar_perfil(request):
    if request.method == 'POST':
        form = EditarPerfilForm(
            request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado exitosamente.')
            return redirect('perfil')
    else:
        form = EditarPerfilForm(instance=request.user, user=request.user)
    return render(request, 'editar_perfil.html', {'form': form})


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
            password = ''.join(random.choice(characters) for i in range(length))
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
            
            # Versión de texto plano del correo
            plain_message = f"""Hola {user.first_name},

Has solicitado recuperar tu contraseña en Bob el Alquilador. Hemos generado una nueva contraseña para tu cuenta.

Tu nueva contraseña es: {new_password}

Por favor, cambia esta contraseña por una de tu elección la próxima vez que inicies sesión.

Si no has solicitado este cambio, por favor contacta con nuestro equipo de soporte inmediatamente.

Saludos,
El equipo de Bob el Alquilador"""
            
            # Enviar el correo
            send_mail(
                subject,
                plain_message,
                settings.EMAIL_HOST_USER,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
        except User.DoesNotExist:
            # No hacemos nada si el usuario no existe
            pass
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")  # Para debugging

        # Siempre redirigimos a la página de éxito con el mismo mensaje
        return super().form_valid(form)


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
                        'Hemos enviado un nuevo correo de verificación. Por favor, revisa tu bandeja de entrada.'
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
            messages.error(request, 'No existe una cuenta con ese correo electrónico.')
    
    return redirect('login')


@login_required
def reservar_maquinaria(request, maquina_id):
    maquina = get_object_or_404(Maquina, id=maquina_id)
    
    if not maquina.esta_disponible():
        messages.error(request, 'No hay stock disponible para esta máquina.')
        return redirect('lista_maquinaria')

    if request.method == 'POST':
        form = ReservaMaquinariaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.maquina = maquina
            reserva.cliente = request.user
            
            # Calcular el monto total
            dias = (form.cleaned_data['fecha_fin'] - form.cleaned_data['fecha_inicio']).days + 1
            reserva.monto_total = maquina.precio_por_dia * dias
            
            try:
                with transaction.atomic():
                    reserva.save()
                    messages.success(request, f'Reserva creada exitosamente. Número de reserva: {reserva.numero_reserva}')
                    return redirect('mis_reservas')
            except Exception as e:
                messages.error(request, 'Error al crear la reserva. Por favor, intente nuevamente.')
                return redirect('lista_maquinaria')
    else:
        form = ReservaMaquinariaForm()

    return render(request, 'reserva/reservar_maquinaria.html', {
        'form': form,
        'maquina': maquina
    })


@login_required
def lista_maquinaria(request):
    maquinas = Maquina.objects.filter(estado='disponible', stock__gt=0)
    return render(request, 'listados/lista_maquinaria.html', {
        'maquinas': maquinas
    })


@login_required
def mis_reservas(request):
    reservas = Reserva.objects.filter(cliente=request.user).order_by('-fecha_reserva')
    return render(request, 'reserva/mis_reservas.html', {
        'reservas': reservas
    })
