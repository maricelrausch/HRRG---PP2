# Frontend · Qué se hizo y qué falta para conectarlo

**Responsable:** Bárbara (frontend/) · **Creado:** 12/10/2026 · **Última actualización:** 21/10/2026 · **Base:** maquetado v34
**Estado general:** el login (A07), "Extraer datos" (A06) y el **guardado del caso** (episodio, mediciones, correcciones e historial) ya funcionan contra Flask. La extracción usa casos simulados (D01–D05) o MedGemma (`HRRG_MODO_EXTRACCION=ia`); la sugerencia de color, el chat y el dictado siguen **simulados**.

---

## 1. Qué se hizo

| Tarea | Archivo | Qué cambió |
|---|---|---|
| A01 · Montar el flujo | `frontend/formulario.html` | El v34 pasa a ser el formulario del proyecto. (El formulario anterior y su `formulario.js` se borraron del repo; quedan en el historial de git, commit `2b07c63`.) |
| A02 · Login simulado | `frontend/index.html` + `frontend/login.js` | El login salió del maquetado a su propia página. Usuarios de demo: `enfermeria`, `medico`, `auditor` (clave `demo`). Guarda el usuario en `sessionStorage` y pasa a `formulario.html`. Si alguien abre el formulario sin pasar por el login, lo devuelve al login. "Salir" borra la sesión. |
| A03 · Rotular simulaciones | `frontend/formulario.html` | Cartel amarillo fijo en todas las pantallas ("Datos ficticios · Simulación"). Se sacaron las atribuciones a MedGemma y a la guía del HRRG: ahora dice "Prioridad de ejemplo · simulada", "guía de ejemplo, no oficial", "Modelo: SIMULADO", "IA: simulada". |
| A04 · Guion de la demo | `docs/guion_demo.md` | Recorrido de 5 a 7 minutos, qué decir en cada pantalla y preguntas probables. |
| **Nuevo** · Asistente IA | `frontend/formulario.html` | En la pantalla **Sugerencia** hay un botón con un robot ("Consultar a la IA") que abre un chat. Ver punto 2. |

**Cómo probarlo:** abrir `frontend/index.html` con doble clic. No necesita servidor, ni internet, ni Ollama.

---

## 2. Asistente IA (chat sobre la sugerencia)

**Para qué sirve:** que el profesional pueda preguntar sobre la sugerencia de ese episodio, por texto o por voz, las veces que necesite. Por ejemplo: por qué ese color, qué datos faltan, qué lo haría subir o de qué guía sale.

**Qué hace hoy (simulado):**

- Las respuestas se arman en el navegador con los datos del caso (función `respuestaSimulada()`): color, motivos, datos faltantes y discriminadores de la guía de ejemplo.
- Si preguntan por diagnóstico, medicación o tratamiento, **no responde** y deriva al médico.
- Cada respuesta termina con "Simulación. La decisión es del profesional."
- Al cambiar de episodio, la conversación arranca de cero.

> **Importante:** el chat **no estaba en el V2.1**. En Trello se registra como un ítem más del checklist de **A03** (la versión simulada y rotulada) y su conexión real queda dentro de **A09**. Falta acordar la ruta en el contrato de la API.

### Qué falta para conectarlo

En `formulario.html` está todo preparado. Solo hay que cambiar **una línea**:

```js
const CHAT_API = null;              // hoy: simulado
const CHAT_API = '/api/consulta';   // cuando exista la ruta
```

Con eso, el chat deja de usar las respuestas simuladas y llama al backend.

| Quién | Qué tiene que hacer |
|---|---|
| **Maricel** (app.py) | Publicar `POST /api/consulta` con sesión obligatoria (401 si no hay usuario) y documentarla en `docs/contrato_api.md`. |
| **Tomás** (src/rag.py) | Función que reciba la pregunta + el contexto del caso y devuelva una respuesta basada en la guía (RAG, tarea B06). No debe diagnosticar ni indicar tratamientos. |
| **Darío** | Sumar al esquema los modelos de entrada y salida de la consulta, y casos de prueba (incluida una pregunta prohibida). |
| **Bárbara** | Cambiar `CHAT_API`, mostrar los errores 401/503/504 y probar con el backend. |

