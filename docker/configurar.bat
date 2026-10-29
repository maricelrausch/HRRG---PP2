@echo off
REM Configura el acceso desde la red (crea .env). Ejecutar una vez, antes de iniciar.
setlocal
cd /d "%~dp0"
echo.
echo ===== Configuracion de IngenIA Salud - Triage =====
echo.
set IP=
set /p IP=IP fija del servidor (ej. 192.168.1.50): 
if "%IP%"=="" ( echo Debe indicar la IP. & pause & exit /b 1 )
set NOMBRE=
set /p NOMBRE=Nombre de red del servidor (ej. triage.hrrg.local) o Enter para omitir: 
set SITIO=%IP%, localhost
if not "%NOMBRE%"=="" set SITIO=%NOMBRE%, %IP%, localhost

if not exist .env copy .env.example .env >nul
>>.env echo.
>>.env echo # ---- Configurado con configurar.bat ----
>>.env echo HRRG_SITIO="%SITIO%"
>>.env echo HRRG_IP_SERVIDOR=%IP%
echo.
echo [OK] Configuracion guardada en .env
echo      Acceso desde las PCs: https://%IP%
if not "%NOMBRE%"=="" echo                         https://%NOMBRE%
echo.
echo Si el sistema ya estaba iniciado: docker compose up -d --force-recreate caddy
pause
