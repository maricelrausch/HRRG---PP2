<h1 align="center">🏥 IngenIA Salud – Triage</h1>

<p align="center">
  <img src="docs/img/portada-triage.svg" alt="Ilustración de la entrada de la guardia con la pantalla de triage asistido" width="100%">
</p>

<p align="center">
  <b>Módulo de Triage Asistido por Inteligencia Artificial</b><br>
  Guardia Central · Hospital Regional Río Grande · Proyecto IngenIA Salud TDF
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-Sprint%203%20·%20cierre-7B1FA2" alt="Sprint 3">
  <img src="https://img.shields.io/badge/actualizado-30%2F10%2F2026-lightgrey" alt="30/10/2026">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white" alt="Flask 3.0">
  <img src="https://img.shields.io/badge/IA-Ollama%20local-2E7D32" alt="Ollama local">
  <img src="https://img.shields.io/badge/Docker-servidor%20HTTPS-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

Prototipo académico de **Prácticas Profesionalizantes II** (Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial, Centro Politécnico Superior Malvinas Argentinas). Es un copiloto para el box de triage: ordena el relato del paciente, controla que los datos estén completos y sugiere un color con su justificación. **El sistema propone y el profesional decide.**

> [!IMPORTANT]
> Prototipo en evaluación. Funciona **solo con casos ficticios** y todo el procesamiento ocurre en la red del hospital, sin servicios en la nube. Las reglas y los rangos de ejemplo no son los del HRRG: el hospital carga los suyos desde la pantalla de reglas.

---

## 📑 Contenido

