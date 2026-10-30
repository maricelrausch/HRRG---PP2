#!/usr/bin/env bash
# Detiene el sistema. Usuarios, datos, claves y modelos se conservan.
. "$(dirname "$0")/_entorno.sh" || exit 1
docker compose down && echo "Sistema detenido."
