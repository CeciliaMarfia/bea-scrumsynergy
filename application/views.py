from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
import os
from django.conf import settings
from .machinery.forms import AltaMaquinariaForm
from .models import Maquina, HomeVideo
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .forms import RegistroUsuarioForm
from django.contrib.auth.decorators import login_required

# Create your views here.


def home(request):
    video_activo = HomeVideo.objects.filter(activo=True).first()
    return render(request, 'home.html', {'video': video_activo})


def login(request):
    if request.method == 'POST':
        # Obtener los datos del formulario
        # Revisa los campos nombre de usuario y contraseña para ver que existan
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Django verifica las credenciales contra la base de datos
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Iniciar sesión
            auth_login(request, user)
            messages.success(
                request, f'¡Bienvenido/a de nuevo, {user.first_name}!')
            return redirect('home')
        else:
            # No coinciden con algun usuario registrado
            messages.error(request, 'Usuario o contraseña incorrectos')

    # Si es GET o si falla la autenticación, mostrar el formulario
    return render(request, 'login.html')


def signup(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()

            # Enviar correo de bienvenida
            subject = '¡Bienvenido/a a Bob el Alquilador!'
            html_message = render_to_string('emails/bienvenida.html', {
                'user': user,
            })
            plain_message = strip_tags(html_message)
            from_email = settings.EMAIL_HOST_USER
            to = user.email

            try:
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    [to],
                    html_message=html_message,
                    fail_silently=False,
                )
            except Exception as e:
                messages.warning(
                    request, 'Tu cuenta fue creada pero hubo un problema al enviar el correo de bienvenida.')

            # Iniciar sesión automáticamente después del registro
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido/a, {user.first_name}!')
            return redirect('home')
    else:
        form = RegistroUsuarioForm()
    return render(request, 'signup.html', {'form': form})

# -- Codigo HU "Alta Maquinaria" --


DATA_PATH = os.path.join(settings.BASE_DIR, 'templatesMachine', 'machinery')


def machinery_registration(request):
    # Si el formulario fue enviado con método POST
    if request.method == 'POST':
        # Se instancia el formulario con los datos recibidos
        form = AltaMaquinariaForm(request.POST, request.FILES)

        # Si los datos del formulario son válidos
        if form.is_valid():
            # Obtenemos el código ingresado
            codigo = form.cleaned_data['codigo']

            # Verificamos si ya existe una maquinaria con ese mismo código
            if Maquina.objects.filter(codigo=codigo).exists():
                form.add_error(
                    'codigo', 'Ya existe una máquina con este código')
            else:
                # Creamos una nueva instancia de Maquinaria con los datos del formulario
                nueva_maquina = Maquina(
                    codigo=codigo,
                    nombre=form.cleaned_data['nombre'],
                    marca=form.cleaned_data['marca'],
                    modelo=form.cleaned_data['modelo'],
                    anio=form.cleaned_data['anio'],
                    ubicacion=form.cleaned_data['ubicacion'],
                    politica_cancelacion=form.cleaned_data['politica_cancelacion'],
                    tipo=form.cleaned_data['tipo'],
                    precio_por_dia=form.cleaned_data['precio_por_dia'],
                    permisos_requeridos=form.cleaned_data['permisos_requeridos'],
                    imagen=form.cleaned_data['imagen']
                )

                # Guardamos la nueva maquina en la base de datos
                nueva_maquina.save()

                # Mostramos la plantilla de éxito
                return render(request, 'templatesMachine/machinery_success.html')
    else:
        # Si no es POST, se muestra el formulario vacío
        form = AltaMaquinariaForm()

    # Renderiza el formulario en el template correspondiente
    return render(request, 'templatesMachine/machinery_registration.html', {'form': form})

# -- fin codigo --


@login_required
def logout(request):
    auth_logout(request)
    messages.success(request, '¡Has cerrado sesión exitosamente!')
    return redirect('home')
