@echo off
REM Actualiza el sistema a la ultima version y lo reinicia.
REM   - Con imagen en un registro (HRRG_IMAGEN=ghcr.io/...): descarga la version publicada.
REM   - Sin registro (PC del equipo): reconstruye con el codigo actual del repo.
REM Usuarios, datos, claves y modelos se conservan.
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
if "%REGISTRO%"=="1" (
  echo Descargando la ultima version publicada...
  docker compose pull || goto :error
  docker compose up -d --no-build || goto :error
) else if not exist ..\backend\app.py (
  echo Esta instalacion no tiene el codigo fuente. Para actualizar use aplicar_actualizacion.bat
  pause
  exit /b 1
) else (
  echo Reconstruyendo con el codigo actual...
  docker compose build app || goto :error
  docker compose pull ollama caddy || goto :error
  docker compose up -d || goto :error
)
echo.
echo LISTO. Sistema actualizado.
pause
exit /b 0
:error
echo *** ERROR. Revise los mensajes de arriba. ***
pause
exit /b 1
