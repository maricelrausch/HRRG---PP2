@echo off
REM ============================================================
REM  Construye la ACTUALIZACION liviana (solo la app, sin modelos).
REM  Requiere haber ejecutado construir.bat al menos una vez.
REM  Antes: subir AppVersion en instalador.iss Y en actualizador.iss
REM  Resultado: empaquetado\salida\actualizacion\
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist .venv-build (echo Primero ejecute construir.bat & goto :error)
call .venv-build\Scripts\activate.bat || goto :error
python -m pip install -r ..\backend\requirements.txt -r requirements-build.txt >nul || goto :error

echo [1/3] Empaquetando la app con PyInstaller...
python -m PyInstaller IngenIA.spec --noconfirm --distpath salida\dist --workpath salida\build || goto :error

echo [2/3] Copiando el frontend...
robocopy ..\frontend salida\dist\IngenIA\frontend /E /XD tests /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :error

echo [3/3] Compilando la actualizacion...
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
%ISCC% actualizador.iss || goto :error

echo.
echo LISTO. Actualizacion en: %~dp0salida\actualizacion
pause
exit /b 0

:error
echo.
echo *** ERROR en la construccion. Revise los mensajes de arriba. ***
pause
exit /b 1
