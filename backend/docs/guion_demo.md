# Guion de la demo simulada — Triage asistido HRRG

Casos: `backend/datos/casos_simulados.json` (FICTICIOS, sin datos reales, sin guía oficial).
El color que muestra la maqueta (`nivel_maqueta`) es de demostración: **no tiene validez clínica**.
Duración estimada: 6–8 minutos.

| # | Pantalla | Quién | Acción | Caso | Qué mostrar |
|---|---|---|---|---|---|
| 1 | Login | Enfermería | Ingresar con usuario `enfermeria` | — | Usuario individual: cada decisión queda firmada |
| 2 | Ingreso | Enfermería | Pegar o dictar el relato y extraer | D02 | La IA completa campos; lo que no se dijo queda vacío (faltante) |
| 3 | Ingreso | Enfermería | Escribir un nombre en el motivo | E03 | Aviso de dato personal (Ley 25.326): no deja seguir |
| 4 | Medición | Enfermería | "Demo: completar con valores" | D02 | PAM calculada; coma decimal (37,8) aceptada |
| 5 | Medición | Enfermería | Tipear SpO₂ 8 | E01 | Error de tipeo detectado antes de la IA |
| 6 | Sugerencia | Enfermería | Ver la tarjeta de color | D02 | Color + justificación + fuente; "requiere validación humana" |
| 7 | Sugerencia | Enfermería | Modificar el color sin motivo | — | Pide motivo obligatorio; nunca se baja en silencio |
| 8 | Espera | Enfermería | Ver la lista | D01–D04 | Orden por prioridad y reloj de tiempo objetivo |
| 9 | Espera | Enfermería | Reevaluar → "Demo: empeoró" | D05 | Alertas fijas suben el color (regla asimétrica) |
| 10 | Sugerencia | — | Apagar Ollama y pedir sugerencia | D01 | Modo sin IA: alertas fijas + "clasificar manualmente" |
| 11 | Login | Auditor | Ingresar con `auditor` | — | Solo lectura del registro (trazabilidad) |

## Antes de empezar
- `python -m pytest -q` en verde.
- Ollama encendido con el modelo cargado (`ollama run medgemma1.5` una vez, para que no tarde la primera consulta).
- Navegador en pantalla completa; sin datos reales en ningún campo.
