from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from datetime import date
from .models import Perfil, PermisoEspecial, Reserva, TarjetaCredito, Maquina
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import password_validation
from django.conf import settings

# Diccionario global de mensajes de error en español
PASSWORD_ERROR_MESSAGES = {
    'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
    'password_too_similar': 'La contraseña es demasiado similar a tu información personal.',
    'password_too_common': 'La contraseña es demasiado común.',
    'password_entirely_numeric': 'La contraseña es demasiado numérica.',
    'password_mismatch': 'Las dos contraseñas no coinciden.',
    'required': 'Este campo es obligatorio.',
    'password_same_as_old': 'La nueva contraseña no puede ser igual a la contraseña actual.',
    'password_incorrect': 'La contraseña actual es incorrecta.'
}


def validate_password_length(password):
    if len(password) < 8:
        raise ValidationError(
            PASSWORD_ERROR_MESSAGES['password_too_short'],
            code='password_too_short'
        )


# Personalizar los mensajes de error de los validadores de Django
password_validation.MinimumLengthValidator.message = PASSWORD_ERROR_MESSAGES[
    'password_too_short']
password_validation.UserAttributeSimilarityValidator.message = PASSWORD_ERROR_MESSAGES[
    'password_too_similar']
password_validation.CommonPasswordValidator.message = PASSWORD_ERROR_MESSAGES[
    'password_too_common']
