from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
import json
import os
from django.conf import settings
from .maquinarias.forms import AltaMaquinariaForm

# Create your views here.
def home(request):
    return render(request, 'home.html')

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
            login(request, user)
            return redirect('home')
        else:
            # No coinciden con algun usuario registrado
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    # Si es GET o si falla la autenticación, mostrar el formulario
    return render(request, 'login.html')

from django.contrib import messages

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

# -- Codigo de solci para HU "Alta Maquinaria" --

DATA_PATH = os.path.join(settings.BASE_DIR, 'tasks', 'maquinarias')

def alta_maquinaria(request):
    if request.method == 'POST':
        form = AltaMaquinariaForm(request.POST, request.FILES)
        if form.is_valid():
            with open(DATA_PATH, 'r') as f:
                maquinas = json.load(f)

            if any(m['id'] == form.cleaned_data['id'] for m in maquinas):
                form.add_error('id', 'Ya existe una máquina con este ID')
            else:
                nueva_maquina = form.cleaned_data.copy()  # copiar para no alterar el original
                nueva_maquina['precio_por_dia'] = float(nueva_maquina['precio_por_dia'])  # <-- conversión
                nueva_maquina['imagen'] = request.FILES['imagen'].name
                maquinas.append(nueva_maquina)

                with open(DATA_PATH, 'w') as f:
                    json.dump(maquinas, f, indent=4)

                return render(request, 'tasks/alta_exitosa.html')
    else:
        form = AltaMaquinariaForm()

    return render(request, 'tasks/alta_maquinaria.html', {'form': form})

# -- fin codigo --