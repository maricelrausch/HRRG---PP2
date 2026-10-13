# Diccionario de datos V2 – Módulo de Triage Asistido

12/10/2026 · Equipo N1 – HRRG PP2 2C 2026 · Reemplaza la versión del 07/10/2026

## Propósito y convenciones

Este diccionario define cada dato que entra, sale o se registra en el prototipo. Lo usan el
frontend, la extracción con IA, la API, la validación, los casos simulados y la evaluación,
para que **un mismo dato se llame igual en todas las capas** y se apliquen los mismos rangos.

- **Fuente de verdad en código:** `src/esquemas.py` (Pydantic). Si este documento y el código
  no coinciden, se corrige uno de los dos; la prueba `tests/test_esquemas.py` lo controla.
- **Nombres:** los del maquetado v33. Los nombres de la V1 se aceptan como alias (ver tabla al final).
- **Faltante vs. cero:** un campo vacío (`""` o `null`) es **faltante**; `0` es un valor real
  y se valida contra su rango (por ejemplo, dolor 0).
- **Decimales:** se aceptan con coma o punto (`37,8` = `37.8`).
- **Rangos de plausibilidad, no umbrales clínicos.** Solo detectan errores de tipeo
  (por ejemplo, SpO₂ de 8 %). No definen gravedad. Los umbrales de alerta los define el HRRG.

**Columnas de las tablas**

| Columna | Significado |
|---|---|
| Campo | Nombre que se usa en el código, los formularios y los JSON |
| Descripción | Qué representa el dato |
| Tipo | número entero, número decimal, texto, opción (un valor de una lista), sí/no, fecha |
| Unidad | Unidad de medida, si corresponde |
| Rango / valores | Valores aceptados; fuera de rango el dato se rechaza |
| Origen | HCE (historia clínica), IA (extraído del relato y revisado por enfermería), medición, sistema |
| Oblig. | Etapa en la que el dato debe estar (ingreso o medición). Si falta, no bloquea: se informa como faltante |
| Ejemplo | Valor de muestra (siempre simulado) |

## Datos de entrada

### Identificación del episodio

| Campo | Descripción | Tipo | Unidad | Rango / valores | Origen | Oblig. | Ejemplo |
|---|---|---|---|---|---|---|---|
| codigo_episodio | Identificador interno del episodio; reemplaza los datos personales | texto | — | `EP-` + 4 a 10 letras/números | sistema | — | EP-004815 |
| edad | Edad del paciente | número entero | años | 0 – 120 | HCE | ingreso | 58 |
| sexo | Sexo, cuando es clínicamente relevante | opción | — | Femenino, Masculino, No informado | HCE | ingreso | Femenino |

### Relato y motivo de consulta (extraído por la IA, revisado por enfermería)

| Campo | Descripción | Tipo | Unidad | Rango / valores | Origen | Oblig. | Ejemplo |
|---|---|---|---|---|---|---|---|
| motivo_categoria | Categoría del motivo | opción | — | Dolor torácico, Dolor abdominal, Disnea, Trauma, Fiebre, Cefalea, Síntoma neurológico, Otro | IA | ingreso | Dolor abdominal |
| tiempo_evolucion_valor | Desde hace (valor) | número decimal | — | 0 – 10000 | IA | ingreso | 6 |
| tiempo_evolucion_unidad | Desde hace (unidad) | opción | — | minutos, horas, días | IA | ingreso | horas |
| motivo_consulta | Resumen del relato | texto | — | hasta 500 caracteres; sin datos personales | IA | ingreso | Dolor abdominal alto con náuseas |
| dolor_localizacion | Dónde le duele | texto | — | hasta 100 caracteres | IA | ingreso | Epigastrio |
| sintomas_asociados | Síntomas que refiere | texto | — | hasta 300 caracteres | IA | No | Náuseas, se siente afiebrada |
| dolor_caracteristicas | Cómo es el dolor | texto | — | hasta 200 caracteres | IA | No | Opresivo |

### Signos vitales

