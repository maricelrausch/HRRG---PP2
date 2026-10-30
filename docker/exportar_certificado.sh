#!/usr/bin/env bash
# Extrae el certificado raíz de Caddy (HRRG_TLS=internal) para instalarlo en las PCs de la red.
. "$(dirname "$0")/_entorno.sh" || exit 1
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt certificado_ingenia.crt \
  && echo "[OK] Certificado guardado en $(pwd)/certificado_ingenia.crt"
