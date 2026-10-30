@echo off
REM Crea un usuario administrador (con el sistema iniciado).
cd /d "%~dp0"
docker compose exec app python empaquetado/launcher.py crear-admin
pause
