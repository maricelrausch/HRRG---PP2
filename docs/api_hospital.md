# Web service para el sistema del hospital

Propuesta del profesor (opcional para la prueba de concepto). La app expone dos rutas de **solo lectura** que devuelven JSON; el sistema del HRRG las consulta y se encarga de su parte. Así no hace falta que nosotros nos conectemos al sistema interno del hospital. Va en la misma app Flask (no hace falta FastAPI).

```
Sistema del hospital  ──GET──▶  /api/cola-espera                          ──▶ JSON
                      ──GET──▶  /api/episodios/<codigo_episodio>/mediciones ──▶ JSON
```

Código: `backend/src/api_hospital.py` · Pruebas: `backend/tests/test_api_hospital.py` (`python -m pytest -q tests/test_api_hospital.py`).

## Cómo habilitarla

La API arranca **apagada**: si no hay token configurado responde `503`. Para encenderla, antes de iniciar la app:

```bat
:: Generar un token largo y aleatorio (una vez) y compartirlo solo con el hospital
python -c "import secrets; print(secrets.token_urlsafe(32))"

set HRRG_API_HOSPITAL_TOKEN=<el token generado>
python app.py
```

| Variable | Qué hace |
|---|---|
| `HRRG_API_HOSPITAL_TOKEN` | Token que tiene que mandar el hospital (mínimo 16 caracteres). Sin ella, la API no responde datos. |
| `HRRG_API_HOSPITAL_DNI=1` | Agrega el DNI a las respuestas. **Por defecto no sale.** Usarlo solo con HTTPS y acuerdo del hospital. |

El puerto no tiene que ser el 80: se usa el mismo de la app (por ejemplo 5000) o el que se configure.

## Autenticación

Cada pedido lleva el token en la cabecera:

```
Authorization: Bearer <token>
```

Sin token o con token incorrecto: `401 TOKEN_INVALIDO`. Las rutas solo aceptan `GET` (un `POST` da `405`).

## GET /api/cola-espera

Pacientes en espera **ya clasificados**, ordenados por prioridad (ROJO primero) y, dentro de cada color, por quien espera más. Los episodios sin color no aparecen porque todavía no pasaron por el triage. No hay color AZUL.

Filtro opcional: `?color=ROJO|NARANJA|AMARILLO|VERDE` (la `posicion` sigue siendo el puesto en la cola completa).

```bash
curl -H "Authorization: Bearer $TOKEN" http://<pc-de-triage>:5000/api/cola-espera
```

```json
{
  "ok": true,
  "version_api": "1.0",
  "modo": "demo",
  "generado_en": "2026-10-27T21:44:15+00:00",
  "total": 4,
  "por_color": {"ROJO": 1, "NARANJA": 0, "AMARILLO": 2, "VERDE": 1},
  "pacientes": [
    {
      "posicion": 1,
      "codigo_episodio": "EPI-ROJO001",
      "codigo_paciente": "PAC-ROJO001",
      "color": "ROJO",
      "prioridad": 1,
      "en_espera_desde": "2026-10-27T21:42:15+00:00",
      "espera_min": 2,
      "tiempo_maximo_min": 0,
      "vencido": false,
      "ingreso_en": "2026-10-27T21:34:15+00:00",
      "triage_en": "2026-10-27T21:42:15+00:00",
      "tiempo_restante_min": -2,
      "proximo_a_vencer": false,
      "motivo_categoria": "Disnea",
      "condicion_especial": null
    },
    {
      "posicion": 2,
      "codigo_episodio": "EPI-AMARI01",
      "codigo_paciente": "PAC-AMARI01",
      "color": "AMARILLO",
      "prioridad": 3,
      "en_espera_desde": "2026-10-27T20:29:15+00:00",
      "espera_min": 75,
      "tiempo_maximo_min": 60,
      "vencido": true,
      "ingreso_en": "2026-10-27T20:21:15+00:00",
      "triage_en": "2026-10-27T20:29:15+00:00",
      "tiempo_restante_min": -15,
      "proximo_a_vencer": false,
      "motivo_categoria": "Cefalea",
      "condicion_especial": "Custodia policial"
    }
  ]
}
```

`prioridad`: 1 ROJO, 2 NARANJA, 3 AMARILLO, 4 VERDE. `vencido` es `true` cuando la espera supera el tiempo máximo del color.

