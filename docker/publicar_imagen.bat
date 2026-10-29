@echo off
REM PC del equipo: construye la imagen y la publica en el registro (GitHub Packages).
REM Requisitos:
REM   1. En .env:  HRRG_IMAGEN=ghcr.io/<usuario-o-equipo>/ingenia-salud-triage
REM   2. Una vez:  docker login ghcr.io -u <usuario-github>
REM      (contrasena = token de GitHub con permiso write:packages)
REM   3. Subir APP_VERSION en .env para cada version nueva.
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
if not "%REGISTRO%"=="1" (
  echo Configure HRRG_IMAGEN=ghcr.io/^<usuario^>/ingenia-salud-triage en .env
  pause
  exit /b 1
)
echo [1/2] Construyendo %HRRG_IMAGEN%:%APP_VERSION% ...
docker compose build app || goto :error
echo [2/2] Publicando...
docker compose push app || goto :error
echo.
echo LISTO. En el servidor: actualizar.bat  (o ./actualizar.sh)
pause
exit /b 0
:error
echo *** ERROR. Si dice "denied" o "unauthorized", ejecute: docker login ghcr.io ***
pause
exit /b 1
