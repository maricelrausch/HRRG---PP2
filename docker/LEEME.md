# IngenIA Salud – Triage con Docker

Tres contenedores en un servidor (Windows o Linux). Las PCs de la guardia entran por **HTTPS** desde el navegador:

```
 PCs de la guardia (navegador)
          │  https://triage.hrrg.local   (o la IP del servidor)
          ▼
 ┌──────────────────────── Servidor (Docker) ────────────────────────┐
 │  ┌──────────────┐    ┌──────────────────────────┐   ┌───────────┐ │
 │  │ ingenia-caddy│───►│ ingenia-app              │──►│ ingenia-  │ │
 │  │ HTTPS :443   │    │ Flask + Whisper + RAG    │   │ ollama    │ │
 │  └──────┬───────┘    └─────┬──────────────┬─────┘   └─────┬─────┘ │
 │   vol. caddy_data     vol. datos    vol. claves     vol. ollama   │
 └───────────────────────────────────────────────────────────────────┘
```

**¿Por qué HTTPS?** Los navegadores solo permiten usar el **micrófono** (dictado por voz) en `localhost` o en sitios `https://`. Sin Caddy, el dictado no funciona desde otras PCs.

---

## 1. Archivos

| Windows | Linux | Para qué |
|---|---|---|
| `iniciar.bat` | `iniciar.sh` | Levanta los 3 contenedores |
| `detener.bat` | `detener.sh` | Los apaga (los datos se conservan) |
| `actualizar.bat` | `actualizar.sh` | Pasa a la última versión (descarga del registro o reconstruye) |
| `crear_admin.bat` | `crear_admin.sh` | Crea un usuario administrador |
| `cambiar_password.bat` | `cambiar_password.sh` | Cambia la contraseña y desbloquea una cuenta |
| `descargar_modelos.bat` | `descargar_modelos.sh` | Descarga los modelos de IA desde internet |
| `cargar_modelos.bat` | `cargar_modelos.sh` | Carga los modelos desde una carpeta (sin internet) |
| `exportar_certificado.bat` | `exportar_certificado.sh` | Extrae el certificado de Caddy para instalarlo en las PCs |
| `crear_acceso_directo.bat` + `icono_ingenia.ico` | — | **En cada PC:** crea el acceso directo con el logo del HRRG |
| `aplicar_actualizacion.bat` | `aplicar_actualizacion.sh` | Aplica una actualización traída en pendrive |
| `publicar_imagen.bat` | — | **Equipo:** publica la imagen en el registro |
| `exportar_offline.bat` | — | **Equipo:** prepara la instalación completa en pendrive |
| `exportar_actualizacion.bat` | — | **Equipo:** prepara una actualización en pendrive |

| Configuración | Para qué |
|---|---|
| `docker-compose.yml` | Los 3 servicios, volúmenes y puertos |
| `Dockerfile` + `Dockerfile.dockerignore` | Imagen de la app |
| `Caddyfile` | Proxy HTTPS hacia la app |
| `.env.example` → copiar como `.env` | Nombre/IP del servidor, certificado, imagen, versiones |
| `certificados/` | Certificado del hospital (opcional) |
| `_entorno.bat` / `_entorno.sh` | Uso interno: cargan `.env` |

---

## 2. Escenarios de instalación

| Escenario | Cómo llega el sistema | Modelos de IA |
|---|---|---|
| **A. Servidor con internet, desde el repositorio** (recomendado) | `git clone` del repo; `iniciar` construye la imagen en el servidor | `descargar_modelos` |
| **A2. Servidor con internet, desde un registro** | `iniciar` descarga la imagen publicada con `publicar_imagen.bat` | `descargar_modelos` |
| **B. Servidor sin acceso a los sitios** | Pendrive (`exportar_offline.bat`) | `cargar_modelos` |
| **C. PC del equipo (desarrollo)** | `docker compose build` con el código del repo | `cargar_modelos` (desde `empaquetado`) |

### A. Servidor con internet, desde el repositorio (recomendado)

```bash
git clone https://github.com/maricelrausch/HRRG---PP2.git /opt/ingenia     # Windows: C:\IngenIA
cd /opt/ingenia/docker
./configurar.sh            # IP y nombre del servidor
./descargar_modelos.sh     # MedGemma (medgemma:4b de ollama.com), qwen2.5, embeddinggemma
./iniciar.sh               # la primera vez construye la imagen (10-20 min)
./crear_admin.sh
```
**Actualizar:** `git pull && ./actualizar.sh`. No hace falta pendrive ni registro.

### A2. Servidor con internet, desde un registro de imágenes

**En la PC del equipo, una vez por versión:**
1. En `.env`: `HRRG_IMAGEN=ghcr.io/<usuario-o-equipo>/ingenia-salud-triage` y la `APP_VERSION`.
2. Una sola vez: `docker login ghcr.io -u <usuario-github>` (contraseña = token de GitHub con permiso `write:packages`).
3. `publicar_imagen.bat`.

> El paquete de GitHub queda **privado** por defecto. El servidor debe hacer `docker login ghcr.io` con un token de solo lectura (`read:packages`), o el equipo lo publica como público.

**En el servidor, la primera vez:**
1. Instalar Docker (Linux: Docker Engine | Windows: Docker Desktop).
2. Copiar la carpeta `docker/` (sin `imagenes/` ni `ollama_modelos/`).
3. Copiar `.env.example` como `.env` y completar `HRRG_IMAGEN`, `APP_VERSION` y `HRRG_SITIO`.
4. `iniciar` → descarga la imagen y levanta todo.
5. `descargar_modelos` → MedGemma, qwen2.5 y embeddinggemma.
6. `crear_admin`.
7. HTTPS en las PCs (sección 3).