**Contrato propuesto** (para discutir y pasar a `docs/contrato_api.md`):

```
POST /api/consulta
Entrada:  { "pregunta": "¿Por qué amarillo?", "episodio": "EP-004812",
            "datos": { ...datos revisados... }, "sugerencia": "AMARILLO" }
Salida:   { "respuesta": "texto", "fuentes": ["Guía ..., diagrama ..., pág. ..."] }
Errores:  401 sin sesión · 422 pregunta vacía · 503 IA no disponible · 504 tiempo agotado
```

---

## 3. La voz: por qué "no funciona" y cómo hacer que funcione

### Por qué no funciona

**No es un error del código: la voz está simulada a propósito.** Hay dos lugares con micrófono:

- **Dictado del Ingreso:** al tocar "Dictar", espera 1,8 segundos y agrega una frase fija ("Esta mañana vomité una vez.").
- **Micrófono del chat:** espera 1,5 segundos y manda la pregunta "¿Qué datos faltan?".

Ninguno de los dos usa el micrófono real. Se hizo así porque la opción más fácil para tener voz real tiene problemas para este proyecto:

1. **Privacidad.** El reconocimiento de voz que trae el navegador (Web Speech API) **manda el audio a servidores de Google**. Eso choca con la regla de que los datos no salen de la computadora.
2. **Compatibilidad.** Solo anda en Chrome y Edge, y necesita internet.
3. **Permisos.** Si el archivo se abre con doble clic (`file://`), el navegador suele bloquear el micrófono. Necesita servirse desde `http://localhost` (por ejemplo, desde Flask).

### Cómo hacer que funcione

**Opción A · Para una demo con casos ficticios (rápida)**

- **Chat:** en `formulario.html` cambiar `const USAR_VOZ_REAL = false;` a `true`. Ya está programado.
- **Dictado del Ingreso:** reemplazar el bloque del botón `#mic` por la versión con `webkitSpeechRecognition` (la pide Bárbara cuando se decida).
- Abrir la app desde `http://localhost`, no con doble clic, y aceptar el permiso del micrófono.
- Avisar en pantalla: *"El dictado usa el reconocimiento de voz del navegador (Google): solo casos ficticios."*

**Opción B · Para el sistema real (voz 100 % local)**

Usar **Whisper** corriendo en la misma computadora, igual que Ollama:

1. **Tomás:** instalar `faster-whisper` y crear en `backend/src/voz.py` la función `transcribir(audio) -> texto`.
2. **Maricel:** publicar `POST /api/transcribir` en `app.py`, que recibe el audio y devuelve `{ "texto": "..." }`. Las dependencias van a `requirements.txt`.
3. **Bárbara:** grabar con `MediaRecorder` (está en el navegador, no manda nada afuera), enviar el audio a `/api/transcribir` y poner el texto en el relato o en el chat.

Así el audio nunca sale de la computadora del box.

---

## 4. Validaciones del formulario (`frontend/validacion.js`) · 14/10

Se actualizó según `backend/docs/controles_validacion.md` (C04 de Darío). Ahora usa los **nombres del diccionario V2** y los mismos controles que `backend/src/validacion.py`:

- Números con coma o punto, enteros y rangos de plausibilidad (edad hasta 120; se suman `glucemia` y `tiempo_evolucion_valor`).
- Opciones cerradas: `sexo` (Femenino / Masculino / No informado), `motivo_categoria`, `tiempo_evolucion_unidad`, `estado_conciencia`.
- Banderas rojas `br_*` y antecedentes `ant_*` como sí/no.
- Diastólica menor que sistólica, y PAM calculada.
- Privacidad con los mismos patrones del backend en todos los textos libres (incluidos `sintomas_asociados`, `dolor_caracteristicas`, `aspecto_general`, `alergias`).
- Formato de `codigo_paciente` y `codigo_episodio` (ej. `PAC-DEMO-001`).
- Faltantes **por etapa** (`ingreso` / `medicion`): se informan, no bloquean. Glasgow y los códigos no son obligatorios.
- Acepta nombres viejos (`tas`, `saturacion`, `sexo: 'F'`, `banderas_rojas: [...]`) y los traduce, igual que el backend.

