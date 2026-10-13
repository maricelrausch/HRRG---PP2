# Diccionario de datos V2 — Triage asistido HRRG

Tabla de control generada desde `src/esquemas.py`. El documento del equipo es `diccionario_datos_v2.md`.

- Nombres = maquetado v33. Un mismo campo se llama igual en frontend, IA y API.
- Campo vacío (`""` o `null`) = **faltante**. `0` es un valor real y se valida contra su rango.
- Decimales con coma o punto (`37,8` = `37.8`).
- Obligatorio por etapa: si falta no bloquea; se informa en `missing_data`.
- Rangos de plausibilidad (errores de tipeo), **no** umbrales clínicos.

| Campo | Descripción | Tipo | Unidad | Rango | Origen | Obligatorio (etapa) | Alias aceptados |
|---|---|---|---|---|---|---|---|
| `edad` | Edad | entero | años | 0–120 | HCE | ingreso |  |
| `sexo` | Sexo | opción: Femenino / Masculino / No informado |  |  | HCE | ingreso |  |
| `motivo_categoria` | Categoría del motivo | opción: Dolor torácico / Dolor abdominal / Disnea / Trauma / Fiebre / Cefalea / Síntoma neurológico / Otro |  |  | IA | ingreso |  |
| `tiempo_evolucion_valor` | Desde hace (valor) | decimal |  | 0–10000 | IA | ingreso |  |
| `tiempo_evolucion_unidad` | Desde hace (unidad) | opción: minutos / horas / días |  |  | IA | ingreso |  |
| `motivo_consulta` | Motivo (resumen del relato) | texto |  |  | IA | ingreso |  |
| `dolor_localizacion` | Dónde le duele | texto |  |  | IA | ingreso | `localizacion_dolor` |
| `sintomas_asociados` | Síntomas que refiere | texto |  |  | IA | no |  |
| `dolor_caracteristicas` | Cómo es el dolor | texto |  |  | IA | no |  |
| `br_sangrado` | Sangrado evidente | sí/no |  |  | IA | no | `banderas_rojas[sangrado]` |
| `br_convulsion` | Convulsión activa | sí/no |  |  | IA | no | `banderas_rojas[convulsion]` |
| `br_disnea` | Dificultad para respirar | sí/no |  |  | IA | no | `banderas_rojas[dificultad_respiratoria]` |
| `br_trauma` | Mecanismo de trauma | sí/no |  |  | IA | no | `banderas_rojas[trauma]` |
| `ant_diabetes` | Diabetes | sí/no |  |  | IA | no | `antecedentes[diabetes]` |
| `ant_cardio` | Cardiovascular | sí/no |  |  | IA | no | `antecedentes[cardiaco]` |
| `ant_resp` | Respiratorio | sí/no |  |  | IA | no |  |
| `ant_anticoag` | Anticoagulación | sí/no |  |  | IA | no |  |
| `ant_inmuno` | Inmunosupresión | sí/no |  |  | IA | no |  |
| `ant_embarazo` | Embarazo | sí/no |  |  | IA | no |  |
| `ant_medicacion` | Medicación crítica | sí/no |  |  | IA | no | `antecedentes[medicacion_critica]` |
| `alergias` | Alergias | texto |  |  | IA | no |  |
| `antecedentes_otros` | Otros antecedentes | texto |  |  | IA | no |  |
| `ta_sistolica` | TA sistólica | entero | mmHg | 50–260 | medición | medicion | `tas` |
| `ta_diastolica` | TA diastólica | entero | mmHg | 20–160 | medición | medicion | `tad` |
| `frecuencia_cardiaca` | Frec. cardíaca | entero | lpm | 20–250 | medición | medicion | `frec_cardiaca`, `fc` |
| `frecuencia_respiratoria` | Frec. respiratoria | entero | rpm | 4–60 | medición | medicion | `frec_respiratoria`, `fr` |
| `saturacion_o2` | SpO₂ | entero | % | 50–100 | medición | medicion | `saturacion`, `spo2` |
| `temperatura` | Temperatura | decimal | °C | 30–43 | medición | medicion |  |
| `glucemia` | Glucemia capilar | entero | mg/dL | 20–800 | medición | no |  |
| `estado_conciencia` | Estado de conciencia (AVDN) | opción: Alerta / Responde a la voz / Responde al dolor / No responde |  |  | medición | no |  |
| `glasgow` | Glasgow | entero | 3–15 | 3–15 | medición | no |  |
| `dolor_intensidad` | Escala de dolor | entero | 0–10 | 0–10 | medición | medicion | `dolor` |
| `aspecto_general` | Aspecto general | texto |  |  | medición | no |  |
| `codigo_episodio` | Código de episodio (no identifica al paciente) | texto |  |  | sistema | no |  |
| `pam` | PAM calculada (sistólica + 2·diastólica) / 3 | entero | mmHg |  | calculado | no |  |

## Controles técnicos (backend `src/validacion.py`; reflejar en `frontend/validacion.js`)

1. Tipo y rango de cada campo numérico según la tabla.
2. Opciones cerradas: solo los valores listados.
3. TA diastólica menor que sistólica.
4. Sin datos personales en textos libres (DNI, teléfono, nombre, domicilio) — Ley 25.326.
5. Campos desconocidos se rechazan.
6. Faltantes por etapa (`ingreso`, `medicion`) se listan, no bloquean.
7. `codigo_episodio` con formato `EP-XXXXXX`.
