"""
URL configuration for system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from application import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verificar-codigo/', views.verificar_codigo, name='verificar_codigo'),
    path('verificar-email/<str:token>/',
         views.verificar_email, name='verificar_email'),
    path('reenviar-verificacion/', views.reenviar_verificacion,
         name='reenviar_verificacion'),
    path('logout/', views.logout, name='logout'),
    path('perfil/', views.perfil, name='perfil'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('eliminar-perfil/', views.eliminar_perfil, name='eliminar_perfil'),
    path('cambiar-password/', views.cambiar_password, name='cambiar_password'),
    path('password-reset/', views.CustomPasswordResetView.as_view(),
         name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
    path('registrar-empleado/', views.registrar_empleado,
         name='registrar_empleado'),
    path('lista-empleados/', views.lista_empleados, name='lista_empleados'),
    path('eliminar-empleado/<int:empleado_id>/',
         views.eliminar_empleado, name='eliminar_empleado'),
    path('ver-perfil-empleado/<int:empleado_id>/',
         views.ver_perfil_empleado, name='ver_perfil_empleado'),
    path('registrar-maquinaria/', views.registrar_maquinaria,
         name='registrar_maquinaria'),
    path('lista-maquinaria/', views.lista_maquinaria, name='lista_maquinaria'),
    path('detalle-maquinaria/<int:maquina_id>/',
         views.detalle_maquinaria, name='detalle_maquinaria'),
    path('reservar-maquinaria/<int:maquina_id>/',
         views.reservar_maquinaria, name='reservar_maquinaria'),
    path('mis-reservas/', views.mis_reservas, name='mis_reservas'),
    path('historial-reservas/', views.historial_reservas,
         name='historial_reservas'),
    path('cancelar-reserva/<str:numero_reserva>/',
         views.cancelar_reserva, name='cancelar_reserva'),
    path('detalle-reserva/<int:reserva_id>/',
         views.detalle_reserva, name='detalle_reserva'),
    path('pagar-reserva/<int:reserva_id>/',
         views.pagar_reserva, name='pagar_reserva'),
    path('procesar-pago/<int:reserva_id>/',
         views.procesar_pago, name='procesar_pago'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-failure/', views.payment_failure, name='payment_failure'),
    path('payment-pending/', views.payment_pending, name='payment_pending'),
    path('crear-preference/<int:reserva_id>/',
         views.crear_preference, name='crear_preference'),
    path('generar-preference-mercadopago/<int:reserva_id>/',
         views.generar_preference_mercadopago, name='generar_preference_mercadopago'),
    path('registrar-cliente/', views.registrar_cliente, name='registrar_cliente'),
    path('lista-clientes/', views.lista_clientes, name='lista_clientes'),
    path('ver-perfil-cliente/<int:cliente_id>/',
         views.ver_perfil_cliente, name='ver_perfil_cliente'),
    path('agregar-permiso/', views.agregar_permiso, name='agregar_permiso'),
    path('lista-permisos/', views.lista_permisos, name='lista_permisos'),
    path('eliminar-permiso/<int:permiso_id>/',
         views.eliminar_permiso, name='eliminar_permiso'),
    path('limpiar-datos/', views.limpiar_datos, name='limpiar_datos'),
    path('sobre-nosotros/', views.sobre_nosotros, name='sobre_nosotros'),
    path('sucursales/', views.lista_ubicaciones, name='lista_ubicaciones'),
    path('sucursales/administrar/', views.administrar_sucursales,
         name='administrar_sucursales'),
    path('sucursales/agregar/', views.agregar_sucursal, name='agregar_sucursal'),
    path('sucursales/editar/<int:sucursal_id>/',
         views.editar_sucursal, name='editar_sucursal'),
    path('sucursales/eliminar/<int:sucursal_id>/',
         views.eliminar_sucursal, name='eliminar_sucursal'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
