# 🏥 Equipo 1 - HRRG - PP2 2C 2026

### Módulo de Triage Asistido por IA (MedGemma + Guías de Manchester) – Guardia Central, Hospital Regional Río Grande

> Proyecto de **Prácticas Profesionalizantes II** – Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial – Centro Politécnico Superior Malvinas Argentinas. Proyecto IngenIA Salud TDF.
> ** Estado:** Sprint 1 – Planificación y análisis inicial (28/09/2026 – 04/10/2026)

## 👥 Equipo de trabajo

- Darío Martínez
- Maricel Rausch
- Tomás Alderete
- Bárbara Rigoni
  
---
  
## 📌 Descripción

En el triage de la Guardia Central, el personal de salud evalúa a cada paciente en pocos minutos y bajo alta presión. Esto genera demoras, omisión de antecedentes y variabilidad al priorizar la urgencia.

El proyecto desarrolla un **copiloto digital de triage** que:
- valida los datos ingresados (signos vitales, nivel de conciencia, dolor, banderas rojas, antecedentes);
- sugiere una categoría de las **Guías de Manchester** (Rojo, Naranja, Amarillo, Verde, Azul) con una justificación breve;
- resalta banderas rojas y avisa si faltan datos clave.

El sistema **propone, no decide**: el profesional acepta o modifica la sugerencia (con justificación obligatoria), y si la IA no está disponible el triage sigue de forma tradicional.

---

## Fuente de datos

