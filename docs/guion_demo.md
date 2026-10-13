# Guion de la demo · Sprint 2 (A04)

**Duración:** 5 a 7 minutos · **Todo es simulado y con datos ficticios.** No depende de internet ni de Ollama.

## Antes

- [ ] Abrir `frontend/index.html` en el navegador (doble clic; no hace falta servidor).
- [ ] Probar una vez el recorrido completo y volver al inicio con "Salir".
- [ ] Tener una copia local de la carpeta `frontend/` (pendrive o escritorio) por si falla el repo.

## Recorrido

| Min | Pantalla | Qué se hace | Qué se dice |
|---|---|---|---|
| 0–1 | Acceso | Probar `enfermeria` con clave mala → error. Después `enfermeria` / `demo` | "El acceso es simulado. El login real lo conecta Maricel en Flask." |
| 1–2 | Ingreso | Mostrar el aviso amarillo y el relato ficticio → "Extraer datos" | "La extracción está simulada. Todavía no es MedGemma." |
| 2–4 | Medición | "Demo: completar con valores de ejemplo", corregir un dato | "Lo que falta queda sin dato, nunca en cero. El profesional corrige." |
| 4–5 | Sugerencia | Mostrar el color, "requiere validación" y la fuente "guía de ejemplo, no oficial" → Aceptar | "El color sale de reglas de ejemplo. No es la guía del hospital." |
| 5–6 | En espera | Ver la lista y el reloj (tiempo acelerado) | "Los tiempos son de ejemplo." |
| 6–7 | Errores | Tocar "IA: simulada" para simular que la IA no está → el texto se conserva | "Si la IA falla, el caso no se pierde y se sigue manual." |
| Cierre | — | "Salir" | Próximos pasos: diccionario V2, esquema y API (Etapa 2). |

## Preguntas probables

- **¿Ya usa MedGemma?** No. Hoy es una simulación. La extracción real entra cuando Tomás entregue `backend/src/ia.py` y Maricel la conecte.
- **¿El color es de la guía Manchester del hospital?** No. Son reglas de ejemplo. No se activan colores reales sin las guías autorizadas por el HRRG.
- **¿Se guardan datos?** No. Todo queda en el navegador y se borra al salir.
