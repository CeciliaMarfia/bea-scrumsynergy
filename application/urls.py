from django.urls import path
from . import views
from application.views import machinery_registration

# -- codigo para el alta de maquinaria --
urlpatterns = [
    path('machinery_registration/', views.machinery_registration,
         name='machinery_registration'),
    path('permisos/', views.lista_permisos, name='lista_permisos'),
    path('permisos/agregar/', views.agregar_permiso, name='agregar_permiso'),
    path('permisos/<int:permiso_id>/eliminar/',
         views.eliminar_permiso, name='eliminar_permiso'),
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    path('perfil/eliminar/', views.eliminar_perfil, name='eliminar_perfil'),
    path('maquinaria/<int:maquina_id>/reservar/', views.reservar_maquinaria, name='reservar_maquinaria'),
    path('maquinaria/<int:maquina_id>/', views.detalle_maquinaria, name='detalle_maquinaria'),
    path('maquinaria/', views.lista_maquinaria, name='lista_maquinaria'),
    path('mis-reservas/', views.mis_reservas, name='mis_reservas'),
    path('reserva/<str:numero_reserva>/cancelar/', views.cancelar_reserva, name='cancelar_reserva'),
]
# ---