| Campo | Descripción | Tipo | Unidad | Rango / valores | Origen | Oblig. | Ejemplo |
|---|---|---|---|---|---|---|---|
| ta_sistolica | Tensión arterial sistólica | número entero | mmHg | 50 – 260 | medición | medición | 130 |
| ta_diastolica | Tensión arterial diastólica | número entero | mmHg | 20 – 160 | medición | medición | 80 |
| frecuencia_cardiaca | Frecuencia cardíaca | número entero | lpm | 20 – 250 | medición | medición | 98 |
| frecuencia_respiratoria | Frecuencia respiratoria | número entero | rpm | 4 – 60 | medición | medición | 18 |
| saturacion_o2 | Saturación de oxígeno (SpO₂) | número entero | % | 50 – 100 | medición | medición | 97 |
| temperatura | Temperatura corporal | número decimal | °C | 30,0 – 43,0 | medición | medición | 37,8 |
| glucemia | Glucemia capilar | número entero | mg/dL | 20 – 800 | medición | No | 210 |
| pam | Presión arterial media = (sistólica + 2 × diastólica) / 3 | número entero | mmHg | calculada, no se carga | sistema | — | 97 |

### Conciencia, dolor y aspecto

| Campo | Descripción | Tipo | Unidad | Rango / valores | Origen | Oblig. | Ejemplo |
|---|---|---|---|---|---|---|---|
| estado_conciencia | Estado de conciencia (AVDN) | opción | — | Alerta, Responde a la voz, Responde al dolor, No responde | medición | No | Alerta |
| glasgow | Escala de coma de Glasgow | número entero | puntos | 3 – 15 | medición | No | 15 |
| dolor_intensidad | Intensidad del dolor | número entero | escala 0–10 | 0 – 10 | medición | medición | 7 |
| aspecto_general | Aspecto general | texto | — | hasta 200 caracteres | medición | No | Pálida, sudorosa |

### Banderas rojas (sí/no)

| Campo | Descripción | Tipo | Origen | Valor por defecto |
|---|---|---|---|---|
| br_sangrado | Sangrado evidente | sí/no | IA | no |
| br_convulsion | Convulsión activa | sí/no | IA | no |
| br_disnea | Dificultad para respirar | sí/no | IA | no |
| br_trauma | Mecanismo de trauma | sí/no | IA | no |

### Antecedentes

| Campo | Descripción | Tipo | Origen | Ejemplo |
|---|---|---|---|---|
| ant_diabetes | Diabetes | sí/no | IA | sí |
| ant_cardio | Cardiovascular | sí/no | IA | no |
| ant_resp | Respiratorio | sí/no | IA | no |
| ant_anticoag | Anticoagulación | sí/no | IA | no |
| ant_inmuno | Inmunosupresión | sí/no | IA | no |
| ant_embarazo | Embarazo | sí/no | IA | no |
| ant_medicacion | Medicación crítica | sí/no | IA | no |
| alergias | Alergias, en texto (hasta 200 caracteres) | texto | IA | Penicilina |
| antecedentes_otros | Otros antecedentes, en texto (hasta 200 caracteres) | texto | IA | Toma pastillas para la diabetes |

## Datos prohibidos y reglas de consistencia

**Datos prohibidos.** El sistema no recibe ni procesa nombre, apellido, DNI, teléfono, domicilio
ni datos administrativos no vinculados al riesgo de salud (Ley 25.326). Si aparecen en cualquier
texto libre, la consulta se rechaza y se pide corregir.

**Reglas de consistencia** (backend: `src/validacion.py`; frontend: `frontend/validacion.js`)

| # | Regla | Qué hace el sistema |
|---|---|---|
| 1 | Valor fuera de rango | Rechaza el dato y pide corregirlo antes de procesar |
| 2 | Texto en un campo numérico (por ejemplo «94 %» o «noventa») | Rechaza; el campo admite solo números |
| 3 | Opción fuera de la lista | Rechaza y muestra las opciones válidas |
| 4 | ta_diastolica mayor o igual a ta_sistolica | Error: se pide revisar la tensión arterial |
| 5 | Dato personal en un texto libre | Rechaza y pide quitarlo |
| 6 | Campo con nombre desconocido | Rechaza (evita nombres distintos entre capas) |
| 7 | Campo obligatorio vacío | No bloquea: se procesa y se informa en `missing_data` |
| 8 | codigo_episodio con formato inválido | Rechaza |
| 9 | Relato que contradice los signos vitales | Se responde «Información insuficiente» y se pide reevaluar |

## Datos de salida

Formato JSON pedido por el hospital. Si falta un campo, un valor está fuera de lo permitido o el
JSON no se puede leer, la respuesta se descarta y queda «Información insuficiente».

