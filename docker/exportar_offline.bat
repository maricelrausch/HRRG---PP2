@echo off
REM Prepara la carpeta docker\ para instalar en una PC SIN acceso a internet:
REM   imagenes\ingenia_imagenes.tar  (app + Ollama + Caddy)
REM   ollama_modelos\                (MedGemma, qwen2.5, embeddinggemma)
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1

echo [1/3] Preparando imagenes...
if "%REGISTRO%"=="1" (
  docker compose pull || goto :error
) else (
  docker compose build app || goto :error
  docker compose pull ollama caddy || goto :error
)

echo [2/3] Exportando imagenes (unos minutos)...
if not exist imagenes mkdir imagenes
docker save -o imagenes\ingenia_imagenes.tar %HRRG_IMAGEN%:%APP_VERSION% ollama/ollama:%OLLAMA_VERSION% caddy:%CADDY_VERSION% || goto :error

echo [3/3] Copiando modelos de IA...
if exist ..\empaquetado\salida\modelos_ollama\manifests (
  robocopy ..\empaquetado\salida\modelos_ollama ollama_modelos /E /NFL /NDL /NJH /NJS >nul
  if errorlevel 8 goto :error
) else (
  echo Falta ..\empaquetado\salida\modelos_ollama: ejecute antes empaquetado\exportar_modelos.ps1
  goto :error
)

echo.
echo LISTO. Copie la carpeta docker\ completa (con imagenes\ y ollama_modelos\) al pendrive.
pause
exit /b 0

:error
echo *** ERROR. Revise los mensajes de arriba. ***
pause
exit /b 1
