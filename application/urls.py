from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),
    path('verificar-email/<str:token>/',
         views.verificar_email, name='verificar_email'),
    path('verificar-codigo/', views.verificar_codigo, name='verificar_codigo'),
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    path('perfil/eliminar/', views.eliminar_perfil, name='eliminar_perfil'),
    path('permisos/agregar/', views.agregar_permiso, name='agregar_permiso'),
    path('permisos/eliminar/<int:permiso_id>/',
         views.eliminar_permiso, name='eliminar_permiso'),

    # Employee management
    path('empleados/registrar/', views.registrar_empleado,
         name='registrar_empleado'),
    path('empleados/', views.lista_empleados, name='lista_empleados'),
    path('empleados/eliminar/<int:empleado_id>/',
         views.eliminar_empleado, name='eliminar_empleado'),
    path('empleados/<int:empleado_id>/perfil/',
         views.ver_perfil_empleado, name='ver_perfil_empleado'),

    # Client management
    path('clientes/registrar/', views.registrar_cliente, name='registrar_cliente'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/<int:cliente_id>/perfil/',
         views.ver_perfil_cliente, name='ver_perfil_cliente'),

    # Machinery management
    path('maquinaria/registrar/', views.registrar_maquinaria,
         name='registrar_maquinaria'),
    path('maquinaria/', views.lista_maquinaria, name='lista_maquinaria'),
    path('maquinaria/<int:maquina_id>/',
         views.detalle_maquinaria, name='detalle_maquinaria'),
    path('maquinaria/<int:maquina_id>/reservar/',
         views.reservar_maquinaria, name='reservar_maquinaria'),

    # Reservations
    path('reservas/historial/', views.historial_reservas,
         name='historial_reservas'),
    path('mis-reservas/', views.mis_reservas, name='mis_reservas'),
    path('reserva/<str:numero_reserva>/cancelar/',
         views.cancelar_reserva, name='cancelar_reserva'),
    path('reserva/<int:reserva_id>/pagar/',
         views.pagar_reserva, name='pagar_reserva'),
    path('reserva/<int:reserva_id>/procesar-pago/',
         views.procesar_pago, name='procesar_pago'),
    path('reserva/<int:reserva_id>/',
         views.detalle_reserva, name='detalle_reserva'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failure/', views.payment_failure, name='payment_failure'),
    path('payment/pending/', views.payment_pending, name='payment_pending'),
    path('limpiar-datos/', views.limpiar_datos, name='limpiar_datos'),
]
