@echo off
REM PC del hospital: aplica la actualizacion (imagenes\ingenia_app.tar) sin internet.
REM Usuarios, datos, claves y modelos se conservan.
setlocal
cd /d "%~dp0"
if not exist imagenes\ingenia_app.tar (
  echo No se encontro imagenes\ingenia_app.tar
  pause
  exit /b 1
)
echo Cargando la nueva version...
docker load -i imagenes\ingenia_app.tar || goto :error
docker compose up -d --no-build || goto :error
echo.
echo LISTO. Sistema actualizado. Abra http://localhost:5000
pause
exit /b 0
:error
echo *** ERROR. Revise los mensajes de arriba. ***
pause
exit /b 1
