from django import forms
from application.models import Maquina

class AltaMaquinariaForm(forms.ModelForm):
    class Meta:
        model = Maquina # esto sale de models.py
        fields = '__all__'  

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['politica_cancelacion'].label = "Política de cancelación (%)"
        self.fields['precio_por_dia'].label = "Precio por día ($)"
        self.fields['anio'].label = "Año"

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if Maquina.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Ya existe una máquina con este código.")
        return codigo
