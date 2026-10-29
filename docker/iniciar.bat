@echo off
REM Inicia IngenIA Salud - Triage (Ollama + app + Caddy) y abre el navegador.
setlocal
cd /d "%~dp0"
title IngenIA Salud - Triage
call _entorno.bat || exit /b 1

docker image inspect %HRRG_IMAGEN%:%APP_VERSION% >nul 2>&1
if not errorlevel 1 goto :arrancar
if exist imagenes\ingenia_imagenes.tar (
  echo Cargando las imagenes de Docker por primera vez, espere...
  docker load -i imagenes\ingenia_imagenes.tar || goto :error
) else if "%REGISTRO%"=="1" (
  echo Descargando la imagen del sistema, espere...
  docker compose pull app || goto :error
) else if exist ..\backend\app.py (
  echo Construyendo la imagen con el codigo del repo, espere...
  docker compose build app || goto :error
) else (
  echo No se encontro la imagen del sistema ^(imagenes\ingenia_imagenes.tar^).
  goto :error
)

:arrancar
echo Iniciando IngenIA Salud - Triage...
docker compose up -d --no-build || goto :error

echo Esperando a que el sistema este listo (la primera vez puede tardar 1-3 minutos)...
set /a N=0
:esperar
set ESTADO=
for /f "delims=" %%s in ('docker inspect -f "{{.State.Health.Status}}" ingenia-app 2^>nul') do set ESTADO=%%s
if "%ESTADO%"=="healthy" goto :listo
set /a N+=1
if %N% geq 72 goto :lento
timeout /t 5 /nobreak >nul
goto :esperar

:listo
echo.
echo [OK] Sistema disponible
echo      En esta PC:           http://localhost:5000
echo      Desde otras PCs:      https://^<nombre o IP del servidor^>   (%HRRG_SITIO%)
echo      Si es la primera vez, cree el administrador con crear_admin.bat
start "" http://localhost:5000
timeout /t 8 >nul
exit /b 0

:lento
echo.
echo El sistema tarda mas de lo normal. Revise los mensajes con:
echo    docker compose logs app
pause
exit /b 1

:error
echo.
echo *** No se pudo iniciar. Revise los mensajes de arriba. ***
pause
exit /b 1
