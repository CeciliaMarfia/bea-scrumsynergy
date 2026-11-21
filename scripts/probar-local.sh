#!/bin/bash
# Prepara y levanta Bob el Alquilador con datos de ejemplo en http://127.0.0.1:8000
# Uso (desde la carpeta del proyecto): bash scripts/probar-local.sh
set -e

cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Instalando uv (gestor de Python)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Preparando Python 3.12 y las dependencias"
[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -q -r requirements.txt

[ -f .env ] || cp .env.example .env

PRIMERA_VEZ=0
[ -f db.sqlite3 ] || PRIMERA_VEZ=1

echo "==> Actualizando la base de datos"
.venv/bin/python manage.py migrate -v 0
if [ "$PRIMERA_VEZ" = "1" ]; then
  .venv/bin/python manage.py cargar_datos_demo
fi

echo ""
echo "==> Listo. Abrí http://127.0.0.1:8000 en el navegador."
echo "    El código de verificación del inicio de sesión aparece en esta ventana."
echo "    Para detener el servidor: Control + C"
echo ""
.venv/bin/python manage.py runserver
