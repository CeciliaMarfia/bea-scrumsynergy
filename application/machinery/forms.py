from django import forms
from django.forms.widgets import ClearableFileInput
from django.core.files.images import get_image_dimensions
from application.models import Maquina, ImagenMaquina
import imghdr
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime


class MultipleImagesField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", ClearableFileInput(
            attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ImagenMaquinariaForm(forms.ModelForm):
    es_principal = forms.BooleanField(required=False, label='Imagen principal')

    class Meta:
        model = ImagenMaquina
        fields = ['imagen', 'es_principal']


class MultipleFileInput(forms.ClearableFileInput):
    """Widget personalizado para manejar múltiples archivos de imagen"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Campo personalizado para manejar múltiples archivos"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class AltaMaquinariaForm(forms.ModelForm):
    imagenes = MultipleFileField(
        required=True,
        help_text='Seleccione una o más imágenes',
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        error_messages={
            'required': 'Debe seleccionar al menos una imagen.',
            'invalid': 'El archivo seleccionado no es una imagen válida.',
        }
    )

    class Meta:
        model = Maquina
        fields = [
            'codigo', 'nombre', 'marca', 'modelo', 'anio',
            'ubicacion', 'descripcion', 'tipo_cancelacion', 'politica_cancelacion',
            'tipo', 'precio_por_dia', 'permisos_requeridos'
        ]

        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Código único de la máquina'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la máquina'
            }),
            'marca': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Marca'
            }),
            'modelo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Modelo'
            }),
            'anio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1900',
                'max': str(datetime.now().year + 1)
            }),
            'ubicacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ubicación de la máquina'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción detallada de la maquinaria'
            }),
            'tipo_cancelacion': forms.Select(attrs={
                'class': 'form-control'
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'precio_por_dia': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'politica_cancelacion': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Porcentaje de cancelación'
            }),
            'permisos_requeridos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Permisos necesarios para operar (dejar en blanco si no requiere permisos)'
            })
        }

        error_messages = {
            'codigo': {
                'required': 'El código de la máquina es obligatorio.',
                'unique': 'Ya existe una máquina con este código.'
            },
            'nombre': {
                'required': 'El nombre de la máquina es obligatorio.'
            },
            'marca': {
                'required': 'La marca de la máquina es obligatoria.'
            },
            'modelo': {
                'required': 'El modelo de la máquina es obligatorio.'
            },
            'anio': {
                'required': 'El año de la máquina es obligatorio.',
                'invalid': 'Ingrese un año válido.'
            },
            'ubicacion': {
                'required': 'La ubicación de la máquina es obligatoria.'
            },
            'tipo': {
                'required': 'El tipo de máquina es obligatorio.'
            },
            'precio_por_dia': {
                'required': 'El precio por día es obligatorio.',
                'invalid': 'Ingrese un precio válido.',
                'min_value': 'El precio debe ser mayor a 0.'
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_cancelacion'].label = "Tipo de cancelación"
        self.fields['politica_cancelacion'].label = "Porcentaje de cancelación (%)"
        self.fields['precio_por_dia'].label = "Precio por día ($)"
        self.fields['anio'].label = "Año"
        self.fields['permisos_requeridos'].label = "Permisos requeridos"
        self.fields['permisos_requeridos'].required = False
        
        # Configurar el campo de porcentaje personalizado
        self.fields['porcentaje_personalizado'] = forms.IntegerField(
            required=False,
            min_value=10,
            max_value=90,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese un valor entre 10 y 90',
                'type': 'number',
                'min': '10',
                'max': '90',
                'step': '1',
                'id': 'id_porcentaje_personalizado',
                'style': 'cursor: text; background-color: #ffffff;',
                'tabindex': '0',
                'autocomplete': 'off'
            }),
            help_text='Campo opcional, completar en caso de reembolso parcial',
            error_messages={
                'min_value': 'El valor debe ser mayor o igual a 10.',
                'max_value': 'El valor debe ser menor o igual a 90.',
                'invalid': 'Por favor ingrese un número válido.'
            }
        )
        self.fields['porcentaje_personalizado'].label = "Porcentaje personalizado (%)"
        
        # Asegurarse de que el campo de política de cancelación tenga el ID correcto
        self.fields['politica_cancelacion'].widget.attrs.update({
            'id': 'id_politica_cancelacion'
        })

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if Maquina.objects.filter(codigo=codigo).exists():
            raise ValidationError("Ya existe una máquina con este código.")
        return codigo

    def clean_anio(self):
        anio = self.cleaned_data.get('anio')
        if anio and anio > datetime.now().year + 1:
            raise ValidationError('El año no puede ser mayor al año siguiente')
        return anio

    def clean_precio_por_dia(self):
        precio = self.cleaned_data.get('precio_por_dia')
        if precio is not None and precio <= 0:
            raise ValidationError('El precio debe ser mayor a 0')
        return precio

    def clean(self):
        cleaned_data = super().clean()
        tipo_cancelacion = cleaned_data.get('tipo_cancelacion')
        politica_cancelacion = cleaned_data.get('politica_cancelacion')
        porcentaje_personalizado = cleaned_data.get('porcentaje_personalizado')

        if tipo_cancelacion == 'total':
            cleaned_data['politica_cancelacion'] = 100
        elif tipo_cancelacion == 'sin_reembolso':
            cleaned_data['politica_cancelacion'] = 0
        elif tipo_cancelacion == 'parcial':
            if porcentaje_personalizado is not None:
                cleaned_data['politica_cancelacion'] = porcentaje_personalizado

        return cleaned_data

    def clean_imagenes(self):
        imagenes = self.files.getlist('imagenes')
        if not imagenes:
            raise ValidationError(
                "Debe cargar al menos una imagen de la maquinaria.")

        for imagen in imagenes:
            # Verificar el tamaño
            if imagen.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError(
                    "El tamaño de cada imagen no debe exceder 5MB.")

            # Verificar que sea una imagen
            if not imagen.content_type.startswith('image/'):
                raise ValidationError("Todos los archivos deben ser imágenes.")

        return imagenes

    def save(self, commit=True):
        try:
            with transaction.atomic():
                # Primero guardamos la maquinaria
                maquina = super().save(commit=True)

                # Luego procesamos las imágenes
                imagenes = self.files.getlist('imagenes')
                if imagenes:
                    primera_imagen = True
                    for imagen in imagenes:
                        ImagenMaquina.objects.create(
                            maquina=maquina,
                            imagen=imagen,
                            es_principal=primera_imagen
                        )
                        primera_imagen = False

                return maquina
        except Exception as e:
            raise ValidationError(f"Error al guardar la maquinaria: {str(e)}")


class RegistrarDevolucionForm(forms.Form):
    codigo = forms.CharField(label='ID de la máquina', max_length=100)
    fecha_devolucion = forms.DateField(label='Fecha de devolución', widget=forms.DateInput(attrs={'type': 'date'}))
