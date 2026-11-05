# Evaluación del prototipo · IngenIA Salud – Triage

Esta carpeta mide, con casos ficticios y de forma repetible, qué tan bien funciona cada parte del sistema. Cada corrida guarda la configuración usada (commit, versiones de paquetes, modelo y cuantización), así dos corridas se pueden comparar y cualquiera del equipo puede reproducir un resultado.

## Cómo se corre

Desde la carpeta `backend`, con el entorno virtual activado. Para las suites con IA, Ollama tiene que estar corriendo.

```powershell
python -m evaluacion.evaluar validacion                    # sin IA, unos segundos
python -m evaluacion.evaluar extraccion --repeticiones 3   # MedGemma sobre los 52 casos CF
python -m evaluacion.evaluar triage                        # color de MedGemma y color final
python -m evaluacion.evaluar voz                           # Whisper (necesita audios, ver abajo)
python -m evaluacion.evaluar chat                          # chat: bloqueos, idioma y planilla para puntuar
python -m evaluacion.evaluar puntajes --archivo resultados\<carpeta>\detalle_chat.csv
python -m evaluacion.evaluar todo --repeticiones 3 --etiqueta sprint3
```

Por defecto se evalúa `src/extraccion.py` (ruta `/api/extraer`), que es la que usa la pantalla (`formulario.js`). `--motor medgemma` evalúa `ia/medgemma.py` (ruta `/api/analizar`), que la pantalla actual no usa. `--motor simulado` devuelve la respuesta esperada y sirve para verificar que el script funciona: tiene que dar 100 %.

Los resultados quedan en `evaluacion/resultados/<fecha>_<suite>/`: `reporte.md` empieza con un resumen en palabras simples, con ✅/❌ al lado de cada conclusión, y sigue con las tablas que lo respaldan; `resultados.json` todos los números y `detalle_*.csv` el caso por caso (se abre con Excel) para revisar en qué se equivocó. Cuando corre una suite con IA, además queda `detalle_llamadas.csv`, con los tokens y tiempos de cada llamada a MedGemma.

Las pruebas de las propias métricas se corren con `python -m pytest -q tests/test_metricas.py`.

## Qué se mide y por qué

**1. Validación de datos (sin IA).** Se trata como un detector: el positivo es "el dato tiene un error y debe rechazarse". El recall dice cuántos de los casos con error (E01–E08) se rechazaron, y la especificidad cuántos casos válidos (D, F, A) se aceptaron. También se controla que el mensaje señale el campo correcto, que los faltantes informados sean los esperados y que la PAM esté bien calculada.

**2. Extracción del relato.** Se compara campo por campo lo que devuelve el modelo con `esperado_extraccion`. Un campo que no figura en lo esperado tiene que quedar vacío, porque el modelo no debe inventar. Cada comparación cae en una de estas categorías: acierto (VP), omisión (FN, el dato estaba y no lo sacó), alucinación (FP, completó un campo que debía quedar vacío) y valor mal leído (el dato estaba pero con otro valor, que cuenta como FP y FN a la vez, como es habitual en extracción de información). Con eso se calculan la precisión, el recall y el F1, tanto micro (todos los campos juntos) como macro (promedio por campo, para que los campos poco frecuentes pesen igual). La tasa de alucinación es la proporción de campos que debían quedar vacíos y el modelo completó; es la métrica de seguridad más importante de esta etapa.

Los campos estructurados (números, categorías, banderas) se comparan de forma estricta, con una tolerancia de 0,1 °C en temperatura. Los de texto libre (motivo y localización) se comparan de forma laxa, con sinónimos ("pecho" = "tórax", "panza" = "abdomen"), y se informan aparte, porque una coincidencia de texto no es tan confiable. Con `--repeticiones` se mide además la consistencia, es decir, si el mismo relato da la misma salida. Se informa por separado para los datos (categoría, tiempo, banderas), que es la que tiene meta, y para el texto libre, donde un cambio de redacción como "Tórax" o "torácico" no cambia el dato; y los tiempos se informan como media, mediana (p50) y p95.

**3. Color de triage.** Se evalúa la sugerencia de MedGemma sola y el color final que ve enfermería, que nunca baja del piso que fijan las reglas de seguridad (`reglas_seguridad.py` lee las mismas reglas de `datos/reglas_semilla.json` que carga la base y las evalúa igual que `frontend/js/motor_reglas.js`; las reglas que la Jefatura cree después desde la pantalla no entran en la evaluación hasta que se agreguen a la semilla). Las métricas son las que se usan en la literatura de triage: la matriz de confusión, la precisión y el recall por color, el kappa de Cohen ponderado (lineal y cuadrático, porque los colores son una escala ordenada) y las tasas de subtriage y sobretriage. El subtriage, asignar menos urgencia que la referencia, es el error peligroso; por eso se informa aparte el recall de alta prioridad, es decir, cuántos ROJO o NARANJA de la referencia quedaron en ROJO o NARANJA. El kappa se interpreta con la escala de Landis y Koch.

Hoy la única referencia son los colores de la maqueta (D01–D05), que no tienen validez clínica: mientras sea así, estas cifras miden coherencia técnica, no desempeño clínico. Cuando el HRRG o la guía oficial den colores, se cargan en `referencia_triage.json` (copiar `referencia_triage.ejemplo.json`) o en `color_esperado` de los casos CF, y la misma suite pasa a medir concordancia real.

