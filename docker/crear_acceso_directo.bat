@echo off
REM Crea en el Escritorio el acceso directo "IngenIA Salud - Triage" con el logo del hospital.
REM Se ejecuta en cada PC de la guardia. Necesita este archivo y icono_ingenia.ico en la misma carpeta.
setlocal
cd /d "%~dp0"
set DIR=
if exist .env for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="HRRG_IP_SERVIDOR" set "DIR=%%~b"
echo.
echo ===== Acceso directo de IngenIA Salud - Triage =====
echo.
if not "%DIR%"=="" if /i not "%DIR%"=="localhost" echo Direccion detectada: %DIR%
set /p ENTRADA=IP o nombre del servidor (Enter para usar la detectada): 
if not "%ENTRADA%"=="" set "DIR=%ENTRADA%"
if "%DIR%"=="" ( echo Debe indicar la IP o el nombre del servidor. & pause & exit /b 1 )
if not exist icono_ingenia.ico ( echo Falta icono_ingenia.ico en esta carpeta. & pause & exit /b 1 )

set "DESTINO_ICONO=%LOCALAPPDATA%\IngenIA"
if not exist "%DESTINO_ICONO%" mkdir "%DESTINO_ICONO%"
copy /y icono_ingenia.ico "%DESTINO_ICONO%\icono_ingenia.ico" >nul

powershell -NoProfile -Command "$e=[Environment]::GetFolderPath('Desktop'); $f=Join-Path $e 'IngenIA Salud - Triage.url'; Set-Content -Path $f -Encoding ASCII -Value @('[InternetShortcut]','URL=https://%DIR%/','IconFile=%DESTINO_ICONO%\icono_ingenia.ico','IconIndex=0'); Write-Host ('[OK] Acceso directo creado en: ' + $f)" || goto :error
echo      Abre: https://%DIR%/
pause
exit /b 0
:error
echo *** No se pudo crear el acceso directo. ***
pause
exit /b 1
