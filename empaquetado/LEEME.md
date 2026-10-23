# Empaquetado offline – IngenIA Salud – Triage

Genera un instalador de Windows que **no necesita internet**. Incluye la app (Flask), Ollama, MedGemma, qwen2.5, embeddinggemma y Whisper.
La PC donde se instala **no necesita Python ni Ollama**: los pone el instalador.

---

## A. Construir el instalador (equipo de desarrollo)

**Requisitos en la PC que construye:**

- Windows 10/11 de 64 bits
- Python 3.11
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (`winget install -e --id JRSoftware.InnoSetup`)
- Ollama, con los modelos ya descargados (verificar con `ollama list`):
  ```
  ollama pull medgemma:4b
  ollama pull qwen2.5:0.5b
  ollama pull embeddinggemma
  ```

**Pasos:**
```powershell
cd <repo>\empaquetado
.\construir.bat
```
La primera vez usa internet (dependencias, Whisper y OllamaSetup) y tarda entre 30 y 40 minutos, casi todo en la compresión. Las siguientes veces no vuelve a descargar nada.

**Resultado:** `empaquetado\salida\instalador\` (unos **6,1 GB**):
```
Instalador_IngenIA_Salud_Triage_0.1.0.exe
Instalador_IngenIA_Salud_Triage_0.1.0-1.bin
Instalador_IngenIA_Salud_Triage_0.1.0-2.bin
Instalador_IngenIA_Salud_Triage_0.1.0-3.bin
Instalador_IngenIA_Salud_Triage_0.1.0-4.bin
```

**Prueba sin instalar** (cerrar antes el Flask de desarrollo):
```powershell
.\salida\dist\IngenIA\IngenIA.exe
```

**Recompilar solo la app** (unos 5 minutos, para probar cambios):
```powershell
.\.venv-build\Scripts\activate
python -m PyInstaller IngenIA.spec --noconfirm --distpath salida\dist --workpath salida\build
robocopy ..\frontend salida\dist\IngenIA\frontend /E /XD tests /NFL /NDL /NJH /NJS
```

### Qué hace cada archivo

| Archivo | Función |
|---|---|
| `launcher.py` | Punto de entrada del .exe: inicia Ollama, prepara las claves, crea el primer administrador y levanta Flask con waitress |
| `IngenIA.spec` | Configuración de PyInstaller |
| `instalador.iss` / `construir.bat` | Instalador completo |
| `actualizador.iss` / `construir_actualizacion.bat` | Actualización liviana |
| `exportar_modelos.ps1` | Copia los modelos de Ollama de esta PC al paquete |
| `descargar_whisper.py` | Descarga Whisper `small` al paquete |
| `crear_icono.py` | Genera el `.ico` a partir del logo |
| `salida\` | Todo lo generado (unos 11 GB). **No se sube a git** |

### Configuración que fija el lanzador

| Variable | Valor | Para qué |
|---|---|---|
| `HRRG_MODO_EXTRACCION` | `ia` | Extracción real con MedGemma (no los casos simulados D01–D05) |
| `HRRG_HOST` | `127.0.0.1` | Solo accesible desde esta PC (`0.0.0.0` habilita la red) |
| `HRRG_PUERTO` | `5000` | Puerto de la app |
| `WHISPER_MODELO` | `modelos\whisper-small` | Whisper local, sin descargar |
| `HF_HUB_OFFLINE`, `ANONYMIZED_TELEMETRY` | `1`, `False` | Nada sale a internet |

Cualquiera se puede cambiar con una variable de entorno del usuario de Windows.

> ⚠️ Si se cambian rutas, puerto o el arranque de `backend/app.py`, revisar `launcher.py`.

---

## A2. Actualización liviana (versiones nuevas)

Sirve para entregar cambios en la app sin volver a distribuir 6 GB.

1. Subir `AppVersion` en `instalador.iss` **y** en `actualizador.iss` (por ejemplo, 0.2.0).
2. Ejecutar `construir_actualizacion.bat`.
3. Entregar `salida\actualizacion\Actualizacion_IngenIA_Salud_Triage_<versión>.exe` (unos 300 MB).

- Solo funciona en PCs donde ya se instaló el instalador completo.
- Conserva los usuarios, los datos, las claves y los modelos.
- Si cambian los modelos de IA, usar el instalador completo.

---

## A3. Cómo compartir el instalador

El instalador **no está en GitHub** (pesa 6 GB). Se comparte por:

| Medio | Indicaciones |
|---|---|
| **Google Drive** | Subir los **5 archivos en la misma carpeta**. Si al descargar llegan en `.zip`, descomprimir primero |
| **Pendrive / disco externo** | Formato **exFAT o NTFS** (FAT32 no admite archivos de más de 4 GB) |
| **GitHub Releases** | Opcional: cada `.bin` mide menos de 2 GB, así que entra en el límite por archivo |

> Los 5 archivos tienen que estar **siempre juntos**. Sin los `.bin`, el `.exe` no instala.

---

## A4. Cuando se modifica el proyecto

| Cambio | ¿Se incluye solo? | Qué hacer |
|---|---|---|
| Editar o agregar `.py` en `backend/src/` o `backend/ia/` (también subcarpetas) | ✅ Sí | Recompilar |
| Editar o agregar archivos en `frontend/` | ✅ Sí | Recompilar |
| Editar o agregar archivos en `backend/datos/` o `backend/src/base_conocimiento/` | ✅ Sí | Recompilar |
| Cambiar `backend/app.py` | ✅ Sí | Recompilar. Si cambia el puerto, las rutas o el arranque, revisar `launcher.py` |
| Carpeta nueva de código en `backend/` (fuera de `src/` e `ia/`) | ❌ No | Agregar `+ modulos_locales("carpeta")` en `IngenIA.spec` |
| Archivos de datos nuevos fuera de `datos/` o `base_conocimiento/` | ❌ No | Agregarlos en `datas` de `IngenIA.spec` |
| Librería nueva de Python | ⚠️ A medias | Agregarla a `backend/requirements.txt`. Si da error de "No module named..." en el `.exe`, sumarla a la lista de `collect_all` de `IngenIA.spec` |
| Módulo que usa `torch` o `transformers` | ❌ Excluido | Por tamaño, están afuera. Hay que sacarlos de `excludes` y de `EXCLUIR_SRC` en `IngenIA.spec` |
| Modelo nuevo de Ollama | ❌ No | Agregarlo en `exportar_modelos.ps1` y en `MODELOS_OLLAMA` de `launcher.py`. Requiere el **instalador completo** |
| Variable de configuración nueva | ❌ No | Fijar el valor por defecto en `configurar_entorno()` de `launcher.py` |

**Flujo de trabajo para cada cambio:**
1. Desarrollar y probar como siempre (`python app.py`).
2. Recompilar solo la app y probar `salida\dist\IngenIA\IngenIA.exe`.
3. Subir `AppVersion` en los dos `.iss`.
4. Si solo cambió la app: `construir_actualizacion.bat` (unos 300 MB). Si cambiaron los modelos: `construir.bat` (6 GB).

---

## B. Manual de instalación (usuario final)

### Requisitos

- Windows 10/11 de 64 bits
- 8 GB de RAM (se recomiendan 16 GB)
- 12 GB libres en disco
- **No hace falta internet**

### Instalación

1. Copiar la carpeta del instalador completa (los 5 archivos) a la PC.
2. Doble clic en `Instalador_IngenIA_Salud_Triage_0.1.0.exe`.
   - Si aparece "Windows protegió su PC": hacer clic en **Más información → Ejecutar de todas formas**.
3. Seguir el asistente (**Siguiente → Instalar**). No pide permisos de administrador. Tarda unos minutos.
4. Al terminar se abre **IngenIA Salud – Triage**. La primera vez pide crear la **cuenta de administrador** en la ventana negra (contraseña de 12 caracteres como mínimo).
5. El navegador se abre solo en `http://localhost:5000`.

