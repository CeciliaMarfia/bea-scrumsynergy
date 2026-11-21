import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from application.models import Maquina, Reserva, Role


def dias(n):
    return timezone.localdate() + datetime.timedelta(days=n)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReservasYAlquileresTests(TestCase):

    def crear_usuario(self, username, rol):
        user = User.objects.create_user(username, f'{username}@mail.com', 'Clave1234!')
        user.perfil.role, _ = Role.objects.get_or_create(name=rol)
        user.perfil.email_verificado = True
        user.perfil.save()
        return user

    def setUp(self):
        self.ana = self.crear_usuario('ana', Role.CLIENTE)
        self.beto = self.crear_usuario('beto', Role.CLIENTE)
        self.empleado = self.crear_usuario('empleado', Role.EMPLEADO)
        self.maquina = Maquina.objects.create(
            codigo='M001', nombre='Tractor', marca='John Deere', modelo='5075E', anio=2020,
            ubicacion='La Plata', tipo='agricola', precio_por_dia=Decimal('100'),
            descripcion='Tractor', tipo_cancelacion='total')

    def reservar(self, cliente, inicio, fin):
        self.client.force_login(cliente)
        self.client.post(reverse('reservar_maquinaria', args=[self.maquina.id]), {
            'maquina': self.maquina.id, 'fecha_inicio': inicio, 'fecha_fin': fin})
        return Reserva.objects.filter(cliente=cliente).latest('id')

    def alquiler_presencial(self, cliente, inicio, fin):
        self.client.force_login(self.empleado)
        self.client.post(reverse('alquiler_presencial_detalle', args=[self.maquina.id]), {
            'fecha_inicio': inicio, 'fecha_fin': fin, 'email_cliente': cliente.email})
        return Reserva.objects.filter(cliente=cliente).latest('id')

    def registrar_retiro(self, codigo):
        self.client.force_login(self.empleado)
        return self.client.post(reverse('registrar_retiro'), {'codigo_retiro': codigo}, follow=True)

    def estado_maquina(self):
        self.maquina.refresh_from_db()
        return self.maquina.estado

    def test_reserva_online_queda_como_reserva(self):
        reserva = self.reservar(self.ana, dias(5), dias(6))
        self.assertEqual(reserva.tipo, Reserva.TIPO_RESERVA)
        self.assertEqual(self.estado_maquina(), 'reservada')

    def test_reserva_no_desaparece_si_otro_cliente_alquila(self):
        self.reservar(self.ana, dias(10), dias(12))
        self.alquiler_presencial(self.beto, dias(0), dias(2))
        self.assertEqual(self.estado_maquina(), 'alquilada')

        self.client.force_login(self.ana)
        self.assertEqual(len(self.client.get(reverse('mis_reservas')).context['reservas']), 1)
        self.assertEqual(len(self.client.get(reverse('mis_alquileres')).context['reservas']), 0)

    def test_retiro_convierte_la_reserva_en_alquiler(self):
        reserva = self.reservar(self.ana, dias(0), dias(2))
        reserva.estado = 'pagada'
        reserva.save()

        self.registrar_retiro(reserva.codigo_retiro.lower())
        reserva.refresh_from_db()
        self.assertEqual(reserva.tipo, Reserva.TIPO_ALQUILER)
        self.assertIsNotNone(reserva.fecha_retiro)
        self.assertEqual(reserva.empleado_gestor, self.empleado)
        self.assertEqual(self.estado_maquina(), 'alquilada')

    def test_retiro_rechaza_reserva_sin_pagar_o_antes_de_fecha(self):
        sin_pagar = self.reservar(self.ana, dias(0), dias(1))
        self.registrar_retiro(sin_pagar.codigo_retiro)
        sin_pagar.refresh_from_db()
        self.assertEqual(sin_pagar.tipo, Reserva.TIPO_RESERVA)

        futura = self.reservar(self.beto, dias(10), dias(11))
        futura.estado = 'pagada'
        futura.save()
        self.registrar_retiro(futura.codigo_retiro)
        futura.refresh_from_db()
        self.assertEqual(futura.tipo, Reserva.TIPO_RESERVA)

    def test_alquiler_presencial_debe_empezar_hoy(self):
        self.client.force_login(self.empleado)
        self.client.post(reverse('alquiler_presencial_detalle', args=[self.maquina.id]), {
            'fecha_inicio': dias(3), 'fecha_fin': dias(4), 'email_cliente': self.ana.email})
        self.assertFalse(Reserva.objects.exists())

        alquiler = self.alquiler_presencial(self.ana, dias(0), dias(1))
        self.assertEqual(alquiler.tipo, Reserva.TIPO_ALQUILER)
        self.assertEqual(alquiler.estado, 'pagada')

    def test_cancelar_reserva_mantiene_estado_si_hay_otras(self):
        reserva_ana = self.reservar(self.ana, dias(1), dias(2))
        self.reservar(self.beto, dias(6), dias(7))

        self.client.force_login(self.ana)
        self.client.post(reverse('cancelar_reserva', args=[reserva_ana.numero_reserva]))
        reserva_ana.refresh_from_db()
        self.assertEqual(reserva_ana.estado, 'cancelada')
        self.assertEqual(self.estado_maquina(), 'reservada')

    def test_cancelar_alquiler_solo_por_post(self):
        alquiler = self.alquiler_presencial(self.ana, dias(0), dias(1))
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse('cancelar_alquiler', args=[alquiler.id]))
        self.assertEqual(respuesta.status_code, 405)
        alquiler.refresh_from_db()
        self.assertEqual(alquiler.estado, 'pagada')

    def test_devolucion_cierra_el_alquiler_y_no_las_reservas_futuras(self):
        alquiler = self.alquiler_presencial(self.ana, dias(0), dias(1))
        reserva = self.reservar(self.beto, dias(6), dias(7))
        reserva.estado = 'pagada'
        reserva.save()

        self.client.force_login(self.empleado)
        self.client.post(reverse('registrar_devolucion'), {'codigo': 'M001'})
        alquiler.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(alquiler.estado, 'devuelta')
        self.assertEqual(reserva.estado, 'pagada')
        self.assertEqual(self.estado_maquina(), 'mantenimiento')

        self.client.force_login(self.beto)
        self.assertEqual(len(self.client.get(reverse('mis_reservas')).context['reservas']), 1)

    def test_maquina_vuelve_a_reservada_al_salir_de_mantenimiento(self):
        self.reservar(self.ana, dias(10), dias(11))
        Maquina.objects.filter(id=self.maquina.id).update(estado='mantenimiento')

        self.client.force_login(self.empleado)
        self.client.post(reverse('actualizar_estado_maquina', args=[self.maquina.id]),
                         data='{"estado": "disponible"}', content_type='application/json',
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(self.estado_maquina(), 'reservada')

    def test_historiales_del_personal_separan_reservas_y_alquileres(self):
        self.reservar(self.ana, dias(10), dias(12))
        self.alquiler_presencial(self.beto, dias(0), dias(2))

        self.client.force_login(self.empleado)
        reservas = self.client.get(reverse('historial_reservas')).context['reservas']
        alquileres = self.client.get(reverse('historial_alquileres')).context['alquileres']
        self.assertEqual([r.tipo for r in reservas], [Reserva.TIPO_RESERVA])
        self.assertEqual([a.tipo for a in alquileres], [Reserva.TIPO_ALQUILER])

    def test_cliente_web_alquilar_redirige_a_reservar(self):
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse('alquilar_maquinaria_detalle', args=[self.maquina.id]))
        self.assertRedirects(respuesta, reverse('reservar_maquinaria', args=[self.maquina.id]),
                             fetch_redirect_response=False)
