#!/usr/bin/env bash
# Copia los modelos de Ollama desde una carpeta (sin internet). Uso: ./cargar_modelos.sh [carpeta]
. "$(dirname "$0")/_entorno.sh" || exit 1
ORIGEN="${1:-ollama_modelos}"
[ -d "$ORIGEN/manifests" ] || { echo "No se encontró $ORIGEN/manifests"; exit 1; }
ORIGEN="$(cd "$ORIGEN" && pwd)"
echo "Copiando modelos desde $ORIGEN ..."
docker compose run --rm --no-deps -v "$ORIGEN:/importar:ro" --entrypoint sh ollama -c \
  "mkdir -p /root/.ollama/models && cp -r --update=none /importar/. /root/.ollama/models/ && echo '[OK] Modelos cargados' && ls /root/.ollama/models/manifests/registry.ollama.ai/library"
