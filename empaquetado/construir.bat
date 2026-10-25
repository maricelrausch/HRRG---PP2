@echo off
REM ============================================================
REM  Construye el instalador offline de IngenIA Salud.
REM  Requisitos en esta PC: Python 3.11, Inno Setup 6, Ollama con
REM  los modelos ya descargados (medgemma:4b, qwen2.5:0.5b, embeddinggemma)
REM  Resultado: empaquetado\salida\instalador\
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/7] Entorno virtual de construccion...
if not exist .venv-build (py -3.11 -m venv .venv-build || python -m venv .venv-build) || goto :error
call .venv-build\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip >nul
python -m pip install -r ..\backend\requirements.txt -r requirements-build.txt || goto :error

echo.
echo [2/7] Icono...
python crear_icono.py || goto :error

echo.
echo [3/7] Empaquetando la app con PyInstaller...
python -m PyInstaller IngenIA.spec --noconfirm --clean --distpath salida\dist --workpath salida\build || goto :error

echo.
echo [4/7] Copiando el frontend...
robocopy ..\frontend salida\dist\IngenIA\frontend /E /XD tests /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :error

echo.
echo [5/7] Modelo de voz (Whisper)...
if not exist salida\modelos\whisper-small\model.bin (python descargar_whisper.py || goto :error) else echo Ya descargado.

echo.
echo [6/7] Ollama y modelos de IA...
if not exist salida\OllamaSetup.exe (curl -L -o salida\OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe || goto :error) else echo OllamaSetup.exe ya descargado.
powershell -NoProfile -ExecutionPolicy Bypass -File exportar_modelos.ps1 || goto :error

echo.
echo [7/7] Compilando el instalador con Inno Setup...
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
%ISCC% instalador.iss || goto :error

echo.
echo ============================================================
echo  LISTO. Instalador en: %~dp0salida\instalador
echo  Distribuir TODOS los archivos de esa carpeta juntos.
echo ============================================================
pause
exit /b 0

:error
echo.
echo *** ERROR en la construccion. Revise los mensajes de arriba. ***
pause
exit /b 1