| Campo | Descripción | Tipo | Rango / valores | Ejemplo |
|---|---|---|---|---|
| color | Categoría Manchester sugerida | opción | Rojo, Naranja, Amarillo, Verde, Azul o null (información insuficiente) | Amarillo |
| confidence | Confianza de la sugerencia | número decimal | 0 – 1 | 0,7 |
| red_flags | Signos o síntomas de alarma presentes; nunca diagnósticos | lista de textos | — | ["dolor intenso"] |
| possible_discriminators | Discriminadores Manchester que se cumplen | lista de textos | — | ["dolor moderado"] |
| missing_data | Datos de triage que faltan; los calcula Python, no el modelo | lista de textos | nombres de campos de entrada | ["temperatura"] |
| rationale | Justificación breve con los valores del paciente | texto | mínimo 10 caracteres; sin diagnóstico, prescripción ni alta | Dolor 7/10 con FC 98 lpm |
| human_validation_required | Indica que la decisión final es del profesional | sí/no | siempre true | true |

## Datos del registro

Una línea por evento en `logs/log_triage.jsonl`.

**Evento «sugerencia»**

| Campo | Descripción | Tipo | Unidad | Ejemplo |
|---|---|---|---|---|
| fecha_hora | Momento del evento | fecha y hora (ISO 8601) | — | 2026-10-12T21:30:05 |
| evento | Tipo de evento | texto | — | sugerencia |
| codigo_episodio | Identificador del episodio | texto | — | EP-004815 |
| modelo | Modelo usado | texto | — | medgemma1.5 |
| version_guia | Versión de las guías Manchester usadas | texto | — | ejemplo-v1 |
| caso | Datos de entrada validados (sin datos personales) | objeto | — | — |
| salida | Estado, resultado, alertas y avisos | objeto | — | — |
| latencia_s | Tiempo total de respuesta | número decimal | segundos | 6,42 |
| carga_modelo_s | Tiempo de carga del modelo | número decimal | segundos | 0,15 |
| generacion_s | Tiempo de generación de la respuesta | número decimal | segundos | 5,90 |

**Evento «decision»**

| Campo | Descripción | Tipo | Ejemplo |
|---|---|---|---|
| fecha_hora | Momento de la decisión | fecha y hora (ISO 8601) | 2026-10-12T21:31:10 |
| evento | Tipo de evento | texto | decision |
| codigo_episodio | Identificador del episodio | texto | EP-004815 |
| id_profesional | Usuario que decidió (login individual) | texto | enfermeria |
| decision | Qué hizo el profesional | opción: aceptar, modificar, descartar | modificar |
| color_final | Color asignado; obligatorio salvo al descartar | opción | Naranja |
| motivo_discrepancia | Por qué modificó o descartó; obligatorio en esos casos | texto | Antecedente cardíaco grave |

## Correspondencia con la V1 (alias aceptados)

El backend traduce solo estos nombres viejos, para no romper código existente mientras se migra.

| V1 (07/10) | V2 |
|---|---|
| tas | ta_sistolica |
| tad | ta_diastolica |
| frec_cardiaca | frecuencia_cardiaca |
| frec_respiratoria | frecuencia_respiratoria |
| saturacion | saturacion_o2 |
| dolor | dolor_intensidad |
| localizacion_dolor | dolor_localizacion |
| sexo: M / F / X | Masculino / Femenino / No informado |
| banderas_rojas: sangrado, convulsion, dificultad_respiratoria, trauma | br_sangrado, br_convulsion, br_disnea, br_trauma = sí |
| antecedentes: diabetes, cardiaco, medicacion_critica | ant_diabetes, ant_cardio, ant_medicacion = sí |

**Cambios de criterio respecto de la V1:** edad hasta 120; glasgow pasa a opcional (se suma
estado_conciencia); se agregan categoría, tiempo de evolución, síntomas, características del
dolor, glucemia, PAM, aspecto, alergias y cuatro antecedentes nuevos; el registro suma
id_profesional.

## Pendientes a validar con el HRRG

- ☐ Rangos de plausibilidad de cada signo vital.
- ☐ Si la temperatura es obligatoria en todos los casos.
- ☐ Formato del código de episodio seudonimizado.
- ☐ Si la edad se carga exacta o por rango.
- ☐ Lista completa de banderas rojas, antecedentes y categorías de motivo que usa la guardia.
- ☐ Si se usa AVDN, Glasgow o ambos.
- ☐ Si el formulario actual de triage tiene campos que no están en este diccionario.
