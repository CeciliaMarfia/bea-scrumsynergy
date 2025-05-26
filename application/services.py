import random
import time
from decimal import Decimal

class BancoService:
    """
    Servicio que simula la conexión con el banco para procesar pagos.
    """
    
    @staticmethod
    def validar_tarjeta(numero_tarjeta):
        """
        Simula la validación de una tarjeta de crédito.
        Para pruebas:
        - 1234: Tarjeta válida con fondos
        - 7891: Tarjeta válida sin fondos
        - Cualquier otro número: Tarjeta inválida
        """
        # Simular latencia de red
        time.sleep(1)
        
        # Simular fallo de conexión aleatoriamente (10% de probabilidad)
        if random.random() < 0.1:
            raise ConnectionError("No se pudo conectar con el servidor del banco")
        
        # Validar número de tarjeta
        return numero_tarjeta == "1234" or numero_tarjeta == "7891"

    @staticmethod
    def verificar_fondos(numero_tarjeta, monto):
        """
        Simula la verificación de fondos disponibles.
        """
        # Simular latencia de red
        time.sleep(0.5)
        
        # La tarjeta 1234 siempre tiene fondos, 7891 nunca tiene fondos
        return numero_tarjeta == "1234"

    @staticmethod
    def procesar_pago(numero_tarjeta, monto):
        """
        Simula el procesamiento del pago.
        Retorna un diccionario con el resultado de la operación.
        """
        try:
            # Validar tarjeta
            if not BancoService.validar_tarjeta(numero_tarjeta):
                return {
                    'exitoso': False,
                    'error': 'tarjeta_invalida',
                    'mensaje': 'La tarjeta ingresada no es válida'
                }

            # Verificar fondos
            if not BancoService.verificar_fondos(numero_tarjeta, monto):
                return {
                    'exitoso': False,
                    'error': 'fondos_insuficientes',
                    'mensaje': 'La tarjeta no tiene fondos suficientes'
                }

            # Generar número de transacción único
            numero_transaccion = f"TX-{int(time.time())}-{random.randint(1000, 9999)}"

            return {
                'exitoso': True,
                'numero_transaccion': numero_transaccion,
                'mensaje': 'Pago procesado exitosamente'
            }

        except ConnectionError:
            return {
                'exitoso': False,
                'error': 'error_conexion',
                'mensaje': 'No se pudo conectar con el servidor del banco'
            }
        except Exception as e:
            return {
                'exitoso': False,
                'error': 'otro',
                'mensaje': f'Error al procesar el pago: {str(e)}'
            } 