# Casos simulados — Triage asistido HRRG

Versión 1.2 · Fuente: `backend/datos/casos_simulados.json` (este documento es un resumen legible).

**Casos FICTICIOS.** No corresponden a personas reales; sin nombre, DNI, domicilio ni teléfono.
El color de la demo (`nivel_maqueta`) **no tiene validez clínica**. Los colores reales los define C07 con la guía oficial, citando página.

## 1. Casos de demo y validación

### Demo (maquetado v33)

| ID | Paciente | Episodio | Relato | Color en la demo | PAM |
|---|---|---|---|---|---|
| D01 | PAC-DEMO-001 | EPI-004818 | Me duele el pecho desde hace media hora, como una presión, y estoy sudando. | Naranja | 113 |
| D02 | PAC-DEMO-002 | EPI-004815 | Me duele mucho la panza, acá arriba, desde hace unas 6 horas. Tengo ganas de vomitar y me siento afiebrada. Soy diabética, tomo pastillas. | Amarillo | 97 |
| D03 | PAC-DEMO-003 | EPI-004809 | Me torcí el tobillo jugando al fútbol, me duele al apoyar. | Verde | 93 |
| D04 | PAC-DEMO-004 | EPI-004806 | Vengo a que me miren la herida de la mano, me la hicieron hace tres días. | Azul | 90 |
| D05 | PAC-DEMO-002 | EPI-004815 | Reevaluación del caso D02: empeoró. | Naranja | 97 |

### Errores técnicos (deben rechazarse)

| ID | Qué prueba | Error esperado en |
|---|---|---|
| E01 | Error de tipeo: SpO2 8 en vez de 98 | saturacion_o2 |
| E02 | TA invertida | diastólica |
| E03 | Dato personal en el motivo | dato personal |
| E04 | DNI en antecedentes | dato personal |
| E05 | Campo con nombre desconocido | presion: campo no permitido |
| E06 | Opción fuera de catálogo | motivo_categoria |
| E07 | Texto en un campo numérico | frecuencia_cardiaca |
| E08 | Código de episodio con formato inválido | codigo_episodio |

### Faltantes y compatibilidad (válidos)

| ID | Qué prueba | Faltantes esperados |
|---|---|---|
| F01 | Solo el relato, sin mediciones (etapa ingreso completa) | ta_sistolica, ta_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, saturacion_o2, temperatura, dolor_intensidad |
| F02 | Campos vacíos del formulario cuentan como faltantes | dolor_localizacion, temperatura |
| F03 | Cero NO es faltante: dolor 0 es un valor real | ninguno |
| A01 | Nombres viejos (tas, saturacion, banderas_rojas, sexo 'F') se traducen | ninguno |

## 2. Casos de extracción (texto → campos que debe sacar MedGemma)

Sirven para C05/C06: se compara lo que extrae el modelo con lo esperado, campo por campo.
Regla clave: **lo que el texto no dice con un número queda vacío (null). El modelo no debe inventar valores.**

