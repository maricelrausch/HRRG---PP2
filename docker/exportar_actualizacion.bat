@echo off
REM PC del equipo: genera SOLO la imagen de la app para actualizar una PC sin internet.
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
docker compose build app || goto :error
if not exist imagenes mkdir imagenes
echo Exportando la imagen de la app...
docker save -o imagenes\ingenia_app.tar %HRRG_IMAGEN%:%APP_VERSION% || goto :error
echo.
echo LISTO. Lleve a la otra PC:  imagenes\ingenia_app.tar  y ejecute aplicar_actualizacion
pause
exit /b 0
:error
echo *** ERROR. Revise los mensajes de arriba. ***
pause
exit /b 1