password_validation.NumericPasswordValidator.message = PASSWORD_ERROR_MESSAGES[
    'password_entirely_numeric']


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
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        self.is_employee = kwargs.pop('is_employee', False)
        super().__init__(*args, **kwargs)

        # Ocultar el campo de username
        if 'username' in self.fields:
            del self.fields['username']

        # Personalizar mensajes de ayuda de la contraseña
        self.fields['password1'].help_text = _(
            'Tu contraseña debe cumplir con los siguientes requisitos:\\n\\n'
            '• Tener al menos 8 caracteres\\n'
            '• No puede ser demasiado similar a tu información personal\\n'
            '• No puede ser una contraseña común\\n'
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
        # Personalizar mensajes de error para password2
        self.fields['password2'].error_messages = {
            'required': 'Por favor, confirma tu contraseña.',
            'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
            'password_too_similar': 'La contraseña es demasiado similar a tu información personal.',
            'password_too_common': 'La contraseña es demasiado común.',
            'password_entirely_numeric': 'La contraseña no puede ser completamente numérica.'
        }

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')

        # Usar el email como username
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
        with transaction.atomic():
            user = super().save(commit=False)
            user.email = self.cleaned_data['email']
            user.username = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.save()  # Guardamos el usuario primero para que se cree el perfil

            # Ahora actualizamos el perfil
            perfil = user.perfil  # La señal ya debería haber creado el perfil
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
    email = forms.EmailField(
        required=True, label='Correo electrónico', disabled=True)  # Email inmutable
    dni = forms.CharField(
        required=True,
        label='DNI',
        widget=forms.TextInput(attrs={
            'type': 'text',
            'pattern': '[0-9]{7,8}',
            'title': 'Ingrese un DNI válido de 7 u 8 dígitos',
            'maxlength': '8'
        })
    )
    fecha_nacimiento = forms.DateField(
        required=True,
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
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
            # Formatear la fecha al formato YYYY-MM-DD para el input type="date"
            if user.perfil.fecha_nacimiento:
                self.fields['fecha_nacimiento'].widget.attrs['value'] = user.perfil.fecha_nacimiento.strftime(
                    '%Y-%m-%d')
            self.fields['direccion'].initial = user.perfil.direccion

    def clean_fecha_nacimiento(self):
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - fecha_nacimiento.year - \
                ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
            if edad < 18:
                raise forms.ValidationError(
                    'No se puede modificar la edad a menos de 18 años.')
        return fecha_nacimiento

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        # Verificar que el DNI solo contenga números
        if not dni.isdigit():
            raise forms.ValidationError('El DNI debe contener solo números.')
        # Verificar la longitud del DNI
        if len(dni) < 7 or len(dni) > 8:
            raise forms.ValidationError(
                'El DNI debe tener entre 7 y 8 dígitos.')
        # Verificar si el DNI ya está registrado, excluyendo el usuario actual
        existing_user = Perfil.objects.filter(
            dni=dni).exclude(usuario=self.instance).first()
        if existing_user:
            raise forms.ValidationError(
                'Este DNI ya está registrado en el sistema.')
        return dni

    def clean_email(self):
        # Devolver el email original sin modificaciones
        return self.instance.email

    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=False)
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            # No actualizamos el email ya que es inmutable

            if commit:
                user.save()
                perfil = user.perfil
                perfil.dni = self.cleaned_data.get('dni')
                perfil.fecha_nacimiento = self.cleaned_data.get(
                    'fecha_nacimiento')
                perfil.direccion = self.cleaned_data.get('direccion')

                if 'documento_foto' in self.cleaned_data and self.cleaned_data['documento_foto']:
                    perfil.documento_foto = self.cleaned_data['documento_foto']

                perfil.save()

            return user


class ReservaMaquinariaForm(forms.ModelForm):
    maquina = forms.ModelChoiceField(
        queryset=Maquina.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )

    class Meta:
        model = Reserva
        fields = ['maquina', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        maquina = cleaned_data.get('maquina')

        if fecha_inicio and fecha_fin and maquina:
            # Validar que la fecha de inicio no sea anterior a la fecha actual
            if fecha_inicio < timezone.now().date():
                raise forms.ValidationError(
                    'La fecha de inicio no puede ser anterior a la fecha actual.')

            # Validar que la fecha de fin no sea anterior a la fecha de inicio
            if fecha_fin < fecha_inicio:
                raise forms.ValidationError(
                    'La fecha de fin no puede ser anterior a la fecha de inicio.')

            # Validar que la reserva no exceda los 7 días
            duracion = (fecha_fin - fecha_inicio).days + 1
            if duracion > 7:
                raise forms.ValidationError(
                    'La reserva no puede exceder los 7 días.')

            # Obtener todas las reservas activas que podrían solaparse
            reservas_existentes = Reserva.objects.filter(
                maquina=maquina,
                estado__in=['pendiente_pago', 'pagada'],
                fecha_fin__gte=fecha_inicio
            ).exclude(
                estado='cancelada'
            ).order_by('fecha_inicio')

            # Verificar solapamiento con otras reservas y períodos de mantenimiento
            for reserva in reservas_existentes:
                # Verificar solapamiento directo con la reserva
                if (fecha_inicio <= reserva.fecha_fin and fecha_fin >= reserva.fecha_inicio):
                    raise forms.ValidationError(
                        f'La máquina está reservada del {reserva.fecha_inicio.strftime("%d/%m/%Y")} al {reserva.fecha_fin.strftime("%d/%m/%Y")}.')

                # Verificar período de mantenimiento (2 días después de cada reserva)
                # La nueva reserva debe comenzar al menos 3 días después de la fecha de fin
                fecha_disponible = reserva.fecha_fin + \
                    timezone.timedelta(days=3)
                if fecha_inicio <= fecha_disponible and fecha_inicio > reserva.fecha_fin:
                    raise forms.ValidationError(
                        f'La máquina estará disponible a partir del {fecha_disponible.strftime("%d/%m/%Y")}.')

        return cleaned_data


class TarjetaCreditoForm(forms.ModelForm):
    numero_tarjeta = forms.CharField(
        label='Número de Tarjeta',
        max_length=16,
        min_length=16,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de tarjeta',
            'pattern': '[0-9]{16}'
        })
    )
    codigo_seguridad = forms.CharField(
        label='Código de Seguridad (CVV)',
        max_length=4,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CVV',
            'pattern': '[0-9]{3,4}',
            'type': 'password'
        })
    )
    fecha_vencimiento = forms.DateField(
        label='Fecha de Vencimiento',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    nombre_titular = forms.CharField(
        label='Nombre del Titular',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre como aparece en la tarjeta'
        })
    )
    es_predeterminada = forms.BooleanField(
        label='Establecer como tarjeta predeterminada',
        required=False,
        initial=False
    )

    class Meta:
        model = TarjetaCredito
        fields = ['nombre_titular', 'fecha_vencimiento', 'es_predeterminada']

    def clean_fecha_vencimiento(self):
        fecha = self.cleaned_data.get('fecha_vencimiento')
        if fecha and fecha < timezone.now().date():
            raise ValidationError('La tarjeta está vencida')
        return fecha

    def clean_numero_tarjeta(self):
        numero = self.cleaned_data.get('numero_tarjeta')
        if not numero.isdigit():
            raise ValidationError(
                'El número de tarjeta debe contener solo dígitos')
        return numero

    def clean_codigo_seguridad(self):
        codigo = self.cleaned_data.get('codigo_seguridad')
        if not codigo.isdigit():
            raise ValidationError(
                'El código de seguridad debe contener solo dígitos')
        if len(codigo) not in [3, 4]:
            raise ValidationError(
                'El código de seguridad debe tener 3 o 4 dígitos')
        return codigo

    def save(self, commit=True):
        tarjeta = super().save(commit=False)
        numero_tarjeta = self.cleaned_data.get('numero_tarjeta')
        tarjeta.ultimos_digitos = numero_tarjeta[-4:]
        tarjeta.tipo = 'credito'  # Por ahora solo manejamos tarjetas de crédito

        if commit:
            tarjeta.save()
        return tarjeta


class CambiarPasswordForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'current-password',
            'autofocus': True
        }),
        error_messages={
            'required': PASSWORD_ERROR_MESSAGES['required'],
            'password_incorrect': PASSWORD_ERROR_MESSAGES['password_incorrect']
        }
    )
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        help_text=_(
            'Tu contraseña debe cumplir con los siguientes requisitos:\n'
            '• Tener al menos 8 caracteres\n'
            '• No puede ser demasiado similar a tu información personal\n'
            '• No puede ser una contraseña común\n'
            '• No puede ser completamente numérica\n'
            '• No puede ser igual a tu contraseña actual'
        )
    )
    new_password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        help_text=_('Ingresa la misma contraseña que antes, para verificación.')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_messages = PASSWORD_ERROR_MESSAGES.copy()

        # Aplicar mensajes de error personalizados a todos los campos
        for field in ['old_password', 'new_password1', 'new_password2']:
            self.fields[field].error_messages.update(PASSWORD_ERROR_MESSAGES)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError(
                PASSWORD_ERROR_MESSAGES['password_incorrect'],
                code='password_incorrect'
            )
        return old_password

    def clean_new_password1(self):
        old_password = self.cleaned_data.get('old_password')
        new_password = self.cleaned_data.get('new_password1')

        if old_password and new_password and old_password == new_password:
            raise ValidationError(
                PASSWORD_ERROR_MESSAGES['password_same_as_old'],
                code='password_same_as_old'
            )

        try:
            password_validation.validate_password(new_password, self.user)
        except ValidationError as error:
            error_messages = []
            for e in error.error_list:
                if 'too short' in str(e).lower() or 'at least 8' in str(e).lower():
                    error_messages.append(ValidationError(
                        PASSWORD_ERROR_MESSAGES['password_too_short'],
                        code='password_too_short'
                    ))
                elif 'too similar to' in str(e).lower():
                    error_messages.append(ValidationError(
                        PASSWORD_ERROR_MESSAGES['password_too_similar'],
                        code='password_too_similar'
                    ))
                elif 'too common' in str(e).lower():
                    error_messages.append(ValidationError(
                        PASSWORD_ERROR_MESSAGES['password_too_common'],
                        code='password_too_common'
                    ))
                elif 'numeric' in str(e).lower():
                    error_messages.append(ValidationError(
                        PASSWORD_ERROR_MESSAGES['password_entirely_numeric'],
                        code='password_entirely_numeric'
                    ))
                else:
                    error_messages.append(e)
            if error_messages:
                raise ValidationError(error_messages)

        return new_password

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')

        if password1 and password2:
            if password1 != password2:
                raise ValidationError(
                    PASSWORD_ERROR_MESSAGES['password_mismatch'],
                    code='password_mismatch'
                )
            try:
                password_validation.validate_password(password2, self.user)
            except ValidationError as error:
                error_messages = []
                for e in error.error_list:
                    if 'too short' in str(e).lower() or 'at least 8' in str(e).lower():
                        error_messages.append(ValidationError(
                            PASSWORD_ERROR_MESSAGES['password_too_short'],
                            code='password_too_short'
                        ))
                    elif 'too similar to' in str(e).lower():
                        error_messages.append(ValidationError(
                            PASSWORD_ERROR_MESSAGES['password_too_similar'],
                            code='password_too_similar'
                        ))
                    elif 'too common' in str(e).lower():
                        error_messages.append(ValidationError(
                            PASSWORD_ERROR_MESSAGES['password_too_common'],
                            code='password_too_common'
                        ))
                    elif 'numeric' in str(e).lower():
                        error_messages.append(ValidationError(
                            PASSWORD_ERROR_MESSAGES['password_entirely_numeric'],
                            code='password_entirely_numeric'
                        ))
                    else:
                        error_messages.append(e)
                if error_messages:
                    raise ValidationError(error_messages)

        return password2
