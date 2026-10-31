@echo off
REM Copia los modelos de Ollama (MedGemma, qwen2.5, embeddinggemma) al volumen de Docker.
REM Uso: cargar_modelos.bat [carpeta]   (por defecto: ollama_modelos\ o ..\empaquetado\salida\modelos_ollama\)
setlocal
cd /d "%~dp0"
set ORIGEN=%~1
if "%ORIGEN%"=="" if exist ollama_modelos\manifests set ORIGEN=ollama_modelos
if "%ORIGEN%"=="" if exist ..\empaquetado\salida\modelos_ollama\manifests set ORIGEN=..\empaquetado\salida\modelos_ollama
if "%ORIGEN%"=="" (
  echo No se encontro la carpeta de modelos. Indiquela: cargar_modelos.bat C:\ruta\modelos_ollama
  pause
  exit /b 1
)
pushd "%ORIGEN%" || exit /b 1
set ORIGEN=%CD%
popd

echo Copiando modelos desde %ORIGEN% (puede tardar varios minutos)...
docker compose run --rm --no-deps -v "%ORIGEN%:/importar:ro" --entrypoint sh ollama -c "mkdir -p /root/.ollama/models && cp -r --update=none /importar/. /root/.ollama/models/ && echo [OK] Modelos cargados && ls /root/.ollama/models/manifests/registry.ollama.ai/library" || goto :error
pause
exit /b 0

:error
echo *** No se pudieron cargar los modelos. ***
pause
exit /b 1
