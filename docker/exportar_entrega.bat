@echo off
REM PC del equipo: genera el KIT DE INSTALACION para el hospital (no necesita el codigo fuente).
REM Resultado: entrega\IngenIA_Salud_Triage_Docker_<version>\
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
set KIT=entrega\IngenIA_Salud_Triage_Docker_%APP_VERSION%
if exist "%KIT%" ( echo Ya existe %KIT%. Borrela o suba APP_VERSION en .env. & pause & exit /b 1 )

echo [1/4] Preparando imagenes...
if "%REGISTRO%"=="1" (
  docker compose pull || goto :error
) else (
  docker compose build app || goto :error
  docker compose pull ollama caddy || goto :error
)

echo [2/4] Copiando archivos del kit...
mkdir "%KIT%\imagenes" "%KIT%\certificados" "%KIT%\documentacion"
for %%f in (docker-compose.yml Caddyfile .env.example .gitattributes LEEME.md _entorno.bat _entorno.sh) do copy "%%f" "%KIT%\" >nul
for %%f in (configurar iniciar detener actualizar aplicar_actualizacion crear_admin cambiar_password cargar_modelos descargar_modelos exportar_certificado) do (
  copy "%%f.bat" "%KIT%\" >nul
  copy "%%f.sh" "%KIT%\" >nul
)
copy certificados\LEEME.txt "%KIT%\certificados\" >nul
if exist documentacion\*.pdf copy documentacion\*.pdf "%KIT%\documentacion\" >nul

echo [3/4] Exportando imagenes (app + Ollama + Caddy), unos minutos...
docker save -o "%KIT%\imagenes\ingenia_imagenes.tar" %HRRG_IMAGEN%:%APP_VERSION% ollama/ollama:%OLLAMA_VERSION% caddy:%CADDY_VERSION% || goto :error

echo [4/4] Copiando modelos de IA (unos 4 GB)...
if not exist ..\empaquetado\salida\modelos_ollama\manifests (
  echo Falta ..\empaquetado\salida\modelos_ollama: ejecute antes empaquetado\exportar_modelos.ps1
  goto :error
)
robocopy ..\empaquetado\salida\modelos_ollama "%KIT%\ollama_modelos" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :error

echo.
echo ============================================================
echo  LISTO. Kit de instalacion en:
echo    %~dp0%KIT%
echo  Agregar el manual en PDF en la subcarpeta documentacion\
echo  (o dejarlo en docker\documentacion\ antes de exportar).
echo ============================================================
pause
exit /b 0

:error
echo *** ERROR. Revise los mensajes de arriba. ***
pause
exit /b 1
