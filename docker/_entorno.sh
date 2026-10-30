#!/usr/bin/env bash
# Carga la configuración de .env y los valores por defecto. Lo usan los demás scripts.
cd "$(dirname "$0")" || exit 1
if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${APP_VERSION:=0.1.0}" "${OLLAMA_VERSION:=latest}" "${CADDY_VERSION:=2}"
: "${HRRG_IMAGEN:=ingenia-salud-triage}" "${HRRG_SITIO:=localhost}" "${MEDGEMMA_MODELO:=medgemma:4b}"
case "$HRRG_IMAGEN" in */*) REGISTRO=1 ;; *) REGISTRO=0 ;; esac
if ! docker info >/dev/null 2>&1; then
  echo "Docker no está funcionando (o falta permiso: use sudo o agregue el usuario al grupo docker)."
  exit 1
fi
