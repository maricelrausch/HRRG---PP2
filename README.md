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

## Archivos del proyecto
```
├── data/
│   ├── raw/          → datos originales (sintéticos/anonimizados)
│   └── processed/    → datos trabajados
├── analysis/         → notebooks de pruebas y evaluación del modelo
├── src/              → código del prototipo (API, RAG, interfaz)
├── docs/             → documentación (ámbito de desarrollo, relevamiento normativo)
├── reports/          → entregables e informes
└── README.md
```
> Los archivos pesados y la documentación oficial se encuentran en Google Drive.

---

## Contactos

Darío Martínez – dario1979.dm@gmail.com

Maricel Rausch – maricelmrausch@gmail.com

Tomás Alderete – alderetetomas26@gmail.com

Bárbara Rigoni – barbyjrigoni@gmail.com


La documentación y la estructura del repositorio serán actualizadas a medida que avance el desarrollo.
