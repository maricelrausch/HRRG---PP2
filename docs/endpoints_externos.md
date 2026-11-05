# Endpoints para otros sistemas: sala de espera y auditoría

**Propuesta Barby 30/10 · pedido del HRRG.** Dos puntos de acceso de **solo lectura** que devuelven JSON, para que otros sistemas usen la información del triage sin entrar a la aplicación.

| # | Para qué | Ruta | Acceso | Datos personales |
|---|---|---|---|---|
| 1 | Pantallas de la **sala de espera** | `GET /api/sala/espera` | Público (sin clave) | **No** |
| 2 | Sistema de **auditoría** (lo mismo que ve el perfil Auditoría) | `/api/auditoria/...` | Con **token** propio | **Sí: DNI completo** |

Las dos rutas usan el mismo servidor y el mismo puerto de la aplicación (por ejemplo `http://<IP de la PC>:5000`).

---

## 1. Lista de espera para la sala · `GET /api/sala/espera`

Es la misma fuente que usa la pantalla del celular de Darío (`sala.html`). La puede leer cualquier pantalla de la red, por eso **no tiene datos personales**: sin nombre, sin DNI, sin motivo y sin código de paciente.

**Respuesta:**

```json
{
  "ok": true,
  "episodios": [
    {"codigo": "245F", "color": "NARANJA", "espera_seg": 312, "objetivo_min": 10,
     "en_espera_desde": "2026-10-30T13:02:11+00:00", "vencido": false},
    {"codigo": "72F1", "color": "AMARILLO", "espera_seg": 4520, "objetivo_min": 60,
     "en_espera_desde": "2026-10-30T11:51:03+00:00", "vencido": true}
  ]
}
```

| Campo | Qué es |
|---|---|
| `codigo` | Últimos 4 caracteres del episodio (no identifica a nadie) |
| `color` | ROJO, NARANJA, AMARILLO o VERDE |
| `espera_seg` | Segundos que lleva esperando, según el reloj del servidor |
| `objetivo_min` | Tiempo máximo de su color (de ejemplo, no oficial) |
| `en_espera_desde` | Hora del triage, en ISO 8601 con zona horaria (**nuevo 30/10**) |
| `vencido` | `true` si superó el tiempo de su color (**nuevo 30/10**) |

- Viene **ordenada**: primero por color (ROJO arriba) y, dentro de cada color, por quien espera más.
- Los pacientes **sin color** (todavía no pasaron por el triage) no aparecen.
- Se puede **apagar** con la variable de entorno `HRRG_SALA_PUBLICA=0`.

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/sala/espera | ConvertTo-Json -Depth 4
```

**Código QR** (propuesta Barby 30/10): la página `qr_sala.html` (botón **QR de la sala** en En espera) muestra un QR para abrir la lista desde un celular de la misma red. El servidor arma el QR con la IP de la PC, aunque la página se haya abierto como `127.0.0.1`.

| Ruta | Qué devuelve |
|---|---|
| `GET /api/sala/qr` | `{"direcciones": {"sala": "http://IP:5000/sala.html"}}` |
| `GET /api/sala/qr.svg?destino=sala` | Imagen SVG del QR de la pantalla de sala |

Son públicas como la lista (sin datos de pacientes) y se apagan junto con ella (`HRRG_SALA_PUBLICA=0`). Necesitan la librería `segno` (está en `requirements.txt`).

---

## 2. API de auditoría · `/api/auditoria/...`

Da a **otro sistema** acceso de solo lectura a lo que ve el perfil Auditoría: búsqueda de casos, historial completo de cada episodio y exportación.

Código: `backend/src/api_auditoria.py` · Pruebas: `backend/tests/test_api_auditoria.py`.

### Cómo habilitarla

Arranca **apagada**: sin token configurado responde `503`. Tiene un token **propio**, distinto del de la API del hospital, para poder revocarlo por separado.

```bat
:: Generar un token largo y aleatorio (una vez) y dárselo solo al sistema autorizado
python -c "import secrets; print(secrets.token_urlsafe(32))"

