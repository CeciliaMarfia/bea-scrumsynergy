# Bob el Alquilador

Sistema web de alquiler de maquinaria desarrollado con Django en Ingeniería de Software II (Facultad de Informática, UNLP). El equipo, ScrumSynergy, trabajó con Scrum. La documentación del proceso (entrevistas, épicas, demos y minutas de sprint) está en [ingenieria-de-software-2](https://github.com/CeciliaMarfia/ingenieria-de-software-2).

## Equipo

- Morena Arias Sánchez
- Sol Justina Arroyo Tabari
- Cecilia Marfia
- Lola Rodríguez

## Funcionalidades

- Catálogo de maquinaria por sucursal, con imágenes.
- Reservas, devoluciones y pagos online (Mercado Pago y Stripe).
- Roles de cliente, empleado y dueño.
- Mapa de sucursales con Folium.

## Tecnologías

Python 3.12, Django 5.2, SQLite, Mercado Pago, Stripe, Folium y Geopy.

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # completar las credenciales
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La aplicación queda en http://127.0.0.1:8000.

Para probar el sistema con datos de ejemplo, ver la [guía de pruebas](PRUEBAS.md). En resumen:

```bash
python manage.py cargar_datos_demo
```

El comando muestra los usuarios y los códigos de retiro. Si no se configuran credenciales de correo en el `.env`, los mails (incluido el código de verificación del inicio de sesión) se muestran en la consola.

## Estructura

- `system/`: configuración del proyecto Django.
- `application/`: modelos, vistas, formularios, templates y comandos de gestión.
- `media/`: imágenes de maquinaria y documentos.
