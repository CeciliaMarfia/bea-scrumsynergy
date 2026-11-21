# Guía para probar Bob el Alquilador

Esta guía explica cómo levantar el sistema en una computadora propia con datos de ejemplo y qué recorridos probar. No hace falta configurar correo ni Mercado Pago.

## 1. Levantar el sistema

### macOS y Linux

Requisito: tener `git` instalado.

```bash
git clone https://github.com/CeciliaMarfia/bea-scrumsynergy.git
cd bea-scrumsynergy
bash scripts/probar-local.sh
```

El script instala [uv](https://docs.astral.sh/uv/) si no está, prepara Python 3.12 con las dependencias, crea la base de datos y carga los datos de ejemplo. La primera vez tarda unos minutos.

### Windows

Requisitos: `git` y [uv](https://docs.astral.sh/uv/getting-started/installation/). En PowerShell:

```powershell
git clone https://github.com/CeciliaMarfia/bea-scrumsynergy.git
cd bea-scrumsynergy
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py cargar_datos_demo
.venv\Scripts\python.exe manage.py runserver
```

### Una vez iniciado

Abrir http://127.0.0.1:8000 en el navegador y dejar abierta la terminal: ahí se muestran los correos que envía el sistema, incluido el código de verificación del inicio de sesión.

Para detener el servidor: `Control + C`. Para volver a levantarlo, se repite el último comando; los datos se conservan. Para empezar de cero con los datos de ejemplo, borrar el archivo `db.sqlite3` antes de levantarlo.

## 2. Usuarios de prueba

La contraseña de todos los usuarios es `Bob12345!`.

| Rol | Usuario |
|---|---|
| Dueño | dueno@bob.com |
| Empleado | empleado@bob.com |
| Cliente | ana@mail.com |
| Cliente | beto@mail.com |

Después de ingresar usuario y contraseña, el sistema pide un código de 6 dígitos. El código aparece en la terminal, dentro del correo "Código de verificación".

## 3. Datos de ejemplo

| Máquina | Código | Situación inicial |
|---|---|---|
| Tractor John Deere | M001 | Reserva pagada de Ana que empieza hoy |
| Sembradora | M002 | Reserva pagada de Ana que empieza en 10 días |
| Excavadora | M003 | Alquiler en curso de Beto |
| Cortadora de césped | M004 | Reserva de Ana pendiente de pago |

Los códigos de retiro de las reservas se muestran en la terminal al cargar los datos y en la sección **Mis reservas** de Ana.

## 4. Cómo funcionan reservas y alquileres

- El cliente **reserva** online, paga y recibe un **código de retiro**.
- Cuando retira la máquina en la sucursal, el empleado ingresa el código en **Registrar Retiro** y la reserva pasa a ser un **alquiler en curso**.
- El **alquiler presencial** lo registra el empleado en la sucursal y comienza el mismo día.
- Al **devolver** la máquina, el empleado registra la devolución con el código de la máquina y esta pasa a mantenimiento.

## 5. Recorridos para probar

Conviene usar una ventana normal para el cliente y una de incógnito para el empleado o el dueño, así se mantienen las dos sesiones abiertas.

### Cliente (ana@mail.com)

1. En **Mis reservas** se ven las tres reservas. Las pagadas muestran su código de retiro.
2. Pagar la reserva de la cortadora de césped con una tarjeta nueva, por ejemplo `4242424242424242`, CVV `123`, vencimiento `12/2030`. La reserva queda pagada y muestra su código de retiro.
3. En el detalle de cualquier máquina, el cliente solo ve el botón **Reservar**.
4. Reservar una máquina disponible y cancelar la reserva desde **Mis reservas**.

Tarjetas que simulan errores del banco: `1111111111111111` (fondos insuficientes) y `2222222222222222` (falla de conexión).

### Empleado (empleado@bob.com)

1. **Registrar Retiro** con el código de la reserva del tractor: la reserva pasa a ser un alquiler en curso. En **Mis alquileres** de Ana aparece como "En curso".
2. **Registrar Retiro** con el código de la sembradora: el sistema lo rechaza porque la reserva todavía no comenzó.
3. **Registrar Devolución** con el código `M003`: se cierra el alquiler de Beto y la excavadora pasa a mantenimiento.
4. **Registrar Alquiler** de una máquina disponible para `beto@mail.com` con fecha de inicio hoy. Con una fecha futura, el sistema indica que corresponde registrar una reserva.
5. **Reservas Activas** y **Alquileres Activos** muestran cada operación en su listado.

### Dueño (dueno@bob.com)

1. En **Gestionar Maquinaria**, cambiar la excavadora de "En Mantenimiento" a "Disponible".
2. Ver el historial de alquileres de una máquina y el perfil del empleado con las operaciones que gestionó.

## 6. Tests automáticos

```bash
.venv/bin/python manage.py test application
```

En Windows: `.venv\Scripts\python.exe manage.py test application`.