set HRRG_API_AUDITORIA_TOKEN=<el token generado>
python app.py
```

Cada pedido lleva el token en la cabecera: `Authorization: Bearer <token>`. Sin token o con uno incorrecto: `401 TOKEN_INVALIDO`.

### Rutas

| Método y ruta | Qué devuelve |
|---|---|
| `GET /api/auditoria/casos` | Lista de casos, del más nuevo al más viejo. Filtros: `estado` (`en_ingreso`, `en_espera`, `finalizado`, `anulado`), `desde` y `hasta` (ISO 8601), `limite` (1 a 100, por defecto 50) y `desplazamiento`. |
| `POST /api/auditoria/casos/buscar` | Todas las atenciones de un paciente. Cuerpo: `{"dni": "30123456"}`. **El DNI va en el cuerpo, nunca en la URL.** |
| `GET /api/auditoria/casos/<codigo_episodio>` | Historial completo del episodio: datos de ingreso, mediciones, correcciones, decisiones con su motivo y cambios de estado, con fecha y profesional. |
| `POST /api/auditoria/exportar` | Exportación. Cuerpo: `{"formato": "json" \| "excel" \| "pdf", "estado", "desde", "hasta", "dni", "clave"}`. |

**Exportar:**
- `json`: devuelve los casos con su historial completo.
- `excel` o `pdf`: devuelve el archivo (los mismos que exporta el auditor), **protegido con la `clave`** que manda el sistema (obligatoria, 12 caracteres o más).
- Con `dni` se exportan **todas las atenciones de ese paciente**, sin aplicar estado ni fechas.

**Ejemplos (PowerShell):**

```powershell
$h = @{ Authorization = "Bearer $env:HRRG_API_AUDITORIA_TOKEN" }
$u = "http://127.0.0.1:5000/api/auditoria"

# Casos en espera
Invoke-RestMethod "$u/casos?estado=en_espera" -Headers $h | ConvertTo-Json -Depth 5

# Atenciones de un paciente
Invoke-RestMethod "$u/casos/buscar" -Method Post -Headers $h -ContentType "application/json" -Body '{"dni":"30123456"}'

# Historial de un episodio
Invoke-RestMethod "$u/casos/EPI-8C4C18B754B40405245F" -Headers $h | ConvertTo-Json -Depth 6

# Excel protegido
Invoke-WebRequest "$u/exportar" -Method Post -Headers $h -ContentType "application/json" `
  -Body '{"formato":"excel","estado":"finalizado","clave":"clave-del-sistema-123"}' -OutFile casos.xlsx
```

### Seguridad

- **Solo lectura:** no crea, modifica ni borra nada.
- **DNI completo** (decisión del grupo 30/10). Es un dato personal (Ley 25.326): con datos reales hace falta **HTTPS** y **autorización del hospital** para el sistema que lo consulte.
- **El DNI nunca va en la URL ni en el log.** Cada acceso queda registrado en `sistema.log` con ruta, IP, resultado y cantidad de casos, sin datos de pacientes.
- Para cortar el acceso: borrar o cambiar `HRRG_API_AUDITORIA_TOKEN` y reiniciar.

### Errores

| Código HTTP | `codigo` | Cuándo |
|---|---|---|
| 400 | `PARAMETROS_INVALIDOS` · `CAMPOS_INVALIDOS` · `ESTADO_INVALIDO` | Parámetros o campos desconocidos, estado o formato inválidos |
| 401 | `TOKEN_INVALIDO` | Falta el token o es incorrecto |
| 404 | `EPISODIO_NO_ENCONTRADO` · `PACIENTE_NO_ENCONTRADO` | No existe el episodio o no hay paciente con ese DNI |
| 415 | `FORMATO_NO_ADMITIDO` | El cuerpo de un POST no es JSON |
| 422 | `IDENTIFICACION_INVALIDA` · `CLAVE_INVALIDA` · `FILTRO_INVALIDO` · `PAGINACION_INVALIDA` | DNI mal formado, clave corta, fechas o paginación inválidas |
| 503 | `API_DESHABILITADA` · `IDENTIFICACION_NO_DISPONIBLE` · `EXPORTACION_NO_DISPONIBLE` | Sin token configurado, sin claves de identificación o sin librerías de exportación |

Todas las respuestas JSON llevan `ok`, `version_api`, `modo` y `generado_en`, y no se guardan en caché (`Cache-Control: no-store`).
