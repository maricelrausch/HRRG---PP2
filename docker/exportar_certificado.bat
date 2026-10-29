@echo off
REM Extrae el certificado raiz de Caddy (solo si HRRG_TLS=internal) para instalarlo
REM en las PCs de la red y que el navegador no muestre "conexion no segura".
setlocal
cd /d "%~dp0"
call _entorno.bat || exit /b 1
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt certificado_ingenia.crt || goto :error
echo.
echo [OK] Certificado guardado en: %~dp0certificado_ingenia.crt
echo Instalarlo en cada PC: doble clic ^> Instalar certificado ^> Equipo local ^>
echo "Colocar todos los certificados en el siguiente almacen" ^> Entidades de certificacion raiz de confianza.
pause
exit /b 0
:error
echo *** No se pudo exportar. Inicie el sistema primero (iniciar.bat). ***
pause
exit /b 1
