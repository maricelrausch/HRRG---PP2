#!/usr/bin/env bash
# Actualiza a la última versión y reinicia (registro: descarga | sin registro: reconstruye).
. "$(dirname "$0")/_entorno.sh" || exit 1
set -e
if [ "$REGISTRO" = 1 ]; then
  docker compose pull
  docker compose up -d --no-build
elif [ ! -f ../backend/app.py ]; then
  echo "Esta instalación no tiene el código fuente. Use ./aplicar_actualizacion.sh"; exit 1
else
  docker compose build app
  docker compose pull ollama caddy
  docker compose up -d
fi
echo "LISTO. Sistema actualizado."