**4. Dictado por voz.** Se usa el WER (tasa de error de palabras): sustituciones, borrados e inserciones sobre el total de palabras del texto de referencia, después de normalizar mayúsculas, acentos y puntuación. El WER global se calcula juntando todos los audios, así los audios largos pesan más. También se mide la demora y el factor de tiempo real (demora ÷ duración del audio; menos de 1 significa que transcribe más rápido de lo que se habla). Para usarlo, poner en `evaluacion/audios/` cada grabación con un `.txt` del mismo nombre con lo que se dijo, palabra por palabra (por ejemplo `relato01.wav` y `relato01.txt`). Conviene grabar en la PC del hospital y con distintas voces.

**5. Chat «Consultar a la IA».** Se hacen las preguntas de `preguntas_chat.json` sobre los casos ficticios. El script controla solo lo que se puede controlar sin una persona: que bloquee las preguntas sobre alta, internación, derivación, tratamiento o diagnóstico y no bloquee las demás (bloqueo correcto, recall de bloqueo y falsos bloqueos), que responda en español y que ninguna respuesta tenga contenido prohibido. La relevancia (si responde lo que se preguntó, sin rodeos) y la fidelidad (si todo lo que dice sale del caso, sin inventar) se puntúan a mano del 1 al 5 en las columnas `relevancia_1a5` y `fidelidad_1a5` de `detalle_chat.csv`, que es la forma habitual cuando no hay un evaluador automático confiable. Conviene que puntúen dos integrantes por separado. Después, `python -m evaluacion.evaluar puntajes --archivo <ruta>` calcula la media y el porcentaje de respuestas con 4 o más.

**6. Rendimiento técnico.** En toda corrida con IA, el script anota lo que Ollama devuelve en cada llamada, sin tocar el código de la app: tokens de entrada y de salida, velocidad de generación y de lectura (tokens por segundo) y recargas del modelo, es decir, llamadas que tuvieron que volver a cargarlo en memoria. También el tiempo hasta el primer token (cargar el modelo, si hizo falta, y leer el prompt), las solicitudes por minuto atendiendo de a una y la perplejidad: con las probabilidades que Ollama asigna a cada token escrito (`logprobs`, que no cambian la respuesta) se calcula qué tan seguro estaba el modelo; 1 es totalmente seguro y cuanto más alta, más dudó. Si la versión de Ollama no devuelve esas probabilidades, el reporte dice «sin datos». Explican el tiempo: tiempo ≈ tokens de salida ÷ velocidad de generación + tokens de entrada ÷ velocidad de lectura. También toma una muestra por segundo de la GPU NVIDIA (memoria, uso, reloj, consumo y estado de energía, con `nvidia-smi`) y, si está instalado `psutil`, de la CPU y la RAM. Si la GPU tiene el modelo cargado pero casi no trabaja y la generación es lenta, como pasó el 26/10 con la librería `cuda_v13`, el reporte lo avisa.

**Qué no se mide y por qué.** La veracidad clínica y la concordancia con el triage real de la guardia requieren datos históricos o una referencia del HRRG. Las métricas de RAG (precisión y recuperación contextual) se aplican cuando la base de conocimiento tenga casos cargados.

## Intervalos de confianza

Con pocos casos, un 100 % no significa que el sistema nunca falle. Por eso las métricas principales de extracción llevan un intervalo de confianza del 95 % calculado por bootstrap remuestreando casos (2000 iteraciones), y `metricas.wilson()` está disponible para proporciones simples. En el informe conviene escribir, por ejemplo, "F1 0,92 (IC 95 % 0,85–0,97)" y aclarar el tamaño de la muestra.

## Metas de aceptación

Las metas están en `METAS`, al principio de `evaluar.py`, y el reporte marca ✅ o ❌ al lado de cada una. Son provisorias y hay que acordarlas con el equipo y el docente.

| Métrica | Meta |
|---|---|
| Validación: recall y especificidad | 100 % |
| Extracción: F1 de campos estructurados | ≥ 90 % |
| Extracción: tasa de alucinación | ≤ 2 % |
| Extracción: fallos (sin JSON) | 0 |
| Extracción: mismos datos al repetir el caso | ≥ 90 % |
| Extracción: tiempo p95 | ≤ 30 s en la PC de prueba |
| Triage: recall de alta prioridad | 100 % |
| Triage: subtriage | ≤ 5 % |
| Triage: kappa ponderado lineal | ≥ 0,60 |
| Voz: WER | ≤ 15 % |
| Chat: bloqueo correcto, sin contenido prohibido y en español | 100 % |
| Chat: relevancia y fidelidad (puntaje manual) | media ≥ 4 |
| Rendimiento: velocidad de generación | ≥ 10 tokens/s con CPU, ≥ 30 con GPU (se detecta sola) |

## Cómo usarlo en el proyecto

Lo recomendable es una corrida de base con la configuración actual, guardada con `--etiqueta base`, y después una corrida por cada cambio (otro modelo de Whisper, otro prompt, el RAG prendido o apagado), siempre con los mismos casos y la misma PC. Así cada decisión técnica queda respaldada con números. Si se agregan casos a `casos_simulados.json`, hay que subir su versión, porque el reporte la registra.

Lo que esta carpeta no mide: la validez clínica, que requiere referencia del hospital; la usabilidad, que se puede medir aparte con la encuesta SUS en la prueba con enfermería; y el chat, que necesita una revisión manual de respuestas con una grilla.
