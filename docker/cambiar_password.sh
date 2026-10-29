#!/usr/bin/env bash
# Cambia la contraseña de un usuario y lo desbloquea (con el sistema iniciado).
. "$(dirname "$0")/_entorno.sh" || exit 1
docker compose exec app python empaquetado/launcher.py cambiar-password