- **Fuente:** casos clínicos **sintéticos o seudonimizados** y versiones oficiales de las Guías de Manchester y protocolos de la Guardia Central del HRRG. Solo se usan con autorización.
- **Tipo de datos:** motivo de consulta, signos vitales, nivel de conciencia, dolor, banderas rojas y antecedentes. Sin nombre, DNI ni datos administrativos.
- **Modelo base:** [MedGemma](https://developers.google.com/health-ai-developer-foundations/medgemma) – Google Health AI Developer Foundations.
- ⚠️ El repositorio **no contiene datos reales de pacientes** ni los pesos del modelo.

---

## 🔎 Objetivo del análisis

**Objetivo general** *(Protocolo de Investigación HRRG, 5.1)*: 

Desarrollar y validar un módulo de Triage Asistido por Inteligencia Artificial con MedGemma, integrado al Sistema Manchester utilizado en la Guardia Central del HRRG, evaluando su seguridad, concordancia, explicabilidad, factibilidad técnica y potencial utilidad como herramienta de apoyo al equipo de salud.

**Objetivos específicos** *(Protocolo de Investigación HRRG, 5.2)*:

1. Caracterizar la estructura y calidad de los datos disponibles en los registros de Triage de la Guardia Central.
2. Definir un conjunto mínimo de variables clínicas necesarias para el procesamiento por IA bajo el principio de minimización de datos.
3. Desarrollar una arquitectura híbrida que combine reglas clínicas explícitas, Sistema Manchester, MedGemma y validación humana.
4. Comparar retrospectivamente la prioridad sugerida por el sistema con la prioridad Manchester asignada por el profesional.
5. Cuantificar concordancia, subtriage, sobretriage, sensibilidad para categorías críticas y estabilidad del sistema.
6. Analizar errores, sesgos, discrepancias y posibles causas de falla.
7. Evaluar la calidad de la explicación generada por la IA y su capacidad para señalar datos faltantes o inconsistentes.
8. Definir criterios de avance hacia una fase de Shadow Mode y criterios de interrupción por seguridad.
9. Generar un marco institucional de gestión de datos, auditoría y gobernanza para futuras fases.

---

## Herramientas utilizadas

- Python · Google Colab / Jupyter
- MedGemma · Hugging Face Transformers / Ollama / vLLM
- Google Drive · Trello · GitHub · Google Meet

---

## Proceso de Análisis

1. **Sprint 1:** organización del equipo, relevamiento del problema y definición del ámbito de desarrollo.
2. **Sprint 2:** 
3. **Sprint 3:** 

---

## Resultados principales

_Se completará al finalizar los Sprints 2 y 3._
- Hallazgo 1
- Hallazgo 2
- Hallazgo 3

---

## Visualizaciones
_Se incorporarán capturas del prototipo y del dashboard de métricas._
<!-- ![Dashboard](reports/img/dashboard.png) -->

---

## Conclusiones
_Se completará al cierre del proyecto: qué se descubrió, implicancias para el hospital y líneas futuras._

---


## Estructura del proyecto

```text
HRRG---PP2/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── src/
│   │   ├── auth.py
│   │   ├── modelo.py
│   │   ├── rag.py
│   │   ├── registro.py
│   │   ├── reglas.py
│   │   ├── reporte.py
│   │   ├── salida.py
│   │   └── validacion.py
│   ├── datos/
│   │   ├── casos_simulados.json
│   │   ├── guias_ejemplo.json
│   │   └── umbrales.json
│   └── evaluacion/
│       ├── metricas.py
│       └── prueba_sin_guia.py
├── frontend/
│   ├── maquetado_extraccion_v33.html
│   ├── formulario.html
│   ├── estilos.css
│   ├── formulario.js
│   ├── validacion.js
│   └── img/
│       └── logo-hrrg.png
├── docs/
│   └── contrato_api.md
├── .gitignore
└── README.md
```

| Ubicación | Propósito |
|---|---|
| `backend/app.py` | Aplicación Flask, rutas y conexión con servicios. |
| `backend/src/` | Módulos de autenticación, registro, IA, reglas y salidas. |
| `backend/datos/` | Archivos destinados a casos ficticios y configuraciones de prueba. |
| `backend/evaluacion/` | Scripts de evaluación y métricas. |
| `frontend/` | Pantallas, estilos, JavaScript e imágenes. |
| `docs/` | Documentación técnica compartida. |

Algunos módulos y archivos están vacíos o en desarrollo. Su presencia
indica su ubicación prevista, no que la funcionalidad esté terminada.

## Ejecución local

Requisitos: Python y pip. El entorno de desarrollo utilizado es Python 3.12.7.

Desde la raíz del repositorio:

```powershell
cd backend
python -m pip install -r requirements.txt
python app.py
```

Abrir en el navegador:

http://127.0.0.1:5000/

Para detener el servidor, presionar `Ctrl + C`.

Flask sirve la maqueta `frontend/maquetado_extraccion_v33.html`
como página principal. El formulario anterior se conserva.

La visualización de la maqueta no implica que sus botones y pantallas
estén conectados a las API del backend.

El servidor de desarrollo de Flask se utiliza para pruebas locales.
La integración con modelos requiere, además del cliente Python,
el servicio Ollama y los modelos correspondientes.

## Administración de profesionales

Las cuentas son creadas por el ingeniero o administrador autorizado
desde la terminal. No hay registro público de usuarios.

Desde la carpeta `backend`:

```powershell
python -m flask --app app crear-profesional
```

Para cambiar una contraseña:

```powershell
python -m flask --app app cambiar-password
```

Las contraseñas se almacenan como hashes. No se pueden recuperar
en texto original; se puede establecer una nueva contraseña.

## Estado del backend

Implementado:

- Autenticación de profesionales con cuentas en SQLite.
- Inicio de sesión, consulta de sesión y cierre de sesión.
- Control de acceso en las rutas protegidas y comprobación de cuentas activas.
- Formato común de errores para las API adaptadas.
- Registro técnico con rotación de archivos.
- Creación y consulta de episodios ficticios.
- Registro del evento de apertura de cada episodio.
- Asociación del episodio con el código interno del paciente y el profesional.
- Rechazo de códigos de episodio duplicados.
- Separación de carpetas de backend y frontend.

### Endpoints disponibles

| Método | Ruta | Función |
|---|---|---|
| POST | `/api/login` | Iniciar sesión. |
| GET | `/api/sesion` | Consultar la sesión autenticada. |
| POST | `/api/logout` | Cerrar la sesión. |
| POST | `/api/demo/episodios` | Crear un episodio ficticio. |
| GET | `/api/demo/episodios/<codigo_episodio>` | Consultar un episodio del profesional autenticado. |

El borrador del contrato se encuentra en `docs/contrato_api.md`.

## Almacenamiento local

Las cuentas, los episodios de demostración, la clave de sesión y los
registros técnicos se guardan fuera del repositorio, en:

```text
~/.hrrg_pp2/
```

Esta carpeta contiene:

- `usuarios.db`: cuentas de profesionales.
- `triage_demo.db`: episodios ficticios y sus eventos.
- `session.key`: clave de firma de las sesiones.
- `sistema.log`: registro técnico, con archivos rotados.

Estos archivos no deben subirse a GitHub.

El registro de episodios demo todavía no almacena el proceso completo
de triage. El guardado heredado del formulario en `pacientes.jsonl`
sigue pendiente de revisión e integración con el registro de episodios.

## Próximas integraciones

- Conectar la maqueta con la autenticación y las API.
- Incorporar los esquemas y validaciones entregados por Darío.
- Integrar la extracción con MedGemma entregada por Tomás.
- Completar la trazabilidad del proceso de triage y sus correcciones.
- Incorporar la descarga opcional del informe en PDF.
- Definir e integrar el motor de reglas con fuentes y criterios aprobados.
- Completar las pruebas automáticas y la documentación de ejecución.

El prototipo se prueba con casos ficticios. Las clasificaciones
ilustrativas de la maqueta no representan un motor Manchester validado.


> Las bases de datos locales, claves de sesión y registros generados
no se incluyen en el repositorio.
> Los archivos pesados y la documentación oficial se encuentran en Google Drive.

---

## Contactos

Darío Martínez – dario1979.dm@gmail.com

Maricel Rausch – maricelmrausch@gmail.com

Tomás Alderete – alderetetomas26@gmail.com

Bárbara Rigoni – barbyjrigoni@gmail.com


La documentación y la estructura del repositorio serán actualizadas a medida que avance el desarrollo.
