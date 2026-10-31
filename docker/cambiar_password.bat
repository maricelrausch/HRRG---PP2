@echo off
REM Cambia la contrasena de un usuario y lo desbloquea (con el sistema iniciado).
cd /d "%~dp0"
docker compose exec app python empaquetado/launcher.py cambiar-password
pause