### Uso diario

- Abrir el acceso directo **IngenIA Salud – Triage** (escritorio o menú Inicio).
- La ventana negra **tiene que quedar abierta** mientras se usa el sistema. Cerrarla apaga el sistema.
- Si se abre otra vez el acceso directo con el sistema ya abierto, solo abre el navegador.
- La primera consulta del día puede tardar entre 1 y 2 minutos mientras se cargan los modelos.

### Otros accesos (menú Inicio)

- *IngenIA Salud – Triage – Crear usuario*
- *IngenIA Salud – Triage – Cambiar contraseña*

### Dónde queda instalado

| Qué | Ubicación |
|---|---|
| Programa + Whisper | `%LOCALAPPDATA%\Programs\IngenIA Salud Triage` |
| Ollama | `%LOCALAPPDATA%\Programs\Ollama` |
| Modelos de IA | `%USERPROFILE%\.ollama\models` |
| Datos (usuarios, episodios, registros) | `%USERPROFILE%\.hrrg_pp2` |
| Claves de cifrado | `%USERPROFILE%\.hrrg_pp2_claves` |

- Los datos y las claves **no se borran al desinstalar**.
- **Respaldar siempre las dos carpetas juntas**: sin las claves no se pueden leer los datos identificatorios.

### Acceso desde otras PCs de la red (opcional)

Crear la variable de entorno de usuario `HRRG_HOST=0.0.0.0` y volver a abrir el sistema. Windows va a pedir permiso en el firewall. Desde la otra PC se entra con `http://<IP-de-esta-PC>:5000`.

---

## C. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| "Windows protegió su PC" | El instalador no tiene firma digital. **Más información → Ejecutar de todas formas** |
| El antivirus bloquea `IngenIA.exe` | Falso positivo habitual de PyInstaller. Agregar una excepción para la carpeta del programa |
| `[AVISO] No se encontró Ollama` | Ollama no quedó instalado. Volver a ejecutar el instalador completo |
| `[AVISO] Faltan modelos en Ollama` | No se copiaron los modelos. Volver a ejecutar el instalador completo |
| La IA o el dictado tardan mucho la primera vez | Normal: se están cargando los modelos. Las siguientes consultas son más rápidas |
| El navegador no abre | Entrar a mano a `http://localhost:5000` |
| Error de puerto ocupado | Hay otra app usando el 5000. Cerrarla, o crear `HRRG_PUERTO=5001` |
| "Usá el relato exacto de un único caso de demostración" | La app está en modo simulado. Verificar que no exista la variable `HRRG_MODO_EXTRACCION=simulado` |
| Entra sin pedir contraseña | Quedó una sesión abierta en el navegador (dura 30 minutos). Cerrar sesión o usar una ventana de incógnito |
| La ventana negra se cierra sola con un error | Abrir PowerShell en la carpeta del programa, ejecutar `.\IngenIA.exe` y enviar el mensaje al equipo |
