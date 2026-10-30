@echo off
REM Detiene IngenIA Salud - Triage. Los datos, claves y modelos se conservan.
cd /d "%~dp0"
docker compose down
echo Sistema detenido.
timeout /t 5 >nul
