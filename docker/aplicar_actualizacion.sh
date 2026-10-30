#!/usr/bin/env bash
# Aplica una actualización sin internet (imagenes/ingenia_app.tar).
. "$(dirname "$0")/_entorno.sh" || exit 1
set -e
[ -f imagenes/ingenia_app.tar ] || { echo "No se encontró imagenes/ingenia_app.tar"; exit 1; }
docker load -i imagenes/ingenia_app.tar
docker compose up -d --no-build
echo "LISTO. Sistema actualizado."