**Uso:** `TriageDatos.validate(datos, 'ingreso')` → `{ valid, errors, missing, data }`.

**Pruebas:** `node frontend/tests/validacion.test.js` (14 pruebas). Además se comparó contra `validar()` del backend con los 17 casos de `casos_simulados.json`: coinciden 16. La diferencia es el caso E05 (campo desconocido), que por diseño se controla solo en el backend (control 7).

**Hecho (A05, 14/10):** `formulario.html` ya usa este archivo para controlar los campos (se carga antes de `formulario.js`).

## 5. Pendientes del frontend

| # | Pendiente | Depende de | Tarea |
|---|---|---|---|
| 1 | ~~Login real (`/api/login`, `/api/sesion`, `/api/logout`)~~ ✅ Hecho 14/10: `api.js` + `login.js`. Desde Flask (`http://127.0.0.1:5000/index.html`) usa el login real; con doble clic sigue el modo demo | D04 · Maricel | A07 |
| 2 | ~~Separar HTML, CSS y JS del formulario~~ ✅ Hecho 14/10: `estilos.css` + `formulario.js` + `validacion.js` | A04 + C01 · Darío | A05 |
| 3 | ~~"Extraer datos" contra la API (primero con JSON simulado)~~ ✅ Hecho 16/10: Maricel conectó `formulario.js` a `/api/extraer`; probado por Bárbara (caso D02 completa la revisión; un texto desconocido avisa y conserva el relato) | D03 · Maricel + contrato D02 | A06 |
| 4 | ~~Revisión y resumen con datos reales~~ ✅ Hecho 16/10 (con la extracción simulada; con MedGemma cuando cierre D05): cada dato muestra su origen (extraído · corregido · completado · cargado · medido · falta), el relato original queda fijo, los obligatorios salen de `validacion.js` y el registro cuenta extraídos/corregidos/completados/medidos/faltantes | A06 + C03/C04 + D05/D06 | A08 |
| 5 | Conectar el chat (`CHAT_API`) | `/api/consulta` · Maricel + RAG · Tomás | A11 (nueva) |
| 6 | Voz real (opción A o B) | Decisión del equipo; opción B: Tomás + Maricel | A11 / A06 |
| 7 | Tarjeta de sugerencia con datos reales | Guías autorizadas por el HRRG | A09 ⏸ |
| 8 | ~~Espera y reevaluación persistidas~~ ✅ Hecho 20/10: al registrar la decisión el episodio pasa a **en espera** en el servidor; la lista "En espera" se lee de `/api/demo/espera` (no se pierde al recargar y la ven todos los usuarios); botón **Finalizar (atendido)** con confirmación; el auditor solo mira. Al reevaluar un episodio de otra sesión se recuperan sus últimos signos vitales. El color de la lista viene de la última decisión guardada (ver punto 13) | Rutas de estado y espera · Maricel | A10 |
| 9 | ~~Guardar el caso en el servidor~~ ✅ Hecho 18/10: al extraer se crea el episodio (código `EPI-…` del servidor); al pedir sugerencia se registra la **medición**; si después se cambian valores se registra una **corrección** (la original no se pisa); reevaluar desde En espera registra una **medición nueva**. El historial se ve en "Ver datos del caso". Sin servidor (doble clic) no se guarda nada | Rutas de episodios · Maricel | A10 |
| 10 | ~~Cartel según el modo~~ ✅ Hecho 18/10: el cartel amarillo usa `modo_extraccion` de `/api/sesion` desde el inicio ("Simulación" o "Extracción con IA local") | `/api/sesion` · Maricel | A03 |
| 12 | ~~Botón imprimir~~ ✅ Hecho 20/10: "Imprimir / PDF" en la pantalla de resultado; imprime solo el resumen (datos, correcciones, historial y registro) con encabezado de datos ficticios. Desde el diálogo se elige "Guardar como PDF". Si Tomi arma un PDF desde el servidor, el botón se puede apuntar a esa ruta | Pedido de Tomi | — |
| 13 | ~~Guardar la **decisión** en el servidor~~ ✅ Hecho 21/10 (`POST …/decision`): Aceptar → *aceptada*; Modificar → *modificada* + motivo; Rechazar → *modificada* con motivo "Sugerencia rechazada…" (el backend usa *rechazada* solo sin color); Clasificar sin IA → *modificada* "Clasificación manual sin asistencia IA"; Escalar a ROJO → *modificada* ROJO. Se ve en el historial y la lista de espera muestra el color en todas las compus. **Pendiente:** guardar edad/sexo y la extracción | Ruta · Maricel | A10 |
| 14 | ~~DNI del paciente (pedido del HRRG en la visita)~~ ✅ Hecho 20–21/10: campo opcional en Ingreso (valida 7 u 8 dígitos). Con servidor sigue el circuito de Maricel: `POST /api/demo/pacientes/identificar` → `codigo_paciente` → se crea el episodio con ese código → `GET /api/demo/episodios?codigo_paciente=` para **atenciones anteriores**, que se ven en "Ver datos del caso" con su historial. **El DNI solo viaja a la ruta de identificación: nunca a la IA ni a `/api/extraer`**. Sin DNI se usa un código provisorio | Ruta · Maricel | A10 |
| 15 | Buscar en **En espera** por código de episodio **o DNI** ✅ 21–22/10. Solo números = búsqueda por DNI (acepta con puntos). Con el DNI completo (7 u 8 dígitos) consulta `POST /api/demo/pacientes/buscar` (Maricel), que **no crea pacientes**, y encuentra los episodios de ese paciente cargados desde **cualquier compu**; también lo puede usar el auditor. El DNI va en el cuerpo del pedido, nunca en la URL ni a la IA. Mensajes: no existe / identificado sin episodios en espera / error. Con DNI parcial solo filtra lo de esta pestaña | ✅ Ruta de Maricel | A10 |
| 16 | "Por qué" de la sugerencia ✅ 22/10: ahora arranca siempre con el **motivo** (categoría + lo que dijo el paciente + tiempo), p. ej. *Motivo: Cefalea — migraña*. Antes solo se veía la categoría si el dolor era 5–7/10, y un relato como "migraña, vómitos" mostraba solo *Refiere: vómitos*. Sigue siendo la simulación con reglas de ejemplo hasta tener las guías del HRRG (A09) | — | A09 |
| 17 | Sacar de la pantalla de sugerencia (acuerdo reunión 21/10) ✅ 22/10: la línea de origen ("Color fijado por regla de seguridad…" / "Simulación con reglas de ejemplo"), la **Fuente** con la guía de ejemplo, el texto "IA · Entendió del relato…" y el aviso "4 · Herramienta de apoyo…". Se **ocultaron** (atributo `hidden`), no se borraron: la lógica y el chat siguen igual y se pueden volver a mostrar. La corrección de los datos del relato quedó como **"4 · Corregir datos del relato"** | Reunión 21/10 | A09 |
| 18 | Carteles del modo IA ✅ 22/10: el chip "IA: simulada" ahora dice **"IA: MedGemma local"** cuando el servidor está en modo IA (antes quedaba fijo hasta la primera extracción). Se sacó "/ Simulación" del encabezado y se corrigió el texto del login real (decía que la extracción seguía simulada). "Datos ficticios" queda siempre: es el aviso de privacidad | — | A10 |
| 19 | **Escalar a ROJO** desde En espera con **motivo obligatorio** ✅ 22/10: al tocar "Escalar a ROJO" se abre un formulario en la fila (motivo de una lista + detalle opcional, obligatorio si es "Otro"). El motivo se guarda en la decisión (`Escalado manual por deterioro en espera: <motivo>. <detalle>.`), se ve en el historial y en la fila de todas las compus. Antes se registraba siempre el mismo texto fijo. Especificaciones (punto 4 de En espera) actualizadas el 23/10 | Pedido de Barby | A10 |
| 20 | Aviso del chat "Consultar a la IA" ✅ 22/10: con servidor decía "Simulación. Respuestas de ejemplo, no de MedGemma" aunque el chat ya consulta a MedGemma local (`js/chat_ia.js` → `/api/ia/consulta`). Ahora dice "MedGemma local…". Sin servidor (doble clic) sigue el aviso de simulación | — | A10 |
| 21 | Textos de la pantalla de Ingreso (pedido 22/10) ✅ 23/10: el campo pasa a llamarse **"DNI"** (sin "opcional · para vincular…"), se sacó la explicación de abajo del DNI y la línea "3 · Si algo falla…". El aviso "Caso ficticio" quedó corto, al lado de "Descripción del evento". La lógica no cambia: el DNI sigue sin ir a la IA y el control de datos personales en el relato sigue activo | Pedido del grupo | A10 |
| 22 | **Organización del código** (A09/A10, con OK de Darío) ✅ 23/10: `formulario.js` se separó en tres archivos sin cambiar lo que se ve: `formulario.js` (lo común: datos, navegación, Ingreso, Medición, guardado, resumen, sesión, imprimir, DNI), **`sugerencia.js`** (tarjeta de color simulado, Por qué, decisión y su guardado, chat) y **`espera.js`** (lista, búsqueda, reevaluar, escalar, finalizar). Orden de carga: formulario → sugerencia → espera → dictado → chat_ia. La sesión arranca en `DOMContentLoaded`, cuando ya están los tres | Darío OK | A09 · A10 |
| 23 | **Sin respaldo del color en la pestaña** (A10) ✅ 23/10: se sacó el `sessionStorage` (`hrrg_espera_colores`). El color de En espera sale solo de la decisión guardada en el servidor. Si no se pudo guardar, la fila lo avisa y al recargar queda "Sin color" (antes podía mostrar un color que el servidor no tenía). El motivo/categoría de filas que vienen del servidor se ve "—" hasta que Maricel guarde la extracción | — | A10 |
| 24 | **Backend: datos de ingreso y DNI en espera** (parte de Maricel, hecha por Barby mientras ella está de viaje; a revisar) ✅ 23/10: ruta nueva `POST …/datos-ingreso` (edad, sexo y lo extraído del relato, validado con los esquemas; nunca el relato ni el DNI) y `GET /api/demo/espera` devuelve `motivo_categoria` y, solo a enfermería y médicos, el `dni`. Frontend: guarda los datos al confirmar la medición; la lista muestra motivo y DNI después de recargar y en otras compus; reevaluar desde otra compu trae edad, sexo y motivo; el historial muestra "Datos de ingreso registrados". Detalle en `contrato_api.md` §14 | Revisar · Maricel | A10 · D10 |
| 25 | **Auditor: DNI e historial completo** (acordado en el grupo 23/10) ✅ 23/10: el auditor ve el DNI en En espera; cada fila tiene **"Ver historial"** (solo lectura: datos de ingreso, mediciones, correcciones, decisiones con motivo, escalados, cambios de estado y otras atenciones del paciente); buscando un DNI completo ve **todas las atenciones del paciente, incluidas las finalizadas**, cada una con su historial. Sin botones de escritura. El historial se arma igual en todas las pantallas (`htmlEventos`). Backend: el auditor se suma a los roles que reciben `dni` en `/api/demo/espera` | Grupo | A10 |
| 26 | **Explicación clínica y discriminadores** (preguntas de Darío, 23/10) ✅: (1) el "Por qué" agrupa las reglas en frases que dicen qué indican: respiratorio (SpO₂ + FR + disnea → "posible compromiso respiratorio"), circulatorio (sangrado/hipotensión/FC → "posible shock"), neurológico (convulsión, Glasgow, conciencia). Mismos umbrales y niveles: solo cambia la explicación. (2) Los Sí/No de "Pasaría a…" ahora se guardan en la decisión del servidor ("Discriminadores confirmados: … Descartados: …"), se ven en el historial y los ve el auditor. Antes quedaban solo en el registro de la pantalla | Darío | A09 |
| 11 | Que un error de IA **no vuelva solo a la simulación** (revisar `frontend/js/medgemma.js` y `dictado.js` de Darío antes de activarlos: hoy no están cargados) | Acordar con Darío | A08 |

**Reglas que se mantienen:** solo casos ficticios; nada se atribuye a MedGemma ni al HRRG mientras sea simulación; la decisión final es siempre del profesional.
