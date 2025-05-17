from django import forms

class AltaMaquinariaForm(forms.Form):
    id = forms.IntegerField(label="ID")
    nombre = forms.CharField(max_length=100)
    marca = forms.CharField(max_length=100)
    modelo = forms.CharField(max_length=100)
    anio = forms.IntegerField(label="Año")
    ubicacion = forms.CharField(max_length=200)
    politica_cancelacion = forms.FloatField(label="Política de cancelación (%)")
    tipo = forms.ChoiceField(choices=[
        ('agricola', 'Agrícola'),
        ('construccion', 'Construcción'),
        ('mineria', 'Minería'),
        ('jardineria', 'Jardinería'),
        ('otros', 'Otros'),
    ])
    precio_por_dia = forms.DecimalField(label="Precio por día ($)", max_digits=15, decimal_places=4)
    permisos_requeridos = forms.CharField(widget=forms.Textarea)
    imagen = forms.ImageField()