1. [🩺 El problema](#-el-problema)
2. [⚙️ Cómo funciona](#️-cómo-funciona)
3. [✅ Qué incluye](#-qué-incluye)
4. [👥 Roles de usuario](#-roles-de-usuario)
5. [💻 Instalación](#-instalación)
6. [🔌 Endpoints para otros sistemas](#-endpoints-para-otros-sistemas)
7. [🧱 Arquitectura y tecnologías](#-arquitectura-y-tecnologías)
8. [🗂️ Estructura del repositorio](#️-estructura-del-repositorio)
9. [🔒 Datos y seguridad](#-datos-y-seguridad)
10. [📆 Avance por sprint](#-avance-por-sprint)
11. [🚧 Limitaciones y trabajo futuro](#-limitaciones-y-trabajo-futuro)
12. [📚 Documentación](#-documentación)
13. [🤝 Equipo](#-equipo)

---

## 🩺 El problema

En el box de triage de la Guardia Central, enfermería escucha el motivo de consulta, registra los signos vitales y asigna un color según reglas internas y su experiencia. Todo pasa en pocos minutos y bajo presión, lo que genera demoras, datos incompletos y diferencias de criterio entre turnos. En la visita del 19/10/2026 el hospital pidió un triage **más intuitivo** y con **trazabilidad de las reevaluaciones**.

---

## ⚙️ Cómo funciona

```text
 Relato del paciente        Signos vitales           Sugerencia               Decisión
 (dictado o escrito)  ──►   (los carga          ──►  color + motivos     ──►  del profesional
        │                   enfermería)              + datos faltantes        aceptar / modificar /
        ▼                                                  ▲                  rechazar (con motivo)
 MedGemma local ordena      MedGemma sugiere color ────────┤                        │
 el relato en campos        Reglas del hospital ───────────┘                        ▼
                            (fijan un color mínimo)                          En espera
                                                                            (reevaluación con reloj)
```

- **MedGemma ordena y sugiere, pero no decide.** Ordena el relato (motivo, localización, duración, síntomas) y propone un color con sus motivos. Los signos vitales, el dolor y las banderas rojas los carga enfermería.
- **Las reglas fijan un piso.** Si se cumple una regla, el color nunca queda por debajo, aunque MedGemma sugiera uno menor.
- **Nada clínico está escrito en el código.** Las reglas, los tiempos por color y los rangos normales de los signos vitales (por grupo etario) los carga la Jefatura de Guardia desde `reglas.html`, y cada cambio queda en el historial. Así otro hospital puede usar los suyos.
- **El profesional confirma.** Si modifica o rechaza la sugerencia, tiene que escribir el motivo y queda registrado.
- **Si la IA no responde**, el triage sigue de forma manual.

---

## ✅ Qué incluye

| Área | Funcionalidad |
|---|---|
| 🔐 Acceso | Inicio de sesión con roles, bloqueo por intentos fallidos, clave temporal, cambio obligatorio de contraseña y **cierre de sesión por inactividad** |
| 🎙️ Ingreso | Relato escrito o **dictado por voz** con Whisper local; MedGemma extrae los datos, la categoría sale por palabras clave (15 motivos de consulta, sin contar lo negado) y se precargan edad, sexo y banderas |
| 🩺 Evaluación | Signos vitales con rangos normales **según la edad** (lactante, niño, adolescente, adulto, adulto mayor), avisos de valores fuera de rango, control de datos faltantes y **condición especial** (policial, judicial, custodia, etc.) aparte del color clínico |
| 🎨 Sugerencia | **MedGemma sugiere el color** (rojo, naranja, amarillo o verde) con sus motivos, ajustado por las reglas del hospital, que indican cuál se aplicó. Muestra qué datos harían subir la prioridad. Si la IA no responde, el color sale solo de las reglas. El formulario se limpia después de cada decisión |
| 📋 Reglas del hospital | Pantalla con cinco pestañas: Reglas, Tiempos por color, **Signos vitales**, Historial de cambios y Cómo funcionan. Cada regla está activa o inactiva; desactivar una regla roja pide confirmación |
| 🔁 En espera | Lista de pacientes por color, búsqueda por código de episodio o DNI, reevaluación con reloj por color |
| 📺 Sala de espera | Pantalla para la sala o el celular (`sala.html`) con código corto, color y tiempo de espera, **sin datos personales** |
| 💬 Consulta | Chat con MedGemma sobre el caso, sin diagnósticos ni indicaciones de tratamiento |
| 📜 Auditoría | Historial por episodio con buscador, filtros y exportación a Excel o PDF protegidos con la contraseña del auditor |
| 🛠️ Administración | Alta de cuentas, roles, desbloqueo y claves temporales, con registro de cada acción |

---

## 👥 Roles de usuario

| Rol | Puede | No puede |
|---|---|---|
| **Enfermería** | Cargar casos, ver sugerencias, decidir y reevaluar | Gestionar cuentas ni reglas |
| **Médico** | Lo mismo que enfermería | Gestionar cuentas ni reglas |
| **Jefatura de Guardia** | Cargar, probar, activar y desactivar las reglas, y ajustar tiempos por color y rangos de signos vitales | Atender pacientes |
| **Auditor** | Consultar el historial, ver el DNI y exportar (pide su contraseña) | Modificar datos |
| **Administrador** | Gestionar cuentas y contraseñas | Atender pacientes |

---

## 💻 Instalación

Hay dos formas de instalarlo. **La recomendada para el hospital es Docker en un servidor**: se instala una vez y las PCs de la guardia entran por el navegador.

| | **A · Servidor con Docker** (recomendado) | **B · Instalador de Windows** |
|---|---|---|
| Dónde corre | Un servidor de la red (Windows o Linux) | Una sola PC |
| Quién lo usa | Todas las PCs de la red, por navegador | Solo esa PC |
| Internet | Para descargar el repo y los modelos (hay opción con pendrive) | No hace falta |
| Dictado por voz desde otras PCs | Sí, por HTTPS (Caddy) | No aplica |
| Actualizar | `git pull` y `actualizar` | Instalador de actualización |
| Uso pensado | **Entrega al HRRG** | Demo o puesto aislado |

### A · Servidor con Docker (recomendado)

Levanta tres contenedores: **Caddy** (HTTPS), la **app** (Flask, Whisper y RAG) y **Ollama** (modelos de IA). Necesita Docker instalado (Docker Engine en Linux o Docker Desktop en Windows).

```bash
git clone https://github.com/maricelrausch/HRRG---PP2.git /opt/ingenia     # Windows: C:\IngenIA
cd /opt/ingenia/docker
./configurar.sh            # IP y nombre del servidor
./descargar_modelos.sh     # medgemma:4b, qwen2.5 y embeddinggemma
./iniciar.sh               # la primera vez construye la imagen (10-20 min)
./crear_admin.sh
```

En Windows se usan los mismos scripts con extensión `.bat`. Después se entra desde cualquier PC de la red con `https://<IP o nombre del servidor>`.

> [!NOTE]
> El navegador solo deja usar el micrófono en sitios `https://`. Si el hospital no tiene certificado propio, hay que instalar en cada PC el certificado que genera `exportar_certificado`.

📘 Guía completa (pendrive, registro de imágenes, HTTPS, actualizaciones): [`docker/LEEME.md`](docker/LEEME.md).

### B · Instalador de Windows (una sola PC)

`Instalador_IngenIA_Salud_Triage.exe` (unos 6 GB, junto con sus archivos `.bin`) instala la app, Ollama y los modelos con doble clic, **sin Python y sin internet**. Crea un acceso directo y, en el primer inicio, pide crear la cuenta de administrador.

> [!WARNING]
> El instalador se arma a partir del código. Cada vez que cambia la app hay que volver a construirlo para que incluya los cambios.

🔧 Cómo se construye: [`empaquetado/LEEME.md`](empaquetado/LEEME.md).

### C · Desarrollo

<details>
<summary><b>Requisitos y puesta en marcha</b></summary>

<br>

| Necesario | Detalle |
|---|---|
| 🐍 Python | 3.11 o superior |
| 🦙 Ollama | Con `medgemma:4b`, `embeddinggemma` y `qwen2.5:0.5b` |
| 🌐 Navegador | Chrome o Edge actualizados (el dictado necesita micrófono) |

```powershell
ollama pull medgemma:4b
ollama pull embeddinggemma
ollama pull qwen2.5:0.5b

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Solo la primera vez: claves de cifrado del DNI y cuenta de administrador
python scripts/preparar_identificacion.py
python -m flask --app app crear-profesional
python -m flask --app app asignar-rol --rol admin

# Iniciar con la extracción real de MedGemma
$env:HRRG_MODO_EXTRACCION = "ia"
python app.py
```

Abrir **http://127.0.0.1:5000/**. Sin `HRRG_MODO_EXTRACCION=ia`, la app usa casos simulados y se puede probar el flujo sin Ollama.

</details>

<details>
<summary><b>Variables de entorno</b></summary>

<br>

| Variable | Para qué | Por defecto |
|---|---|---|
| `HRRG_MODO_EXTRACCION` | `ia` usa MedGemma; `simulado` usa casos de prueba | `simulado` |
| `MEDGEMMA_MODELO` | Modelo de Ollama | `medgemma:4b` |
| `OLLAMA_HOST` | Dirección de Ollama | `http://localhost:11434` |
| `WHISPER_MODELO` | Modelo de voz (`tiny`, `base`, `small`, `medium`) | `small` |
| `WHISPER_HILOS` / `MEDGEMMA_HILOS` | Reparto de la CPU entre voz e IA en PCs sin GPU | automático |
| `HRRG_SESION_INACTIVIDAD_MIN` | Minutos sin actividad hasta cerrar la sesión | `15` |
| `HRRG_API_HOSPITAL_TOKEN` | Habilita los endpoints con token (sin token responden 503) | sin definir |

</details>

<details>
<summary><b>Pruebas automáticas</b></summary>

<br>

```powershell
cd backend
python -m pytest -q tests
```

</details>

---

## 🔌 Endpoints para otros sistemas

La app expone rutas de **solo lectura** que devuelven JSON, para que otros sistemas del hospital usen la información sin entrar a la aplicación.

| Para qué | Ruta | Acceso | Datos personales |
|---|---|---|---|
| Pantallas de la sala de espera | `GET /api/sala/espera` | Público dentro de la red | No |
| Cola de espera para el sistema del hospital | `GET /api/cola-espera` | Token | No (DNI solo si se habilita) |
| Mediciones de un episodio | `GET /api/episodios/<codigo>/mediciones` | Token | No |
| Auditoría | `/api/auditoria/...` | Token propio | Sí |

Detalle con ejemplos de pedido y respuesta: [`docs/endpoints_externos.md`](docs/endpoints_externos.md) y [`docs/api_hospital.md`](docs/api_hospital.md).

---

## 🧱 Arquitectura y tecnologías

| Capa | Tecnología | Función |
|---|---|---|
| Interfaz | HTML, CSS y JavaScript | Ingreso, sugerencia, En espera, sala, reglas, auditoría y administración |
| Servidor | Flask 3 | API, sesiones, roles y validaciones |
| Datos | Pydantic y SQLite | Esquema único de campos, episodios, eventos, cuentas, reglas y rangos de signos vitales |
| IA | MedGemma 4B en Ollama | Extracción del relato, sugerencia de color y chat sobre el caso |
| Voz | faster-whisper (local) | Dictado sin enviar audio fuera de la red |
| Búsqueda documental | ChromaDB + embeddinggemma | Base para el RAG con guías |
| Seguridad | Hash de contraseñas, Fernet | Cuentas y DNI cifrado |
| Despliegue | Docker Compose + Caddy | Servidor con HTTPS para toda la red |
| Distribución | PyInstaller + Inno Setup | Instalador offline para una PC |

---

## 🗂️ Estructura del repositorio

```text
HRRG---PP2/
├── backend/
│   ├── app.py              # aplicación Flask y rutas
│   ├── ia/                 # MedGemma, chat, dictado (Whisper) y trazabilidad
│   ├── src/                # esquemas, validación, reglas, auth, admin, registro, cifrado, API
│   ├── datos/              # casos simulados y esquemas JSON
│   ├── evaluacion/         # métricas de extracción
│   ├── scripts/            # preparación de claves y pruebas de IA y voz
│   ├── tests/              # pruebas automáticas (pytest)
│   └── docs/               # diccionario de datos, controles y configuración de la IA
├── frontend/               # pantallas, estilos y JavaScript
├── docker/                 # despliegue en servidor (Compose, Caddy y scripts .bat/.sh)
├── empaquetado/            # instalador offline para Windows
├── docs/                   # manual de usuario, endpoints, políticas e imágenes
└── README.md
```

---

## 🔒 Datos y seguridad

- **Sin datos reales.** Se prueba con casos ficticios. El repositorio no tiene datos de pacientes, contraseñas ni pesos de modelos.
- **Todo local.** El relato, el audio y la IA se procesan dentro de la red del hospital, sin servicios en la nube (Leyes 25.326 y 26.529).
- **Los pacientes no se llaman por nombre.** Se usa el código de episodio; la sala de espera muestra solo los últimos cuatro caracteres.
- **DNI cifrado** y búsqueda por huella, con las claves fuera del repositorio.
- **Sesiones** que se cierran por inactividad y endpoints que, sin token, no responden.
- **Trazabilidad.** Cada extracción, corrección, decisión, cambio de regla y exportación queda registrado con usuario y hora.

---

## 📆 Avance por sprint

| Sprint | Período | Resultado |
|---|---|---|
| **1 · Planificación** | 28/09 – 04/10 | Equipo, roles, ámbito de desarrollo, carta de presentación y análisis del problema |
| **2 · Desarrollo** | 05/10 – 25/10 | Prototipo de punta a punta, visita a la guardia e instalador offline |
| **3 · Cierre** | 26/10 – 01/11 | Prueba de concepto en el HRRG (28/10), reglas y signos vitales configurables, sugerencia de color con MedGemma, despliegue con Docker, endpoints, cierre de sesión por inactividad, manuales y documento de escalabilidad |

---

## 🚧 Limitaciones y trabajo futuro

- **Reglas y guías del hospital:** las reglas y los rangos de signos vitales que trae el sistema son de ejemplo, no oficiales. El HRRG tiene que cargar y validar los suyos, y el RAG se completa cuando haya guías autorizadas.
- **Validación clínica:** no se informan métricas clínicas (concordancia, subtriage) hasta evaluarlo con referentes del hospital.
- **Rendimiento:** en un servidor sin GPU, MedGemma puede tardar entre 30 segundos y más de un minuto por respuesta.
- **Próximas versiones:** extensión a ginecología, pediatría y odontología, ajuste del modelo con LoRA e integración con la historia clínica (ver documento de escalabilidad).

---

## 📚 Documentación

| Documento | Ubicación |
|---|---|
| **Manual de usuario** | [`docs/manual_usuario.md`](docs/manual_usuario.md) |
| **Instalación en servidor (Docker)** | [`docker/LEEME.md`](docker/LEEME.md) |
| Instalador de Windows | [`empaquetado/LEEME.md`](empaquetado/LEEME.md) |
| Endpoints de sala y auditoría | [`docs/endpoints_externos.md`](docs/endpoints_externos.md) |
| Web service para el hospital | [`docs/api_hospital.md`](docs/api_hospital.md) |
| Contrato de API | [`docs/contrato_api.md`](docs/contrato_api.md) |
| Diccionario de datos V2 | [`backend/docs/diccionario_datos_v2.md`](backend/docs/diccionario_datos_v2.md) |
| Controles de validación | [`backend/docs/controles_validacion.md`](backend/docs/controles_validacion.md) |
| Configuración de la IA | [`backend/docs/configuracion_ia.md`](backend/docs/configuracion_ia.md) |
| Identificación cifrada | [`docs/identificacion_cifrada.md`](docs/identificacion_cifrada.md) |
| Política de registros | [`docs/politica_registros.md`](docs/politica_registros.md) |
| Guion de la demo | [`docs/guion_demo.md`](docs/guion_demo.md) |
| Manual de instalación, minutas, retrospectivas y escalabilidad | Carpeta del proyecto en Google Drive |

---

## 🤝 Equipo

**Equipo N1 – HRRG – PP2 2C 2026.** Los roles rotan en cada sprint.

| Integrante |
|---|
| Darío Martínez |
| Maricel Rausch |
| Tomás Alderete |
| Bárbara Rigoni |

Referente del HRRG: Esp. Bioing. Juan Francisco Navoni.

---

<p align="center">
  <sub>Equipo N1 · Prácticas Profesionalizantes II · Centro Politécnico Superior Malvinas Argentinas · Proyecto IngenIA Salud TDF · 2026</sub>
</p>
