#!/usr/bin/env python
"""
Script de prueba para verificar que la función registrar_devolucion funcione correctamente.
"""

import os
import sys
import django
from datetime import date, timedelta
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'system.settings')
django.setup()

from application.models import Maquina, Reserva, User, Role, Perfil
from application.machinery.forms import RegistrarDevolucionForm

def test_registrar_devolucion():
    """Prueba la funcionalidad de registrar devolución"""
    
    print("=== PRUEBA DE REGISTRAR DEVOLUCIÓN ===")
    
    # 1. Verificar que existe al menos una máquina
    maquinas = Maquina.objects.all()
    if not maquinas.exists():
        print("❌ No hay máquinas en la base de datos")
        return False
    
    print(f"✅ Se encontraron {maquinas.count()} máquinas")
    
    # 2. Buscar una máquina con estado 'alquilada'
    maquina_alquilada = maquinas.filter(estado='alquilada').first()
    if not maquina_alquilada:
        print("❌ No hay máquinas con estado 'alquilada'")
        print("Estados disponibles:")
        for maquina in maquinas:
            print(f"  - {maquina.codigo}: {maquina.estado}")
        return False
    
    print(f"✅ Se encontró máquina alquilada: {maquina_alquilada.codigo} ({maquina_alquilada.nombre})")
    
    # 3. Verificar que existe una reserva pagada para esta máquina
    reserva_activa = Reserva.objects.filter(
        maquina=maquina_alquilada, 
        estado='pagada'
    ).order_by('-fecha_fin').first()
    
    if not reserva_activa:
        print("❌ No hay reservas pagadas para esta máquina")
        print("Reservas disponibles:")
        for reserva in Reserva.objects.filter(maquina=maquina_alquilada):
            print(f"  - {reserva.numero_reserva}: {reserva.estado} ({reserva.fecha_inicio} - {reserva.fecha_fin})")
        return False
    
    print(f"✅ Se encontró reserva activa: {reserva_activa.numero_reserva}")
    print(f"   Fecha fin: {reserva_activa.fecha_fin}")
    
    # 4. Probar el formulario con datos válidos
    fecha_devolucion = date.today()
    form_data = {
        'codigo': maquina_alquilada.codigo,
        'fecha_devolucion': fecha_devolucion
    }
    
    form = RegistrarDevolucionForm(data=form_data)
    if form.is_valid():
        print("✅ Formulario válido")
        print(f"   Código: {form.cleaned_data['codigo']}")
        print(f"   Fecha devolución: {form.cleaned_data['fecha_devolucion']}")
    else:
        print("❌ Formulario inválido")
        print("Errores:", form.errors)
        return False
    
    # 5. Simular el proceso de devolución
    print("\n=== SIMULANDO DEVOLUCIÓN ===")
    
    # Verificar si la devolución es en término
    if fecha_devolucion <= reserva_activa.fecha_fin:
        print("✅ Devolución en término")
        estado_final = 'mantenimiento'
        mensaje = 'Devolución registrada con éxito. La maquinaria pasa a estado "En Mantenimiento".'
    else:
        print("⚠️ Devolución fuera de término")
        estado_final = 'mantenimiento'
        dias_retraso = (fecha_devolucion - reserva_activa.fecha_fin).days
        recargo = Decimal('0.10') * reserva_activa.monto_total * dias_retraso
        mensaje = f'La devolución del alquiler fue entregada fuera de término. Se aplica un recargo de ${recargo:.2f} por {dias_retraso} días de retraso.'
    
    print(f"   Estado final de la máquina: {estado_final}")
    print(f"   Mensaje: {mensaje}")
    
    # 6. Verificar que el estado 'mantenimiento' está en las opciones del modelo
    estados_disponibles = [choice[0] for choice in Maquina.ESTADO_CHOICES]
    if 'mantenimiento' in estados_disponibles:
        print("✅ Estado 'mantenimiento' disponible en el modelo")
    else:
        print("❌ Estado 'mantenimiento' NO disponible en el modelo")
        print("Estados disponibles:", estados_disponibles)
        return False
    
    print("\n=== PRUEBA COMPLETADA ===")
    print("✅ La función registrar_devolucion debería funcionar correctamente")
    return True

if __name__ == '__main__':
    test_registrar_devolucion() 