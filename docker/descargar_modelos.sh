#!/usr/bin/env bash
# Descarga los modelos de IA desde internet (alternativa a cargar_modelos.sh).
. "$(dirname "$0")/_entorno.sh" || exit 1
set -e
docker compose up -d ollama
sleep 10
for m in qwen2.5:0.5b embeddinggemma "$MEDGEMMA_MODELO"; do
  echo "Descargando $m ..."; docker compose exec ollama ollama pull "$m"
done
echo "[OK] Modelos descargados."
