from django.contrib import admin
from .models import Perfil, HomeVideo, Maquina, ValoracionEmpleado


@admin.register(HomeVideo)
class HomeVideoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'activo', 'fecha_subida')
    list_filter = ('activo',)
    search_fields = ('titulo',)
    ordering = ('-fecha_subida',)


# Registrar otros modelos si es necesario
admin.site.register(Perfil)
admin.site.register(Maquina)
admin.site.register(ValoracionEmpleado)