[Actualizado 29/10, pedido de Francisco Navoni]
- `tiempo_maximo_min`: ya no es fijo. Sale de la configuración de la Jefatura de Guardia (`reglas.html`); por defecto, los de referencia Manchester: ROJO 0, NARANJA 10, AMARILLO 60, VERDE 120.
- `ingreso_en`: cuándo se creó el episodio. `triage_en`: cuándo se registró la última clasificación.
- `tiempo_restante_min`: minutos que faltan para el tiempo máximo; negativo = ya lo superó.
- `proximo_a_vencer`: `true` en el último 25 % del tiempo máximo (nunca en ROJO).
- `condicion_especial`: Policial, Judicial, Custodia policial, Violencia, Accidente laboral, Salud mental, Otra o `null`. Es una condición administrativa o legal, **no** cambia `color` ni `prioridad`.

## GET /api/episodios/<codigo_episodio>/mediciones

Los datos registrados durante la evaluación, los mismos que salen en el PDF/Excel: datos de ingreso, decisión profesional y todas las mediciones con las correcciones ya aplicadas. `ultima_medicion` repite la más reciente para no tener que buscarla.

```bash
curl -H "Authorization: Bearer $TOKEN" http://<pc-de-triage>:5000/api/episodios/EPI-AMARI01/mediciones
```

```json
{
  "ok": true,
  "version_api": "1.0",
  "modo": "demo",
  "generado_en": "2026-10-27T21:44:15+00:00",
  "episodio": {"codigo_episodio": "EPI-AMARI01", "codigo_paciente": "PAC-AMARI01",
               "creado_en": "2026-10-27T20:29:15+00:00", "estado": "en_espera"},
  "datos_ingreso": {"edad": 58, "sexo": "Femenino", "motivo_categoria": "Cefalea", "motivo_consulta": null,
                    "condicion_especial": "Custodia policial",
                    "tiempo_evolucion": {"valor": 6, "unidad": "horas"},
                    "banderas_rojas": ["Dificultad para respirar"], "antecedentes": ["Diabetes"],
                    "registrado_en": "2026-10-27T20:29:15+00:00"},
  "decision": {"color": "AMARILLO", "decision": "aceptar", "motivo": "", "profesional": "med1",
               "registrada_en": "2026-10-27T20:29:15+00:00", "escalado_rojo": false},
  "ultima_medicion": {"medicion_id": 10, "medido_en": "2026-10-27T21:34:15+00:00",
                      "registrado_en": "2026-10-27T21:44:15+00:00", "profesional": "enf1", "corregida": false,
                      "valores": {"ta_sistolica": 150, "ta_diastolica": 95, "pam": 113, "frecuencia_cardiaca": 110}},
  "mediciones": ["… todas, de la más vieja a la más nueva, con el mismo formato que ultima_medicion …"]
}
```

Campos posibles en `valores` (solo vienen los que se registraron): `ta_sistolica`, `ta_diastolica`, `pam`, `frecuencia_cardiaca`, `frecuencia_respiratoria`, `saturacion_o2`, `temperatura`, `glucemia`, `estado_conciencia`, `glasgow`, `dolor_intensidad`, `aspecto_general`. Unidades en `backend/docs/diccionario_datos_v2.md`.

## Errores

Siempre con el mismo formato: `{"ok": false, "codigo": "...", "mensaje": "..."}`

| HTTP | código | cuándo |
|---|---|---|
| 400 | `PARAMETROS_INVALIDOS` / `COLOR_INVALIDO` | parámetro desconocido o color que no existe |
| 401 | `TOKEN_INVALIDO` | falta el token o no coincide |
| 404 | `EPISODIO_NO_ENCONTRADO` | el código de episodio no existe |
| 500 | `ERROR_REGISTRO` | no se pudo leer la base |
| 503 | `API_DESHABILITADA` | no se configuró `HRRG_API_HOSPITAL_TOKEN` |

## Seguridad (lo aclarado en la reunión)

- **Para la demo se usan datos ficticios** (`"modo": "demo"` en cada respuesta).
- Estar dentro de la red del hospital **no garantiza seguridad**: por eso el token es obligatorio aun en la red interna.
- **El DNI es dato personal**: no sale salvo que se habilite a propósito. El hospital puede cruzar por `codigo_episodio` / `codigo_paciente`.
- Para exponer **datos reales** falta: conexión cifrada (HTTPS, por ejemplo con el túnel o un certificado del hospital), un token por sistema con permisos acotados y que se pueda revocar, y acordar con el hospital qué datos se comparten.
- Cada acceso queda en el log (ruta, IP y resultado), sin datos de pacientes.
