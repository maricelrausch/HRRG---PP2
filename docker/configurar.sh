#!/usr/bin/env bash
# Configura el acceso desde la red (crea .env). Ejecutar una vez, antes de iniciar.
cd "$(dirname "$0")" || exit 1
echo "===== Configuración de IngenIA Salud – Triage ====="
read -rp "IP fija del servidor (ej. 192.168.1.50): " IP
[ -n "$IP" ] || { echo "Debe indicar la IP."; exit 1; }
read -rp "Nombre de red del servidor (ej. triage.hrrg.local) o Enter para omitir: " NOMBRE
SITIO="$IP, localhost"; [ -n "$NOMBRE" ] && SITIO="$NOMBRE, $IP, localhost"
[ -f .env ] || cp .env.example .env
printf '\n# ---- Configurado con configurar.sh ----\nHRRG_SITIO="%s"\nHRRG_IP_SERVIDOR=%s\n' "$SITIO" "$IP" >> .env
echo "[OK] Configuración guardada en .env"
echo "     Acceso desde las PCs: https://$IP ${NOMBRE:+ / https://$NOMBRE}"
echo "Si el sistema ya estaba iniciado: docker compose up -d --force-recreate caddy"
