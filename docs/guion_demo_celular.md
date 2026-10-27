# Guion de la demo · Lista de espera en el celular y API para el hospital

**Duración:** 5 a 7 minutos (+2 si se muestra la API) · **Actualizado:** 27/10/2026 · **Rama:** `dario`
**Qué se muestra:** la cola de espera en vivo en un celular o tablet (`sala.html`), sincronizada con la PC de triage, y el web service de solo lectura que podría consultar el sistema del hospital (`docs/api_hospital.md`).
**Datos:** todos ficticios. Ningún dato real en ningún campo.

---

## Antes (el día anterior)

- [ ] `git pull origin dario` y probar el recorrido completo una vez, con el celular de verdad.
- [ ] Firewall (una sola vez, PowerShell **como administrador**):

```powershell
New-NetFirewallRule -DisplayName "IngenIA Triage 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private
```

- [ ] Token de la API guardado (una sola vez; **no** usar uno que haya aparecido en un chat):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
setx HRRG_API_HOSPITAL_TOKEN "<token>"
```

- [ ] Averiguar si el Wi-Fi del lugar deja que los dispositivos se vean entre sí (las redes de invitados suelen bloquearlo). Si no se sabe, llevar el **túnel** preparado o un router/celular propio para compartir red.

## Antes (en el momento)

- [ ] Terminal en `HRRG---PP2\backend` → `python app.py` → esperar `Running on http://127.0.0.1:5000`. **No cerrar esa terminal.**
- [ ] `ipconfig` → anotar la IPv4 de la PC (ej.: `192.168.100.71`). PC y celular en el **mismo Wi-Fi**, configurado como red **Privada**.
- [ ] En la PC: abrir **http://127.0.0.1:5000/**, entrar con `enfermeria` y apretar **Ctrl+F5**.
- [ ] Dejar **3 pacientes ficticios ya clasificados** (por ejemplo VERDE, AMARILLO y NARANJA) para que la cola no arranque vacía. Si quedó uno viejo vencido, mejor: sirve para mostrar el aviso.
- [ ] En el celular o la tablet: abrir **`http://<IP>:5000/sala.html`** y dejarlo apoyado a la vista, como si fuera la pantalla de la sala.
- [ ] Brillo al máximo y bloqueo automático de pantalla desactivado en el celular.
- [ ] **Plan B** si el celular no conecta: abrir `https://<túnel>/sala.html` con datos móviles. Plan C: en la PC, otra pestaña con `sala.html` y el modo celular del navegador (F12 → ícono de dispositivo).

---

## Recorrido

| Min | Dónde | Qué se hace | Qué se dice |
|---|---|---|---|
| 0–1 | **Celular · vista pública** | Mostrar la cola: chips de color arriba, orden, tiempos | "Esta es la pantalla de la sala de espera. Se ordena por prioridad y, dentro de cada color, por quien espera más. No hay nombres ni DNI: solo los últimos 4 caracteres del episodio." |
| 1 | **Celular · vencido** | Señalar el paciente marcado en rojo con ⚠ | "Cada color tiene un tiempo máximo. Cuando se pasa, se marca solo. Es lo primero que tiene que ver el personal." |
| 1–2 | **Celular · filtro** | Tocar **AMARILLO** → quedan solo esos. Tocar **TODOS** | "Se puede filtrar por color. El número de la izquierda sigue siendo el lugar en la fila general." |
| 2–3 | **PC · nuevo ingreso** | Cargar un paciente ficticio nuevo y clasificarlo (por ejemplo NARANJA) | "Ingresa un paciente y la enfermera lo clasifica en la PC de triage…" |
| 3 | **Celular** | Esperar unos segundos (**hasta 15 s**) sin tocar nada | "…y aparece solo en el celular, en el lugar que le corresponde por su color. No hay que recargar." |
| 3–4 | **PC · escalar** | En **En espera**, **Escalar a ROJO** sobre un amarillo o verde, con motivo | "Si alguien empeora mientras espera, se escala a ROJO y queda registrado el motivo." |
| 4 | **Celular** | Ver cómo ese paciente **sube al primer lugar** | "El cambio se refleja en todas las pantallas." |
| 4–5 | **PC · finalizar** | **Finalizar (atendido)** sobre el ROJO (confirmar) | "Cuando lo atienden, sale de la lista…" → en el celular desaparece. |
| 5–6 | **Celular · vista del personal** | Abrir `http://<IP>:5000/`, entrar con `enfermeria`, ir a `sala.html?personal=1` | "Con usuario del sistema, el personal ve más datos desde su celular: código completo, DNI enmascarado y motivo. Es solo consulta: las decisiones se toman en la PC." |
| 6 | **PC · reloj** | Mostrar que en **En espera** los minutos avanzan solos | "Los tiempos de la PC y del celular salen del mismo reloj del servidor." |
| *Opcional* 6–8 | **PowerShell · API** | Correr la consulta de la cola (abajo). Después la misma **sin token** → error 401 | "Esto es lo que propuso el profesor: el sistema del hospital consulta nuestra API y recibe la cola en JSON. Sin token no responde: estar en la red del hospital no alcanza como seguridad." |
| Cierre | — | — | Próximos pasos (abajo). |

Consulta para el tramo opcional (en una segunda ventana de PowerShell):

```powershell
$h = @{ Authorization = "Bearer $env:HRRG_API_HOSPITAL_TOKEN" }
Invoke-RestMethod http://127.0.0.1:5000/api/cola-espera -Headers $h | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:5000/api/cola-espera            # sin token → 401
```

---

## Preguntas probables

- **¿Por qué no aparece el nombre o el DNI en la pantalla de la sala?** Porque cualquiera la puede ver. Se muestran solo 4 caracteres del episodio, el color y la espera; con eso no se identifica a nadie. El DNI es dato personal (Ley 25.326).
- **¿Cómo sabe el paciente cuál es su código?** Hoy no lo sabe. Habría que darle un ticket impreso o anotarle el código al clasificarlo. Es un punto para definir con el HRRG.
- **¿Qué pasa con los pacientes que todavía no pasaron por el triage?** No aparecen: sin color no tienen prioridad todavía.
- **¿Se puede reevaluar o escalar desde el celular?** No, a propósito. El celular es de consulta; las decisiones quedan en la PC, con usuario y registro.
- **¿Funciona fuera de la red del hospital?** Por la IP local, no. Con el túnel, sí, desde cualquier lugar. Para datos reales eso requiere conexión cifrada y autorización del hospital.
- **¿La API ya está conectada al sistema del hospital?** No. Nosotros dejamos la API lista y documentada (`docs/api_hospital.md`); la parte que la consulta la tiene que desarrollar el hospital. Fue una sugerencia opcional del profesor.
- **¿Es seguro?** Para la demo, con datos ficticios, sí. Para datos reales falta: HTTPS, un token por sistema que se pueda revocar y acordar con el hospital qué datos se comparten. Hoy la API no entrega el DNI salvo que se habilite a propósito.
- **¿Por qué tarda unos segundos en aparecer?** El celular consulta cada 15 s y la PC cada 30 s. Se puede bajar si el hospital lo necesita.

## Próximos pasos (para el cierre)

- Definir con el HRRG cómo se entera el paciente de su código (ticket, pantalla, llamado).
- Confirmar los tiempos máximos por color con las guías que autorice el hospital (hoy son de ejemplo).
- Si el hospital quiere usar la API: acordar qué datos necesita, quién la consulta y cómo se cifra la conexión.
