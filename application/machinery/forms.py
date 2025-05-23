from django import forms
from django.forms.widgets import Input
from application.models import Maquina, ImagenMaquina

class MultiImageFileInput(Input):
    input_type = 'file'
    needs_multipart_form = True
    
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['multiple'] = 'multiple'
        attrs['accept'] = 'image/*'
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        else:
            return files.get(name)

class ImagenMaquinariaForm(forms.ModelForm):
    es_principal = forms.BooleanField(required=False, label='Imagen principal')
    
    class Meta:
        model = ImagenMaquina
        fields = ['imagen', 'es_principal']

class AltaMaquinariaForm(forms.ModelForm):
    imagenes = forms.FileField(
        widget=MultiImageFileInput(),
        label='Imágenes',
        help_text='Seleccione una o más imágenes. Al menos una es obligatoria.',
        required=True
    )

    class Meta:
        model = Maquina
        fields = ['codigo', 'nombre', 'marca', 'modelo', 'anio', 'ubicacion', 
                 'tipo_cancelacion', 'politica_cancelacion', 'tipo', 
                 'precio_por_dia', 'permisos_requeridos']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_cancelacion'].label = "Tipo de cancelación"
        self.fields['politica_cancelacion'].label = "Porcentaje de cancelación (%)"
        self.fields['precio_por_dia'].label = "Precio por día ($)"
        self.fields['anio'].label = "Año"

    def clean(self):
        cleaned_data = super().clean()
        tipo_cancelacion = cleaned_data.get('tipo_cancelacion')
        politica_cancelacion = cleaned_data.get('politica_cancelacion')

        if tipo_cancelacion == 'total':
            cleaned_data['politica_cancelacion'] = 100
        elif tipo_cancelacion == 'sin_reembolso':
            cleaned_data['politica_cancelacion'] = 0
        elif tipo_cancelacion == 'parcial':
            if politica_cancelacion is None:
                raise forms.ValidationError("Debe ingresar un porcentaje para reembolso parcial")
            if politica_cancelacion < 10 or politica_cancelacion > 90:
                raise forms.ValidationError("El porcentaje de reembolso parcial debe estar entre 10% y 90%")

        # Validar que se haya subido al menos una imagen
        imagenes = self.files.getlist('imagenes')
        if not imagenes:
            raise forms.ValidationError("Debe cargar al menos una imagen de la maquinaria.")

        return cleaned_data

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if Maquina.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Ya existe una máquina con este código.")
        return codigo

    def save(self, commit=True):
        maquina = super().save(commit=commit)
        
        # Guardar las imágenes
        imagenes = self.files.getlist('imagenes')
        if imagenes:
            # La primera imagen será la principal
            primera_imagen = True
            for imagen in imagenes:
                ImagenMaquina.objects.create(
                    maquina=maquina,
                    imagen=imagen,
                    es_principal=primera_imagen
                )
                primera_imagen = False
        
        return maquina
