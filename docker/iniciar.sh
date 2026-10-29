#!/usr/bin/env bash
# Inicia IngenIA Salud – Triage (Ollama + app + Caddy).
. "$(dirname "$0")/_entorno.sh" || exit 1
set -e
if ! docker image inspect "$HRRG_IMAGEN:$APP_VERSION" >/dev/null 2>&1; then
  if [ -f imagenes/ingenia_imagenes.tar ]; then
    echo "Cargando las imágenes de Docker por primera vez..."; docker load -i imagenes/ingenia_imagenes.tar
  elif [ "$REGISTRO" = 1 ]; then
    echo "Descargando la imagen del sistema..."; docker compose pull app
  elif [ -f ../backend/app.py ]; then
    echo "Construyendo la imagen con el código del repo..."; docker compose build app
  else
    echo "No se encontró la imagen del sistema (imagenes/ingenia_imagenes.tar)."; exit 1
  fi
fi
docker compose up -d --no-build
set +e
echo "Esperando a que el sistema esté listo (la primera vez puede tardar 1-3 minutos)..."
for _ in $(seq 1 72); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' ingenia-app 2>/dev/null)" = healthy ] && {
    echo; echo "[OK] Sistema disponible"
    echo "     En este equipo:   http://localhost:5000"
    echo "     Desde otras PCs:  https://<nombre o IP del servidor>   ($HRRG_SITIO)"
    echo "     Si es la primera vez: ./crear_admin.sh"
    exit 0; }
  sleep 5
done
echo "El sistema tarda más de lo normal. Revise: docker compose logs app"; exit 1