| ID | Tipo | Texto | Diagrama esperado | Resultado esperado | Nota |
|---|---|---|---|---|---|
| CF-01 | completo | Varón de 62 años con dolor opresivo en el pecho de 40 minutos de evolución, dolor 9/10. FC 112 lpm, FR 24, saturación 91 %, temperatura 36,8 °C. Alerta. Sin sangrado. | Dolor torácico | pendiente (C07) |  |
| CF-02 | completo | Mujer de 24 años, dolor de garganta desde hace 3 días, dolor 2/10. Temperatura 36,6 °C, FC 78, FR 14, saturación 99 %. Lúcida. Niega sangrado. | — | Información insuficiente | Motivo fuera de los 3 diagramas cargados: el motor debe devolver NO_CONCLUYENTE |
| CF-03 | completo | Mujer de 52 años con dolor abdominal en flanco derecho de 5 horas, dolor 8/10, con vómitos. Temperatura 37,4 °C, FC 102, FR 20, saturación 98 %. Orientada. No presenta sangrado. | Dolor abdominal en adulto | pendiente (C07) |  |
| CF-04 | completo | Varón de 30 años con fiebre y escalofríos desde hace 2 días. Temperatura 39,2 °C, FC 118, FR 22, saturación 95 %. Alerta. Refiere malestar general, sin dolor. Sin sangrado. | Malestar en adulto / fiebre | pendiente (C07) | 'sin dolor' = 0 (el texto lo afirma); a confirmar en EQ1 si se acepta 0 o null |
| CF-05 | faltantes | Mujer de 47 años que consulta por dolor torácico. Dolor 6/10. | Dolor torácico | Información insuficiente | Faltan signos vitales: no debe asignar color por defecto |
| CF-06 | faltantes | Consulta por dolor de panza desde ayer. | Dolor abdominal en adulto | Información insuficiente | 'desde ayer' no se convierte: valor y unidad en null |
| CF-07 | decimales_coma | Varón de 68 años, fiebre de 38,6 °C y tos con flema hace 4 días. FC 104 lpm, FR 24, saturación 92 %. Despierto. Niega sangrado. | Malestar en adulto / fiebre | pendiente (C07) | Prueba la coma decimal en la temperatura (38,6). La FC se registra sin decimales. |
| CF-08 | incompatible | Paciente de sesenta años con dolor abdominal intenso hace 2 horas. Temperatura 37 grados. | Dolor abdominal en adulto | Información insuficiente | Edad en letras -> 60. 'Dolor intenso' sin número -> null (no inventar 8 o 9) |
| CF-09 | incompatible | Adulto mayor con dolor en el pecho de unos minutos, refiere que es 'muy fuerte'. Saturación normal según familiar. | Dolor torácico | Información insuficiente | Trampa: 'adulto mayor', 'unos minutos', 'muy fuerte' y 'saturación normal' no tienen número -> todo null. El modelo NO debe inventar 98 % |
| CF-10 | negaciones | Mujer de 35 años con dolor abdominal 5/10 de 12 horas. Niega fiebre, niega sangrado. FC 88, FR 16, saturación 98 %, temperatura 36,7 °C. Lúcida. | Dolor abdominal en adulto | pendiente (C07) |  |
| CF-11 | conciencia_alterada | Varón de 71 años traído por familiares, malestar general desde hace 6 horas, solo responde cuando se le habla fuerte. Temperatura 38,9 °C, FC 124, FR 28, saturación 89 %. | Malestar en adulto / fiebre | pendiente (C07) |  |
| CF-12 | hemorragia | Varón de 58 años con dolor abdominal y vómitos con sangre desde hace 1 hora. Dolor 6/10. FC 120, FR 22, saturación 95 %, temperatura 36,5 °C. Alerta, se marea al pararse. | Dolor abdominal en adulto | pendiente (C07) |  |

### Campos esperados por caso

| ID | Edad | Categoría | Evolución | FC | FR | SpO₂ | T° | Dolor | Localización | Conciencia | Sangrado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CF-01 | 62 | Dolor torácico | 40 minutos | 112 | 24 | 91 | 36.8 | 9 | Tórax | Alerta | no |
| CF-02 | 24 | Otro | 3 días | 78 | 14 | 99 | 36.6 | 2 | Garganta | Alerta | no |
| CF-03 | 52 | Dolor abdominal | 5 horas | 102 | 20 | 98 | 37.4 | 8 | Flanco derecho | Alerta | no |
| CF-04 | 30 | Fiebre | 2 días | 118 | 22 | 95 | 39.2 | 0 |  | Alerta | no |
| CF-05 | 47 | Dolor torácico |  |  |  |  |  | 6 | Tórax |  |  |
| CF-06 |  | Dolor abdominal |  |  |  |  |  |  | Abdomen |  |  |
| CF-07 | 68 | Fiebre | 4 días | 104 | 24 | 92 | 38.6 |  |  | Alerta | no |
| CF-08 | 60 | Dolor abdominal | 2 horas |  |  |  | 37.0 |  | Abdomen |  |  |
| CF-09 |  | Dolor torácico |  |  |  |  |  |  | Tórax |  |  |
| CF-10 | 35 | Dolor abdominal | 12 horas | 88 | 16 | 98 | 36.7 | 5 | Abdomen | Alerta | no |
| CF-11 | 71 | Otro | 6 horas | 124 | 28 | 89 | 38.9 |  |  | Responde a la voz |  |
| CF-12 | 58 | Dolor abdominal | 1 horas | 120 | 22 | 95 | 36.5 | 6 | Abdomen | Alerta | sí |

Celda vacía = el texto no lo dice → debe quedar null.

## 3. Casos de API

| ID | Qué prueba | Respuesta HTTP esperada |
|---|---|---|
| API-01 | texto vacio | 422 |
| API-02 | solo espacios | 422 |

## Decisiones tomadas

- Frecuencia cardíaca y demás signos enteros **sin decimales** (13/10/2026).
- «Sin dolor» explícito = 0; dolor no mencionado = null.
- «Desde ayer», «unos minutos», «adulto mayor» no se convierten a número: quedan null.

## Pendientes

- Colores esperados con la guía oficial del HRRG (C07).
- Alinear los diagramas esperados (Dolor torácico, Dolor abdominal en adulto, Malestar/fiebre) con los que cargue Tomás en el RAG.
