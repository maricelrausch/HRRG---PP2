# Controles de validación — C04

12/10/2026 · Define: Darío (backend `src/validacion.py`) · Refleja: Bárbara (`frontend/validacion.js`)

El backend es el control final: aunque el frontend deje pasar algo, `src/validacion.py` lo rechaza.
El frontend repite los mismos controles para avisar antes, mientras se completa el formulario.
Ningún control asigna gravedad clínica: solo tipos, rangos, opciones, coherencia y privacidad.

## Controles

| # | Control | Qué hace | Bloquea |
|---|---|---|---|
| 1 | Tipo numérico | Solo números; acepta coma o punto decimal. «94 %» o «noventa» = error | Sí |
| 2 | Entero | edad, TA, FC, FR, SpO₂, glucemia, Glasgow y dolor sin decimales | Sí |
| 3 | Rango de plausibilidad | Según la tabla de rangos (abajo) | Sí |
| 4 | Opción cerrada | Solo los valores de la lista | Sí |
| 5 | Coherencia TA | ta_diastolica menor que ta_sistolica | Sí |
| 6 | Privacidad (Ley 25.326) | En textos libres: DNI/documento, números de 7+ dígitos, teléfono, email, nombre/apellido, domicilio | Sí |
| 7 | Campo desconocido | Un nombre que no está en el diccionario se rechaza | Sí (solo backend) |
| 8 | Formato de códigos | codigo_paciente y codigo_episodio: `XXX-XXXX` (ej. PAC-DEMO-001) | Sí |
| 9 | Faltantes por etapa | Lista los obligatorios vacíos de `ingreso` y `medicion` | **No**: se informan |
| 10 | Vacío ≠ cero | `""` o null = faltante; `0` es un valor real | — |

## Rangos

| Campo | Mín | Máx | Entero |
|---|---|---|---|
| edad | 0 | 120 | sí |
| ta_sistolica | 50 | 260 | sí |
| ta_diastolica | 20 | 160 | sí |
| frecuencia_cardiaca | 20 | 250 | sí |
| frecuencia_respiratoria | 4 | 60 | sí |
| saturacion_o2 | 50 | 100 | sí |
| temperatura | 30 | 43 | no |
| glucemia | 20 | 800 | sí |
| glasgow | 3 | 15 | sí |
| dolor_intensidad | 0 | 10 | sí |
| tiempo_evolucion_valor | 0 | 10000 | no |

## Obligatorios por etapa

- **ingreso:** edad, sexo, motivo_categoria, tiempo_evolucion_valor, tiempo_evolucion_unidad, motivo_consulta, dolor_localizacion
- **medicion:** ta_sistolica, ta_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, saturacion_o2, temperatura, dolor_intensidad

## Cambios a hacer en `frontend/validacion.js` (Bárbara)

El archivo actual ya tiene bien la lógica (número, rango, TA, privacidad, faltantes). Hay que actualizar
nombres y listas al diccionario V2:

| Hoy en validacion.js | Pasa a |
|---|---|
| `tas`, `tad` | `ta_sistolica`, `ta_diastolica` |
| `frec_cardiaca`, `frec_respiratoria` | `frecuencia_cardiaca`, `frecuencia_respiratoria` |
| `saturacion` | `saturacion_o2` |
| `dolor` | `dolor_intensidad` |
| `localizacion_dolor` | `dolor_localizacion` |
| edad máx. 110 | 120 |
| sexo `M`, `F`, `X` | `Femenino`, `Masculino`, `No informado` |
| `banderas_rojas` (lista) | `br_sangrado`, `br_convulsion`, `br_disnea`, `br_trauma` (sí/no) |
| `antecedentes` (lista) | `ant_diabetes`, `ant_cardio`, `ant_resp`, `ant_anticoag`, `ant_inmuno`, `ant_embarazo`, `ant_medicacion` (sí/no) |
| `required` con glasgow y codigo_episodio | obligatorios por etapa (arriba); glasgow y códigos no son obligatorios |
| — | agregar `glucemia`, `tiempo_evolucion_valor` (rango y número) |
| — | agregar opciones: `motivo_categoria`, `tiempo_evolucion_unidad`, `estado_conciencia` |
| — | privacidad también en `sintomas_asociados`, `dolor_caracteristicas`, `aspecto_general`, `alergias` |

Referencia exacta (tipos, rangos y opciones): `backend/datos/esquemas/DatosTriage.json`.
