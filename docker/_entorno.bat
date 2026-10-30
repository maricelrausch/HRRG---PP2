@echo off
REM Carga la configuracion de .env y los valores por defecto. Lo usan los demas scripts.
if exist "%~dp0.env" for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0.env") do set "%%a=%%~b"
if not defined APP_VERSION set APP_VERSION=0.1.0
if not defined OLLAMA_VERSION set OLLAMA_VERSION=latest
if not defined CADDY_VERSION set CADDY_VERSION=2
if not defined HRRG_IMAGEN set HRRG_IMAGEN=ingenia-salud-triage
if not defined HRRG_SITIO set HRRG_SITIO=localhost
if not defined MEDGEMMA_MODELO set MEDGEMMA_MODELO=medgemma:4b
set REGISTRO=0
echo %HRRG_IMAGEN% | find "/" >nul && set REGISTRO=1
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo Docker no esta funcionando.
  echo Abra Docker Desktop, espere a que indique "Engine running" y vuelva a intentar.
  pause
  exit /b 1
)
exit /b 0