**Para actualizar:** el equipo ejecuta `publicar_imagen.bat` (con `APP_VERSION` nueva) → en el servidor se cambia `APP_VERSION` en `.env` y se ejecuta `actualizar`.

### B. Servidor sin acceso (pendrive)

**PC del equipo:** `exportar_offline.bat` → copiar la carpeta `docker/` completa.
**Servidor:** `.env` → `cargar_modelos` → `iniciar` → `crear_admin`.
**Actualizar:** `exportar_actualizacion.bat` → en el servidor, `aplicar_actualizacion`.

### C. PC del equipo

```powershell
docker compose build
docker compose up -d ollama
.\cargar_modelos.bat
.\iniciar.bat
.\crear_admin.bat
```
Después de `git pull`: `actualizar.bat` (reconstruye con el código nuevo).

---

## 3. HTTPS y acceso desde la red

En `.env`, `HRRG_SITIO` lista los nombres y/o IP con los que se entra al servidor:
```
HRRG_SITIO="triage.hrrg.local, 192.168.1.50, localhost"
HRRG_IP_SERVIDOR=192.168.1.50
```

> **`HRRG_IP_SERVIDOR` es obligatoria para entrar por IP.** Al entrar por IP, el navegador no envía el nombre del sitio (SNI) y, sin este dato, Caddy corta la conexión con `ERR_SSL_PROTOCOL_ERROR`. Después de cambiar `.env`: `docker compose up -d --force-recreate caddy`.

| Opción | `.env` | Resultado en las PCs |
|---|---|---|
| **Certificado del hospital** (ideal) | `HRRG_TLS="/certs/cert.pem /certs/key.pem"` + archivos en `certificados/` | Sin avisos |
| **Certificado interno de Caddy** | `HRRG_TLS=internal` | "Conexión no segura" hasta instalar el certificado raíz en cada PC |

**Instalar el certificado interno en las PCs** (opción 2):
1. En el servidor: `exportar_certificado` → genera `certificado_ingenia.crt`.
2. En cada PC (o por directiva de grupo): doble clic → **Instalar certificado** → **Equipo local** → **Colocar todos los certificados en el siguiente almacén** → **Entidades de certificación raíz de confianza**.

> El certificado raíz de Caddy se guarda en el volumen `caddy_data`. Si se borra ese volumen, hay que reinstalarlo en las PCs.
>
> **Celulares** (vista del personal): también necesitan el certificado instalado, o el certificado del hospital.

**Firewall del servidor:** abrir los puertos **443** y **80** (TCP) para la red interna.

---

## 4. Cuando cambia el código

El `Dockerfile` copia `backend/` y `frontend/` completos: **los archivos nuevos o modificados entran solos**. Si cambia `requirements.txt`, las librerías se reinstalan solas.

Solo hay que tocar Docker si cambia **cómo arranca** la app (puerto, rutas de `app.py`) o si se agrega un **modelo nuevo** de Ollama.

---

## 5. Datos y respaldo

| Volumen | Contenido |
|---|---|
| `ingenia_datos` | Usuarios, episodios, registros |
| `ingenia_claves` | Claves de cifrado — **respaldar junto con datos** |
| `ingenia_ollama` | Modelos de IA |
| `ingenia_caddy_data` | Certificados de Caddy (incluye la CA interna) |

- `detener` y `docker compose down` **no borran** los volúmenes. **Nunca** usar `docker compose down -v`.
- Docker usa **su propia base de datos**, separada de la del `.exe` o del desarrollo.

Respaldo (Linux; en Windows reemplazar `$(pwd)` por `${PWD}` en PowerShell):
```bash
docker run --rm -v ingenia_datos:/d -v ingenia_claves:/c -v "$(pwd):/r" alpine tar czf /r/respaldo_ingenia.tgz /d /c
```

Importar datos locales (`%USERPROFILE%\.hrrg_pp2` + claves) a Docker — **reemplaza** lo que haya:
```powershell
docker compose stop app
docker run --rm -v ingenia_datos:/datos -v ingenia_claves:/claves -v "$env:USERPROFILE\.hrrg_pp2:/o_datos:ro" -v "$env:USERPROFILE\.hrrg_pp2_claves:/o_claves:ro" alpine sh -c "cp -a /o_datos/. /datos/ && cp -a /o_claves/. /claves/ && chown -R 1000:1000 /datos /claves"
docker compose start app
```

---

## 6. Preguntas para Informática del hospital

1. ¿Sistema operativo del servidor? (Windows / Linux)
2. ¿Puede acceder a `ghcr.io`, `registry-1.docker.io` y `ollama.com`?
3. ¿Nombre de red (DNS) e IP fija del servidor?
4. ¿Pueden emitir un certificado para ese nombre, o instalar un certificado raíz en las PCs?
5. ¿RAM y GPU del servidor? (MedGemma con varias consultas simultáneas)
6. ¿Pueden abrir los puertos 443/80 hacia la red interna?

---

## 7. Decisiones de diseño

- **3 contenedores:** Caddy (entrada HTTPS), app (nuestra imagen), Ollama (imagen oficial). Cada uno se actualiza por separado.
- **Solo Caddy queda expuesto a la red.** La app solo responde en `localhost:5000` del servidor y Ollama no tiene puertos publicados.
- **Usuario sin privilegios** dentro del contenedor de la app.
- **Whisper dentro de la imagen** y `HF_HUB_OFFLINE=1`.
- **Mismo lanzador** que el instalador de Windows (`empaquetado/launcher.py`) con `HRRG_EN_DOCKER=1`.
- **Healthchecks:** la app espera a Ollama; `iniciar` espera a la app.
- **Scripts `.bat` y `.sh`** con la misma lógica; `.gitattributes` mantiene los finales de línea correctos.
