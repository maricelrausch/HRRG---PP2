# Evaluación del prototipo · IngenIA Salud – Triage

Esta carpeta mide, con casos ficticios y de forma repetible, qué tan bien funciona cada parte del sistema. Cada corrida guarda la configuración usada (commit, versiones de paquetes, modelo y cuantización), así dos corridas se pueden comparar y cualquiera del equipo puede reproducir un resultado.

## Cómo se corre

Desde la carpeta `backend`, con el entorno virtual activado. Para las suites con IA, Ollama tiene que estar corriendo.

```powershell
python -m evaluacion.evaluar validacion                    # sin IA, unos segundos
python -m evaluacion.evaluar extraccion --repeticiones 3   # MedGemma sobre los 12 casos CF
python -m evaluacion.evaluar triage                        # color de MedGemma y color final
python -m evaluacion.evaluar voz                           # Whisper (necesita audios, ver abajo)
python -m evaluacion.evaluar todo --repeticiones 3 --etiqueta sprint3
```

Por defecto se evalúa `src/extraccion.py` (ruta `/api/extraer`), que es la que usa la pantalla (`formulario.js`). `--motor medgemma` evalúa `ia/medgemma.py` (ruta `/api/analizar`), que la pantalla actual no usa. `--motor simulado` devuelve la respuesta esperada y sirve para verificar que el script funciona: tiene que dar 100 %.

Los resultados quedan en `evaluacion/resultados/<fecha>_<suite>/`: `reporte.md` tiene las tablas para el informe, `resultados.json` todos los números y `detalle_*.csv` el caso por caso (se abre con Excel) para revisar en qué se equivocó.

Las pruebas de las propias métricas se corren con `python -m pytest -q tests/test_metricas.py`.

## Qué se mide y por qué

**1. Validación de datos (sin IA).** Se trata como un detector: el positivo es "el dato tiene un error y debe rechazarse". El recall dice cuántos de los casos con error (E01–E08) se rechazaron, y la especificidad cuántos casos válidos (D, F, A) se aceptaron. También se controla que el mensaje señale el campo correcto, que los faltantes informados sean los esperados y que la PAM esté bien calculada.

**2. Extracción del relato.** Se compara campo por campo lo que devuelve el modelo con `esperado_extraccion`. Un campo que no figura en lo esperado tiene que quedar vacío, porque el modelo no debe inventar. Cada comparación cae en una de estas categorías: acierto (VP), omisión (FN, el dato estaba y no lo sacó), alucinación (FP, completó un campo que debía quedar vacío) y valor mal leído (el dato estaba pero con otro valor, que cuenta como FP y FN a la vez, como es habitual en extracción de información). Con eso se calculan la precisión, el recall y el F1, tanto micro (todos los campos juntos) como macro (promedio por campo, para que los campos poco frecuentes pesen igual). La tasa de alucinación es la proporción de campos que debían quedar vacíos y el modelo completó; es la métrica de seguridad más importante de esta etapa.

Los campos estructurados (números, categorías, banderas) se comparan de forma estricta, con una tolerancia de 0,1 °C en temperatura. Los de texto libre (motivo y localización) se comparan de forma laxa, con sinónimos ("pecho" = "tórax", "panza" = "abdomen"), y se informan aparte, porque una coincidencia de texto no es tan confiable. Con `--repeticiones` se mide además la consistencia, es decir, si el mismo relato da la misma salida, y los tiempos se informan como media, mediana (p50) y p95.

**3. Color de triage.** Se evalúa la sugerencia de MedGemma sola y el color final que ve enfermería, que nunca baja del piso que fijan las reglas de seguridad (`reglas_seguridad.py` es una copia en Python de `reglas()` de `frontend/sugerencia.js`; si se cambian los umbrales allá, hay que cambiarlos acá). Las métricas son las que se usan en la literatura de triage: la matriz de confusión, la precisión y el recall por color, el kappa de Cohen ponderado (lineal y cuadrático, porque los colores son una escala ordenada) y las tasas de subtriage y sobretriage. El subtriage, asignar menos urgencia que la referencia, es el error peligroso; por eso se informa aparte el recall de alta prioridad, es decir, cuántos ROJO o NARANJA de la referencia quedaron en ROJO o NARANJA. El kappa se interpreta con la escala de Landis y Koch.

Hoy la única referencia son los colores de la maqueta (D01–D05), que no tienen validez clínica: mientras sea así, estas cifras miden coherencia técnica, no desempeño clínico. Cuando el HRRG o la guía oficial den colores, se cargan en `referencia_triage.json` (copiar `referencia_triage.ejemplo.json`) o en `color_esperado` de los casos CF, y la misma suite pasa a medir concordancia real.

**4. Dictado por voz.** Se usa el WER (tasa de error de palabras): sustituciones, borrados e inserciones sobre el total de palabras del texto de referencia, después de normalizar mayúsculas, acentos y puntuación. El WER global se calcula juntando todos los audios, así los audios largos pesan más. También se mide la demora y el factor de tiempo real (demora ÷ duración del audio; menos de 1 significa que transcribe más rápido de lo que se habla). Para usarlo, poner en `evaluacion/audios/` cada grabación con un `.txt` del mismo nombre con lo que se dijo, palabra por palabra (por ejemplo `relato01.wav` y `relato01.txt`). Conviene grabar en la PC del hospital y con distintas voces.

## Intervalos de confianza

Con 12 casos, un 100 % no significa que el sistema nunca falle. Por eso las métricas principales de extracción llevan un intervalo de confianza del 95 % calculado por bootstrap remuestreando casos (2000 iteraciones), y `metricas.wilson()` está disponible para proporciones simples. En el informe conviene escribir, por ejemplo, "F1 0,92 (IC 95 % 0,85–0,97)" y aclarar el tamaño de la muestra.

## Metas de aceptación

Las metas están en `METAS`, al principio de `evaluar.py`, y el reporte marca ✅ o ❌ al lado de cada una. Son provisorias y hay que acordarlas con el equipo y el docente.

| Métrica | Meta |
|---|---|
| Validación: recall y especificidad | 100 % |
| Extracción: F1 de campos estructurados | ≥ 90 % |
| Extracción: tasa de alucinación | ≤ 2 % |
| Extracción: fallos (sin JSON) | 0 |
| Extracción: consistencia entre repeticiones | ≥ 90 % |
| Extracción: tiempo p95 | ≤ 30 s en la PC de prueba |
| Triage: recall de alta prioridad | 100 % |
| Triage: subtriage | ≤ 5 % |
| Triage: kappa ponderado lineal | ≥ 0,60 |
| Voz: WER | ≤ 15 % |

## Cómo usarlo en el proyecto

Lo recomendable es una corrida de base con la configuración actual, guardada con `--etiqueta base`, y después una corrida por cada cambio (otro modelo de Whisper, otro prompt, el RAG prendido o apagado), siempre con los mismos casos y la misma PC. Así cada decisión técnica queda respaldada con números. Si se agregan casos a `casos_simulados.json`, hay que subir su versión, porque el reporte la registra.

Lo que esta carpeta no mide: la validez clínica, que requiere referencia del hospital; la usabilidad, que se puede medir aparte con la encuesta SUS en la prueba con enfermería; y el chat, que necesita una revisión manual de respuestas con una grilla.
