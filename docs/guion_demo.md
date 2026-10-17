# Guion de la demo · Sprint 2 (v2, con servidor)

**Duración:** 6 a 8 minutos · **Actualizado:** 16/10/2026 · **Rama:** `barby`
**Qué cambió desde la v1:** el login es real (Flask), "Extraer datos" llama a `/api/extraer` y la revisión muestra el origen de cada dato (A06, A07, A08).
**Sigue simulado:** la extracción usa casos predefinidos (D01–D05), la sugerencia de color usa reglas de ejemplo y el chat responde en el navegador. **No es MedGemma ni la guía del HRRG.**

---

## Antes (el día anterior)

- [ ] `git pull origin barby` y probar el recorrido completo una vez.
- [ ] Tener las cuentas creadas con su perfil (clave de 12 caracteres o más):

```powershell
cd backend
python -m flask --app app crear-profesional --usuario auditor --nombre "Auditoría" --password "<clave>"
python -m flask --app app asignar-rol --usuario auditor --rol auditor
```

(La cuenta `enfermeria` ya existe y tiene perfil.)

- [ ] Tener a mano los relatos exactos (copiar y pegar, la simulación compara el texto tal cual):
  - **D01:** `Me duele el pecho desde hace media hora, como una presión, y estoy sudando.`
  - **D02:** ya viene escrito en el formulario.

## Antes (en el momento)

- [ ] Terminal en `HRRG---PP2\backend` → `python app.py` → esperar `Running on http://127.0.0.1:5000`. **No cerrar esa terminal.**
- [ ] Abrir **http://127.0.0.1:5000/** y apretar **Ctrl+F5**.
- [ ] Navegador en pantalla completa. Ningún dato real en ningún campo.
- [ ] **Plan B** si el servidor no arranca: abrir `frontend/index.html` con doble clic (modo demo, usuario `enfermeria` / clave `demo`). El recorrido es el mismo, pero sin servidor.

---

## Recorrido

| Min | Pantalla | Qué se hace | Qué se dice |
|---|---|---|---|
| 0–1 | **Login** | Probar una clave mala → error. Entrar con `enfermeria` y la clave real | "El acceso es real: cada profesional tiene su usuario y su perfil (enfermería, médico, auditor). Lo controla el servidor, no el navegador." |
| 1–2 | **Ingreso · privacidad** | Agregar al relato *"mi DNI es 30123456"* → Extraer | "Antes de mandar nada, se bloquea cualquier dato personal (Ley 25.326)." Después borrar la frase a mano. |
| 2–3 | **Ingreso · texto desconocido** | Escribir *"me duele la cabeza"* → Extraer | "Hoy el servidor solo reconoce los casos de prueba. Si no lo conoce, avisa y **el texto no se pierde**." |
| 3–4 | **Ingreso · caso D02** | Volver a pegar el relato D02 → **Extraer datos** | "El servidor devuelve los datos del relato. El cartel dice que es una **extracción simulada**: no se presenta como IA." |
| 4–5 | **Revisión** | Mostrar las etiquetas (*simulado*, *falta*). Cargar edad y sexo (*cargado*). Cambiar "Desde hace" de 6 a 5 (*corregido*). **Cargar vitales de ejemplo** (*medido*) | "Cada dato dice de dónde salió. Lo que no se dijo queda **vacío, nunca en cero**. El relato original queda fijo arriba." |
| 5 | **Revisión · error de tipeo** | Escribir SpO₂ **8** → mostrar el aviso y el botón bloqueado → corregir a 97 | "Los controles son los mismos que valida el backend (Darío). Un error de tipeo no llega a la sugerencia." |
| 5–6 | **Sugerencia** | Mostrar color, justificación y "guía de ejemplo, no oficial". Tocar **Modificar** → pide motivo. Después **Aceptar** | "La decisión es siempre del profesional. Si cambia el color, tiene que dejar el motivo." |
| 6–7 | **Resumen y registro** | Abrir **"Ver datos del caso, correcciones y registro"** | "El resumen muestra el origen de cada dato: extraído, corregido, completado, medido. El registro trae fecha, usuario, qué extracción se usó y el conteo." |
| 7 | **Sin extracción** | En el encabezado, tocar el indicador de extracción → pasa a **"Continuar sin extracción"** | "Si la IA no está disponible, se sigue con el triage manual. No se pierde nada." |
| 7–8 | **Auditor** | **Salir** → entrar con `auditor` | "El auditor entra directo a la lista: solo consulta, no carga ni decide." |
| Cierre | — | **Salir** | Próximos pasos (abajo). |

---

## Preguntas probables

- **¿Ya usa MedGemma?** Todavía no en la demo. El backend ya tiene preparado el modo IA (Tomás + Maricel, D05). Cuando se active, el frontend no cambia: la etiqueta pasa de *simulado* a *IA*.
- **¿El color es de la guía Manchester del hospital?** No. Son reglas de ejemplo. No se activan colores reales sin las guías autorizadas por el HRRG.
- **¿Se guardan los datos?** La sesión y el usuario, sí (servidor local). El backend ya puede guardar episodios, mediciones y correcciones con su autor, pero la pantalla todavía no los envía. Eso es lo próximo.
- **¿Qué pasa con un relato real?** No se usan relatos reales. Solo casos ficticios.
- **¿Por qué el dictado por voz no es real?** El reconocimiento del navegador manda el audio a servidores externos. La opción segura es Whisper local (ver `docs/frontend_cambios.md`, punto 3).

## Próximos pasos (para el cierre)

1. **D05:** extracción con MedGemma local en lugar de casos simulados.
2. **Guardar en el historial:** mandar mediciones y correcciones a las rutas de episodios del backend.
3. **A09:** conectar el chat del asistente a `/api/consulta` (con RAG).
4. **Guías del HRRG:** recién con ellas, colores reales (A09/A10 en pausa).
