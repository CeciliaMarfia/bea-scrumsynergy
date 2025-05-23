from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from datetime import date
from .models import Perfil, PermisoEspecial
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class RegistroUsuarioForm(UserCreationForm):
    first_name = forms.CharField(required=True, label='Nombre')
    last_name = forms.CharField(required=True, label='Apellido')
    email = forms.EmailField(required=True)
    fecha_nacimiento = forms.DateField(
        required=True,
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    dni = forms.CharField(required=True, label='DNI')
    localidad = forms.CharField(required=True)
    documento_foto = forms.ImageField(
        required=True, label='Foto del documento')

    error_messages = {
        'password_mismatch': 'Las contraseñas no coinciden.',
    }

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email',
                  'username', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.HiddenInput()
        self.fields['username'].required = False

        # Personalizar mensajes de ayuda de la contraseña
        self.fields['password1'].help_text = _(
            'Tu contraseña debe cumplir con los siguientes requisitos:\n'
            '• Tener al menos 8 caracteres\n'
            '• No puede ser demasiado similar a tu información personal\n'
            '• No puede ser una contraseña común\n'
            '• No puede ser completamente numérica'
        )
        self.fields['password2'].help_text = _(
            'Ingresa la misma contraseña que antes, para verificación.')

        # Personalizar etiquetas
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar contraseña'
        self.fields['email'].label = 'Correo electrónico'

        # Personalizar mensajes de error de la contraseña
        self.error_messages['password_mismatch'] = 'Las dos contraseñas no coinciden.'
        self.fields['password1'].error_messages = {
            'required': 'La contraseña es obligatoria.',
            'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
            'password_too_similar': 'La contraseña es demasiado similar a tu información personal.',
            'password_too_common': 'La contraseña es demasiado común.',
            'password_entirely_numeric': 'La contraseña no puede ser completamente numérica.'
        }

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')

        # Usar el email completo como username
        if email:
            cleaned_data['username'] = email

        return cleaned_data

    def clean_fecha_nacimiento(self):
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - fecha_nacimiento.year - \
                ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
            if edad < 18:
                raise forms.ValidationError(
                    'Debes ser mayor de 18 años para registrarte.')
        return fecha_nacimiento

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'Este correo electrónico ya está registrado.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        # Asegurarnos que el username sea el email
        user.username = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            perfil = Perfil.objects.get(usuario=user)
            perfil.dni = self.cleaned_data['dni']
            perfil.fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
            perfil.direccion = self.cleaned_data['localidad']
            perfil.documento_foto = self.cleaned_data['documento_foto']
            perfil.save()

        return user


class PermisoEspecialForm(forms.ModelForm):
    class Meta:
        model = PermisoEspecial
        fields = ['nombre', 'descripcion', 'archivo']
        labels = {
            'nombre': 'Nombre del permiso',
            'descripcion': 'Descripción',
            'archivo': 'Archivo del permiso'
        }
        help_texts = {
            'archivo': 'Sube el archivo del permiso en formato PDF o imagen'
        }

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            # Obtener la extensión del archivo
            ext = archivo.name.split('.')[-1].lower()
            # Verificar que sea un tipo de archivo permitido
            if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
                raise forms.ValidationError(
                    'El archivo debe ser PDF o imagen (jpg, jpeg, png)')
        return archivo


class EditarPerfilForm(forms.ModelForm):
    first_name = forms.CharField(required=True, label='Nombre')
    last_name = forms.CharField(required=True, label='Apellido')
    email = forms.EmailField(required=True, label='Correo electrónico')
    dni = forms.CharField(required=True, label='DNI')
    fecha_nacimiento = forms.DateField(
        required=True,
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    direccion = forms.CharField(required=True, label='Dirección')
    documento_foto = forms.ImageField(
        required=False,
        label='Foto del documento',
        help_text='Deja en blanco para mantener la foto actual'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['dni'].initial = user.perfil.dni
            self.fields['fecha_nacimiento'].initial = user.perfil.fecha_nacimiento
            self.fields['direccion'].initial = user.perfil.direccion

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(id=self.instance.id).filter(email=email).exists():
            raise forms.ValidationError(
                'Este correo electrónico ya está registrado.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            perfil = user.perfil
            perfil.dni = self.cleaned_data['dni']
            perfil.fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
            perfil.direccion = self.cleaned_data['direccion']
            if self.cleaned_data.get('documento_foto'):
                perfil.documento_foto = self.cleaned_data['documento_foto']
            perfil.save()
        return user
