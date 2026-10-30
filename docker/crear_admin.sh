#!/usr/bin/env bash
# Crea un usuario administrador (con el sistema iniciado).
. "$(dirname "$0")/_entorno.sh" || exit 1
docker compose exec app python empaquetado/launcher.py crear-admin
