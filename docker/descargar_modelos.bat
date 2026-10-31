@echo off
REM Descarga los modelos de IA desde internet (alternativa a cargar_modelos.bat).
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
docker compose up -d ollama || goto :error
echo Esperando a Ollama...
timeout /t 10 /nobreak >nul
for %%m in (qwen2.5:0.5b embeddinggemma %MEDGEMMA_MODELO%) do (
  echo Descargando %%m ...
  docker compose exec ollama ollama pull %%m || goto :error
)
echo.
echo [OK] Modelos descargados.
pause
exit /b 0
:error
echo *** No se pudo descargar. Si el servidor no tiene acceso a ollama.com, use cargar_modelos.bat ***
pause
exit /b 1
