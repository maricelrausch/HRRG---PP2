# Contrato de API — HRRG


Estado: propuesta para revisión de Bárbara, Tomás, Darío y Maricel.
Versión propuesta del contrato: 0.3 — integración en revisión.

La autenticación y las rutas de episodios están implementadas.
POST /api/extraer tiene modo simulado implementado y una conexión experimental con MedGemma.
La ejecución real de IA y la integración web todavía requieren pruebas.

## 1. Convenciones generales


- Solicitudes y respuestas en JSON.
- Content-Type: application/json.
- Nombres de campos en snake_case.
- Identificadores tratados como texto.
- El profesional se obtiene de la sesión del servidor.
- El cliente no puede elegir el profesional ni sus permisos.
- Las pruebas utilizan exclusivamente datos ficticios.

## 2. Autenticación disponible


### POST /api/login


Entrada:

```json
{
  "usuario": "prueba_enfermeria",
  "password": "<contraseña de la cuenta local>"
}
```


Respuesta correcta: HTTP 200.

```json
{
  "ok": true,
  "mensaje": "Sesión iniciada correctamente.",
  "usuario": "prueba_enfermeria"
}
```

### Modo de extracción informado en la sesión

GET /api/sesion requiere una sesión válida y devuelve los datos del
profesional junto con el modo de extracción configurado en el servidor.

Ejemplo de respuesta HTTP 200:

```json
{
  "ok": true,
  "usuario": "prueba_enfermeria",
  "nombre": "Enfermeria de prueba",
  "rol": "enfermeria",
  "modo_extraccion": "ia"
}
```

Valores de modo_extraccion:

- "simulado": utiliza respuestas predefinidas de demostración.
- "ia": está configurado para realizar extracción mediante el modelo local.

Este campo informa la configuración; no comprueba que Ollama o el modelo
estén disponibles ni confirma que una extracción haya terminado correctamente.

El frontend debe conservar este campo al procesar la respuesta de sesión
y utilizarlo para mostrar el modo configurado desde el inicio.
El origen de cada extracción se obtiene del campo "modo" de /api/extraer.

La respuesta de sesión mantiene la cabecera Cache-Control: no-store.

### GET /api/sesion


Respuesta correcta: HTTP 200.

```json
{
  "ok": true,
  "usuario": "prueba_enfermeria",
  "nombre": "Enfermería de prueba",
  "rol": "enfermeria",
  "modo_extraccion": "ia"
}
}
```


Perfiles admitidos: enfermeria, medico y auditor.
Las cuentas sin perfil asignado no acceden a las rutas protegidas.

### POST /api/logout


Recibe un objeto JSON vacío: {}.
Elimina la sesión del cliente y devuelve HTTP 200.

Las cuentas se administran desde la terminal.
No existe registro público de profesionales.

## 3. Identificación y episodios


- codigo_paciente identifica al paciente ficticio.
- codigo_episodio identifica una atención concreta.
- Un paciente puede tener varios episodios.
- Los códigos no deben contener nombres, DNI ni otros datos personales.
- El profesional responsable se obtiene de la sesión.

Para la extracción se valida el siguiente formato:

^[A-Z]{2,4}-[A-Z0-9-]{3,20}$

Ejemplos: PAC-DEMO-001 y EPI-DEMO-001.

El servidor genera codigo_episodio cuando se omite en la creación.
Por compatibilidad, también se admite un código explícito.

Rutas disponibles:

- POST /api/demo/episodios: recibe codigo_paciente y, opcionalmente,
  codigo_episodio. Guarda el episodio y su evento de creación.
- GET /api/demo/episodios: lista episodios con filtros opcionales
  por codigo_paciente y codigo_episodio, y admite paginación.
- GET /api/demo/episodios/<codigo_episodio>: consulta el episodio
  y su historial completo.

Médicos y enfermería pueden crear y consultar episodios.
El auditor puede consultar el listado y los historiales, pero no crear.

Los identificadores recibidos en estas rutas admiten textos de
1 a 100 caracteres. Su unificación con el patrón de /api/extraer
sigue pendiente. El código generado por el servidor cumple ese patrón.

La generación automática y la búsqueda se incorporaron al código;
sus pruebas e integración con el frontend están pendientes.

Rutas disponibles:

- POST /api/demo/episodios:
  recibe codigo_paciente y codigo_episodio;
  crea un episodio asociado al profesional de la sesión.
- GET /api/demo/episodios/<codigo_episodio>:
  consulta un episodio y su historial según el rol, aunque lo haya creado otro profesional.

La validación actual de estas rutas admite textos de 1 a 100
caracteres; su unificación con el patrón de DatosTriage está pendiente.

El auditor no puede crear episodios.
El auditor puede consultar un episodio por código, aunque lo haya creado otro profesional.
No hay una ruta de listado global de episodios.

## 4. Extracción — modos simulado e IA


POST /api/extraer

Requiere sesión válida y perfil enfermeria o medico.
El perfil auditor recibe HTTP 403.

Entrada:

```json
{
  "codigo_paciente": "PAC-DEMO-001",
  "codigo_episodio": "EPI-DEMO-001",
  "texto": "Me duele el pecho desde hace media hora, como una presión, y estoy sudando."
}
```


Reglas de entrada implementadas:

- Los tres campos son obligatorios y deben ser textos.
- No se aceptan campos adicionales.
- Los códigos deben cumplir el patrón de la sección 3.
- texto debe tener entre 1 y 5000 caracteres después de quitar
  espacios al principio y al final.
- Un texto vacío o con formato inválido devuelve HTTP 422.

Esta ruta no crea episodios ni guarda decisiones en D03.
Devuelve los códigos recibidos para vincular la respuesta.
No comprueba todavía que esos códigos existan en el registro.

La función de extracción recibe únicamente el relato y el esquema,
sin credenciales ni códigos de identificación.

## 5. Funcionamiento de la simulación


El modo simulado se configura explícitamente en el servidor.
No se utiliza como reemplazo silencioso cuando falla el modelo real.

Fuente: backend/datos/casos_simulados.json.

Para D03:

1. Se consideran los casos de tipo "demo" que tengan relato y entrada.
2. Se compara texto con el relato del caso, normalizando espacios.
   No se realiza búsqueda semántica ni interpretación del texto.
3. Si no existe una coincidencia única, se devuelve HTTP 422.
4. Se seleccionan únicamente los campos definidos en ExtraccionIA.
5. La respuesta se valida con ese modelo Pydantic.

Los casos son respuestas predefinidas para probar integración.
Algunos contienen información que no aparece en el relato:
no constituyen resultados de extracción real ni sirven para medir
la precisión de MedGemma.

No se devuelven:

- Mediciones ni signos vitales.
- Edad y sexo provenientes de la identificación.
- nivel_maqueta.
- Colores, prioridades o discriminadores clínicos.

## 6. Respuesta de extracción simulada


Respuesta correcta: HTTP 200.

Estructura:

- ok: true.
- modo: "simulado".
- caso_simulado_id: identificador del caso utilizado.
- codigo_paciente: código recibido.
- codigo_episodio: código recibido.
- version_esquema: "ExtraccionIA-v2".
- modelo: null, porque no se invoca un modelo.
- datos: objeto validado con ExtraccionIA.
- campos_faltantes: lista de campos requeridos de extracción vacíos.
- advertencias: lista de textos explicativos.

"ExtraccionIA-v2" es una etiqueta propuesta para este contrato;
no implica que el esquema tenga actualmente versionado automático.

datos incluye todos los campos de ExtraccionIA.
Los campos opcionales sin valor se representan como null.
Los valores numéricos se devuelven como números JSON.

Limitación del esquema actual:
las banderas y antecedentes booleanos tienen false por defecto.
Ese valor no distingue entre "no mencionado" y "negado".
El equipo debe acordar esta diferencia antes de la extracción real.

campos_faltantes se calcula tomando los campos de
OBLIGATORIOS["ingreso"] que pertenecen a ExtraccionIA y cuyo valor
validado es null.

No incluye edad, sexo ni mediciones, porque pertenecen a otras etapas.
Una lista vacía no significa que el caso esté completo para clasificar.

advertencias debe informar que:

- La respuesta es predefinida y simulada.
- No proviene de MedGemma.
- Requiere revisión humana.
- No constituye una clasificación Manchester.

## 7. Errores


Formato común:

```json
{
  "ok": false,
  "mensaje": "Descripción del problema.",
  "codigo": "IDENTIFICADOR_DEL_ERROR"
}
```


Estados previstos para D03:

| HTTP | Situación |
|---|---|
| 400 | JSON mal formado o que no sea un objeto |
| 401 | Sesión inexistente o cuenta inactiva |
| 403 | Perfil no asignado o sin permiso |
| 415 | Contenido no enviado como JSON |
| 422 | Campos, tipos, códigos o texto inválidos |
| 422 | No existe una coincidencia única con un caso simulado |
| 500 | Archivo de casos inaccesible, mal formado o respuesta predefinida inválida |
| 503 | Modo de extracción deshabilitado o todavía no disponible |

Ejemplo:

```json
{
  "ok": false,
  "mensaje": "El texto no corresponde a un caso de demostración disponible.",
  "codigo": "CASO_SIMULADO_NO_IDENTIFICADO"
}
```


Para D05, al integrar la IA:

- 502: salida del modelo inválida.
- 503: servicio de IA no disponible.
- 504: tiempo de espera agotado.

Los errores no deben incluir contraseñas, trazas internas ni
copias del relato recibido.

## 8. Persistencia y auditoría


D03 valida la solicitud y devuelve una respuesta simulada.
No persiste el relato, la extracción ni las correcciones.

El registro completo del proceso se desarrolla en D07 y D10.
Debe vincular episodio, profesional, origen de datos,
correcciones, modelo, latencia y decisión.

sistema.log no reemplaza el historial del episodio.
Las pruebas usan datos ficticios y no registran secretos.

## 9. Criterios de prueba de D03


- Solicitud válida: HTTP 200 y modo "simulado".
- Respuesta compatible con ExtraccionIA.
- No incluye signos vitales ni prioridad clínica.
- Texto vacío o solicitud inválida: HTTP 422.
- Texto sin caso correspondiente: HTTP 422.
- Sin sesión: HTTP 401.
- Con auditor: HTTP 403.
- Archivo de casos inválido: error controlado, sin respuesta falsa.
- No requiere Ollama ni modifica el frontend.

## 10. Acuerdos pendientes para cerrar D02


- Bárbara: estructura consumible desde el frontend.
- Tomás: compatibilidad con la futura función de extracción.
- Darío: campos, faltantes, booleanos y versión del esquema.
- Maricel: implementación, permisos y errores del backend.


Cualquier cambio del contrato debe comunicarse al equipo.


## Historial de episodios — modo demostración


Estado: implementado en backend; pendiente de revisión del equipo
e integración con el frontend.

Solo se utilizan pacientes, episodios y mediciones ficticios.
Estas rutas requieren una sesión válida.

### Permisos


| Acción | Enfermería / Médico | Auditor |
|---|---|---|
| Crear episodio | Sí | No |
| Consultar episodio e historial | Sí | Sí |
| Registrar mediciones | Sí | No |
| Corregir mediciones | Sí | No |

La consulta y la escritura autorizadas no dependen de quién creó
el episodio. Cada evento conserva su propio autor.

Flask obtiene el usuario y el rol desde la sesión.
El cliente no debe enviar la identidad del profesional.

## Creación y consulta de episodios de demostración

### Crear un episodio

POST /api/demo/episodios
Content-Type: application/json

Requiere sesión activa con rol medico o enfermeria.
El auditor no puede crear episodios.

Entrada recomendada:

```json
{
  "codigo_paciente": "PAC-DEMO-001"
}
```

El servidor genera codigo_episodio y guarda en SQLite el episodio
y el evento EPISODIO_CREADO, con fecha y profesional responsable.

Por compatibilidad, también se admite codigo_episodio en la entrada.
Si el código ya existe, se devuelve HTTP 409.

Ejemplo de respuesta HTTP 201:

```json
{
  "ok": true,
  "modo": "demo",
  "episodio": {
    "codigo_episodio": "EPI-A1B2C3D4E5F607182930",
    "codigo_paciente": "PAC-DEMO-001",
    "creado_en": "2026-10-18T21:00:00+00:00"
  }
}
```

El frontend debe conservar episodio.codigo_episodio y reutilizarlo
para las mediciones, correcciones y consultas de esa atención.

Una reevaluación mantiene el episodio.
Una nueva atención genera otro episodio.

No repetir automáticamente el POST si se pierde la respuesta:
la creación todavía no tiene un mecanismo de idempotencia que
impida duplicados por reintentos.

### Buscar episodios

GET /api/demo/episodios

Requiere sesión activa con rol medico, enfermeria o auditor.
Permite consultar episodios creados por otros profesionales.

Parámetros opcionales:

- codigo_paciente: coincidencia exacta.
- codigo_episodio: coincidencia exacta.
- limite: entero entre 1 y 100; por defecto 50.
- desplazamiento: entero mayor o igual a 0; por defecto 0.

Si se envían ambos códigos, deben coincidir ambos.
No se aceptan parámetros desconocidos ni repetidos.

Ejemplo:

GET /api/demo/episodios?codigo_paciente=PAC-DEMO-001&limite=50

Respuesta HTTP 200:

```json
{
  "ok": true,
  "modo": "demo",
  "episodios": [
    {
      "codigo_episodio": "EPI-A1B2C3D4E5F607182930",
      "codigo_paciente": "PAC-DEMO-001",
      "creado_en": "2026-10-18T21:00:00+00:00",
      "profesional_usuario": "prueba_enfermeria"
    }
  ],
  "total": 1,
  "limite": 50,
  "desplazamiento": 0
}
```

Los resultados se ordenan por fecha de creación descendente.
Sin coincidencias se devuelve HTTP 200, episodios: [] y total: 0.

profesional_usuario identifica al creador del episodio.
Cada evento del historial conserva por separado a su propio autor.

### Consultar el historial completo

GET /api/demo/episodios/<codigo_episodio>

Devuelve el episodio y sus eventos mediante la ruta existente.
Médicos, enfermería y auditores pueden consultarlo.

El listado de episodios no equivale al tablero de espera:
todavía falta implementar la persistencia del estado de atención.

### Integración pendiente en el frontend

1. Crear el episodio una sola vez al iniciar la atención.
2. Conservar el código que devuelve el servidor.
3. Registrar nuevas mediciones sobre ese mismo episodio.
4. Diferenciar una nueva medición de una corrección por error.
5. Buscar episodios y consultar su historial.
6. Mostrar "Guardado" únicamente después de una respuesta exitosa.

### Registrar una medición


POST /api/demo/episodios/{codigo_episodio}/mediciones

Entrada:

```json
{
  "medido_en": "2026-10-15T10:45:00-03:00",
  "valores": {
    "ta_sistolica": 150,
    "ta_diastolica": 80
  }
}
```


El episodio debe existir previamente.

medido_en debe incluir fecha, hora y zona horaria.
No se admiten fechas futuras.

valores utiliza los nombres y validaciones de Mediciones,
definidos en backend/src/esquemas.py.

Se admite una medición parcial con al menos un valor válido.
Los campos omitidos no se copian de mediciones anteriores.
La PAM se calcula en el backend; no debe enviarse.

Respuesta correcta: HTTP 201.

```json
{
  "ok": true,
  "modo": "demo",
  "evento": {
    "id": 3,
    "codigo_episodio": "EPI-DEMO-001",
    "tipo": "MEDICION_REGISTRADA",
    "ocurrido_en": "2026-10-15T13:46:00+00:00",
    "profesional_usuario": "prueba_enfermeria",
    "datos": {
      "version_evento": 1,
      "modo": "demo",
      "origen": "medicion_profesional",
      "medido_en": "2026-10-15T13:45:00+00:00",
      "valores": {
        "ta_sistolica": 150,
        "ta_diastolica": 80,
        "pam": 103
      }
    }
  }
}
```


Los identificadores y fechas de las respuestas son ilustrativos.

### Corregir una medición


POST /api/demo/episodios/{codigo_episodio}/mediciones/{evento_id}/correcciones

Entrada:

```json
{
  "cambios": {
    "ta_sistolica": 140
  },
  "motivo": "Error de transcripcion en caso ficticio"
}
```


Respuesta correcta: HTTP 201, con ok, modo y evento.

El nuevo evento tiene tipo MEDICION_CORREGIDA y contiene:

- evento_corregido_id: ID de la versión corregida.
- medido_en: hora de medición original.
- motivo: explicación obligatoria, de 1 a 200 caracteres.
- valores_anteriores: valores de la versión anterior.
- valores: resultado validado después de aplicar los cambios.
- profesional_usuario: autor de la corrección, en el evento.
- ocurrido_en: fecha de registro generada por el servidor.

Los campos no incluidos en cambios conservan su valor anterior.
Un null explícito permite retirar un valor, siempre que quede
al menos una medición válida. La PAM se recalcula.

El evento original no se modifica ni se elimina.
Para corregir nuevamente debe utilizarse el ID de la última
corrección. Una versión ya corregida no admite otra rama de cambios.

Esta operación corrige valores; no cambia la hora de medición.
Una nueva toma de signos vitales debe registrarse como nueva medición.

### Consultar historial


GET /api/demo/episodios/{codigo_episodio}

Respuesta correcta: HTTP 200, con ok, modo y episodio.
episodio contiene sus identificadores, creador, fecha y eventos.

Los eventos se devuelven ordenados por ID de registro.
Ese orden no necesariamente coincide con la hora de medición,
porque puede haber cargas retrospectivas.

El frontend debe conservar la distinción entre mediciones y
correcciones. Una corrección de una medición antigua no debe
presentarse como una nueva toma de signos vitales.


### Errores de las nuevas rutas de escritura


Formato:

```json
{
  "ok": false,
  "mensaje": "Descripción del problema.",
  "codigo": "IDENTIFICADOR_DEL_ERROR"
}
```


| HTTP | Código | Situación |
|---|---|---|
| 400 | JSON_INVALIDO | JSON mal formado o contenido que no es objeto. |
| 401 | SESION_REQUERIDA | Sesión ausente, inválida o cuenta inactiva. |
| 403 | ROL_NO_ASIGNADO | Cuenta sin un rol admitido. |
| 403 | PERMISO_DENEGADO | El auditor intenta escribir. |
| 415 | FORMATO_NO_SOPORTADO | Contenido no JSON. |
| 422 | CAMPOS_INVALIDOS | Campos requeridos ausentes o adicionales. |
| 422 | MEDICION_INVALIDA | Valores que incumplen el esquema. |
| 422 | REGISTRO_INVALIDO | Fecha o medición inválida, o episodio inexistente. |
| 422 | CORRECCION_INVALIDA | Corrección inválida o versión ya corregida. |
| 500 | ERROR_REGISTRO | Falla de almacenamiento. |

La consulta de un episodio inexistente devuelve HTTP 404
con EPISODIO_NO_ENCONTRADO.

### Relación con la extracción


POST /api/extraer devuelve una respuesta simulada o de IA según la configuración explícita del servidor.
Actualmente no crea episodios ni guarda automáticamente eventos
de extracción, mediciones o correcciones.


## 11. Configuración de extracción en la integración


Estado: código preparado; pendiente de ensayo con modelos instalados y revisión conjunta.
La configuración se lee al iniciar Flask. Cambiarla requiere reiniciar el servidor.

| Configuración | Comportamiento |
|---|---|
| `HRRG_MODO_EXTRACCION` ausente o `simulado` | Usa los casos ficticios; no carga MedGemma, BETO ni ChromaDB para extraer. |
| `HRRG_MODO_EXTRACCION=ia` | Llama a `src.extraccion.extraer_datos(relato, ExtraccionIA)`. |
| Otro valor | HTTP 503, `CONFIGURACION_INVALIDA`. |
| `EXTRACCION_SIMULADA_HABILITADA=False` en Flask | Bloquea el modo simulado con HTTP 503, `EXTRACCION_DESHABILITADA`. No controla el modo IA. |

En modo IA, la respuesta conserva las claves de la sección 6 con estas diferencias:

- `modo`: `"ia"`.
- `caso_simulado_id`: `null`.
- `modelo`: valor de `LLM_MODEL` en `src/modelo.py` (actualmente `medgemma:4b`).
- `datos`: resultado del modelo validado con `ExtraccionIA`.
- `advertencias`: informa origen IA, revisión profesional y ausencia de clasificación Manchester.

La función actual de Tomás consulta RAG antes de MedGemma. Requiere las dependencias y modelos correspondientes; su instalación reproducible está pendiente.
Si falla la IA, no se devuelve un caso simulado como sustituto.

| HTTP | Código | Situación |
|---|---|---|
| 502 | SALIDA_IA_INVALIDA | La función devuelve datos incompatibles o lanza un error de valor/validación. |
| 503 | IA_NO_DISPONIBLE | Falla al importar, inicializar o ejecutar el servicio. |

Limitaciones: falta distinguir errores de conexión, modelo ausente y tiempo agotado; definir un timeout explícito; validar la extracción con casos de referencia. Los booleanos con `false` por defecto siguen sin distinguir ausencia de información y negación. La validación estructural no garantiza exactitud clínica.

## 12. Ruta experimental BETO — pendiente de contrato definitivo


`POST /api/analizar` se conserva para revisar el aporte de Tomás. No es equivalente a `/api/extraer` ni utiliza MedGemma.

- Requiere sesión activa y perfil `enfermeria` o `medico`; auditor recibe HTTP 403.
- Está deshabilitada por defecto: devuelve HTTP 503 con `BETO_DESHABILITADO` a un profesional autorizado.
- Solo se habilita con `HRRG_BETO_HABILITADO=1` al iniciar Flask.
- Recibe exclusivamente `{"texto": "Relato ficticio"}`; texto de 1 a 5000 caracteres tras quitar espacios exteriores.
- Sin JSON: 415; JSON no objeto: 400; claves incorrectas o texto inválido: 422.
- Un error de carga o procesamiento devuelve 503 con `BETO_NO_DISPONIBLE`.
- Si funciona, devuelve HTTP 200 con el diccionario de `extraer_datos_planilla`, sin la envoltura `ok`, `modo`, `datos` de `/api/extraer`.

El diccionario experimental usa claves como `tas`, `tad`, `frec_cardiaca`, `saturacion` y `dolor`. Todavía no se valida con `ExtraccionIA` ni con `Mediciones` en esta ruta. Debe acordarse su normalización y la separación entre datos relatados, datos medidos y revisión humana antes de integrarlo al flujo común.

El modelo local `modelo_medico_entrenado` y sus dependencias deben estar disponibles para habilitar BETO. La ruta no guarda episodios ni eventos.

## 13. Pendientes de la fusión y coordinación


- Resolver y revisar `frontend/api.js` y `frontend/formulario.js` con Bárbara. El botón de la rama de Tomás llama a `/api/analizar`, aunque su mensaje menciona MedGemma; corregir esa correspondencia.
- Conectar el historial del backend al frontend y probar permisos por HTTP.
- Revisar dependencias, modelos y preparación reproducible con Tomás.
- Acordar esquemas, valores desconocidos y ejemplos JSON con Darío.
- La integración del chat `/api/chat` de Tomás sigue pendiente. El `app.py` entregado conserva las rutas documentales anteriores (`/chat`, `/upload`), deshabilitadas por defecto; no deben presentarse como chat MedGemma integrado.
- La espera y las decisiones profesionales todavía no tienen persistencia completa en estas rutas.
- Este documento describe una propuesta de integración, no una aprobación del equipo ni validación institucional.

## 13. Administración de cuentas y contraseñas

Implementado en `backend/src/admin_usuarios.py` y registrado en `app.py`.
Pantallas: `frontend/admin.html` (perfil `admin`) y `frontend/cambiar_password.html` (cualquier perfil).

### Perfil `admin`

- Gestiona cuentas y contraseñas. No accede a las rutas clínicas (403 `PERMISO_DENEGADO`).
- El primer administrador se crea desde la terminal, en la carpeta `backend`:

```powershell
python -m flask --app app crear-profesional
python -m flask --app app asignar-rol --rol admin
```

### Política de contraseñas

- Entre 12 y 256 caracteres, con mayúscula, minúscula, número y símbolo.
- Vence a los 90 días: al ingresar se exige el cambio.
- No se puede repetir ninguna de las últimas 5.
- Cinco intentos fallidos bloquean la cuenta hasta que un administrador la desbloquea.
- El administrador nunca ve contraseñas: genera una clave temporal de un solo uso (1, 4 o 24 h) que el profesional cambia al ingresar.
- `flask cambiar-password` (terminal) también desbloquea la cuenta y quita el cambio pendiente: sirve para recuperar un administrador bloqueado.

### Cambios en las rutas existentes

| Ruta | Cambio |
|---|---|
| POST /api/login | 423 `CUENTA_BLOQUEADA`; 401 `CLAVE_TEMPORAL_VENCIDA`; la respuesta agrega `debe_cambiar` |
| GET /api/sesion | Agrega `debe_cambiar`. Responde también al perfil `admin` y a cuentas con cambio pendiente |
| Rutas protegidas | 403 `CAMBIO_PASSWORD_REQUERIDO` mientras la contraseña esté pendiente de cambio o vencida |

### Rutas nuevas

Todas responden JSON, con `Cache-Control: no-store` y el formato de error común. Los POST exigen `Content-Type: application/json`.

| Ruta | Quién | Cuerpo | Respuesta |
|---|---|---|---|
| GET /api/admin/usuarios | admin | — | `usuarios` (id, usuario, nombre, rol, estado, dias_desde_cambio, propia) y `roles` |
| POST /api/admin/usuarios | admin | `usuario`, `nombre`, `rol` | 201 con `temporal` y `vence_horas` (24) |
| POST /api/admin/usuarios/<id>/restablecer | admin | `horas`: 1, 4 o 24 | `temporal`, `vence_horas` |
| POST /api/admin/usuarios/<id>/desbloquear | admin | `{}` | `ok` |
| POST /api/admin/usuarios/<id>/rol | admin | `rol` | `ok` (no sobre la propia cuenta: 409) |
| POST /api/admin/usuarios/<id>/activo | admin | `activo`: true/false | `ok` (no sobre la propia cuenta: 409) |
| GET /api/admin/auditoria | admin | — | `eventos`: las últimas 100 acciones |
| POST /api/cuenta/password | cualquier sesión | `actual`, `nueva` | `ok` |

Estados de una cuenta: `Activa`, `Vencida`, `Bloqueada`, `Cambio pendiente`, `Desactivada`.

Códigos de error nuevos: `CUENTA_BLOQUEADA` (423), `CLAVE_TEMPORAL_VENCIDA` (401), `CAMBIO_PASSWORD_REQUERIDO` (403), `USUARIO_EXISTENTE` (409), `OPERACION_SOBRE_SI_MISMO` (409), `CUENTA_NO_ENCONTRADA` (404), `PASSWORD_ACTUAL_INCORRECTA`, `PASSWORD_DEBIL` y `PASSWORD_REPETIDA` (400).

### Persistencia

En `~/.hrrg_pp2/usuarios.db`, junto a `profesionales`:

- Columnas nuevas en `profesionales`: `intentos_fallidos`, `bloqueada`, `debe_cambiar`, `password_cambiada`, `temp_vence`. Se agregan solas al iniciar `app.py`.
- `historial_passwords`: últimos 5 hashes por profesional.
- `auditoria_cuentas`: fecha, actor, acción, cuenta e IP de cada operación.

## 14. Datos de ingreso y DNI en la lista de espera — propuesta (Barby, 23/10) · a revisar por Maricel

> Hecho mientras Maricel está de viaje, con el mismo estilo que las rutas de mediciones.
> Archivos tocados: `backend/src/registro.py`, `backend/src/identificacion.py`, `backend/app.py`.
> Cada bloque nuevo está marcado con `[Propuesta Barby 23/10 · a revisar por Maricel]`.

### Registrar los datos de ingreso revisados

`POST /api/demo/episodios/<codigo_episodio>/datos-ingreso` (enfermería y médicos; el auditor no puede escribir)

```json
{
  "datos": {
    "edad": 61, "sexo": "Masculino",
    "motivo_categoria": "Dolor torácico", "motivo_consulta": "Dolor de pecho opresivo con sudoración",
    "tiempo_evolucion_valor": 30, "tiempo_evolucion_unidad": "minutos",
    "dolor_localizacion": "Tórax", "sintomas_asociados": "Sudoración",
    "br_sangrado": false, "ant_cardio": true
  },
  "origen_extraccion": "ia"
}
```

- `datos` se valida con `Identificacion` + `ExtraccionIA` de `esquemas.py` (mismos nombres, tipos y rangos; campos extra → 422).
- `origen_extraccion`: `"ia"`, `"simulado"`, `"manual"` o `null`.
- **No** recibe el relato completo ni el DNI.
- Guarda un evento nuevo `DATOS_INGRESO_REGISTRADOS` (no pisa los anteriores). El frontend lo manda al confirmar la medición y solo si los datos cambiaron.
- Respuestas: `201` con el evento · `422 DATOS_INGRESO_INVALIDOS` / `REGISTRO_INVALIDO` · `500 ERROR_REGISTRO`.

### Cambios en `GET /api/demo/espera`

Cada episodio suma dos campos:

| Campo | Qué es | Quién lo recibe |
|---|---|---|
| `motivo_categoria` | Categoría del último `DATOS_INGRESO_REGISTRADOS` (o `null`) | Todos |
| `dni` | DNI descifrado del paciente (o `null` si no se identificó) | Enfermería, médicos y **auditor** (el auditor se sumó el 23/10, acordado en el grupo, para cruzar con la historia clínica) |

- El DNI se obtiene con `dnis_de_pacientes()` (nuevo, en `identificacion.py`): solo lectura, verifica claves y que el DNI coincida con su índice.
- Si las claves fallan, la lista sale igual, sin DNI, y se registra `ERROR_DNI_ESPERA` en el log.
- Motivo: pedido del HRRG (en su triage se ve el DNI) y auditoría. **Acordado en el grupo el 23/10.** Para volver atrás alcanza con quitar roles del conjunto en `consultar_espera_demo`.
- El auditor ya podía leer el historial (`GET /api/demo/episodios/<ep>`) y la lista por paciente (`GET /api/demo/episodios?codigo_paciente=`): el frontend ahora los muestra (botón "Ver historial" y búsqueda por DNI con todas las atenciones, incluidas las finalizadas).

### Historial de casos — `GET /api/demo/episodios` (propuesta Barby 23/10, noche)

Sin cambios en los parámetros. Cada episodio suma campos (los anteriores siguen igual):

| Campo | Qué es | Quién lo recibe |
|---|---|---|
| `estado` | `en_ingreso` / `en_espera` / `finalizado` (o `null`) | Todos |
| `color_final` | Color de la última decisión registrada (o `null`) | Todos |
| `motivo_categoria` | Categoría del último `DATOS_INGRESO_REGISTRADOS` (o `null`) | Todos |
| `dni` | DNI del paciente (o `null`) | Enfermería, médicos y auditor (mismo criterio que la lista de espera) |

Lo usa la pantalla "Historial de casos" del auditor (todos los episodios, de a 50, filtrables por estado) y las atenciones anteriores.

### Exportar el historial de casos — `POST /api/demo/episodios/exportar` (propuesta Barby 23/10)

```json
{ "password": "<contraseña del auditor>", "formato": "excel", "estado": "finalizado",
  "desde": "2026-10-23T00:00:00-03:00", "hasta": "2026-10-24T00:00:00-03:00" }
```

- **Solo auditor** (los demás perfiles: `403 PERMISO_DENEGADO`). `estado`, `desde` y `hasta` son opcionales.
- **Vuelve a pedir la contraseña** del auditor (va en el cuerpo, nunca en la URL). Incorrecta → `401 PASSWORD_INCORRECTA` con los intentos que quedan; a la tercera → `403 EXPORTACION_BLOQUEADA` hasta cerrar sesión y volver a entrar.
- `formato: "excel"` → CSV para Excel (UTF-8 con BOM, `;`, coma decimal), una fila por episodio con el detalle completo.
- `formato: "pdf"` → tabla resumida en A4 apaisado (requiere `reportlab`, agregado a `requirements.txt`; si falta → `503 PDF_NO_DISPONIBLE`).
- **No incluye el DNI**: el paciente aparece con su código interno (`PAC-…`).
- Columnas del Excel: fecha de ingreso, episodio, código de paciente, profesional, estado, edad, sexo, categoría, motivo, tiempo de evolución, banderas rojas, antecedentes, última medición vigente, cantidad de mediciones y correcciones, color final, decisión, motivo de la decisión, quién y cuándo decidió, cantidad de decisiones, escalado a ROJO y fecha de finalización.
- Textos que empiezan con `= + - @` se exportan con `'` adelante (evita fórmulas en Excel).
- `sistema.log`: `EXPORTAR_CASOS | <usuario> | <formato> | <n> filas` y `EXPORTAR_PASSWORD_INCORRECTA | <usuario> | intento <n>`.
- El armado de los archivos está en `backend/src/exportacion.py` (archivo nuevo).

### Filtro por fecha (propuesta Barby 23/10)

`GET /api/demo/episodios` y la exportación aceptan `desde` (inclusive) y `hasta` (exclusivo), en ISO 8601 **con zona horaria** (por ejemplo `2026-10-23T00:00:00-03:00`). Se comparan en UTC con la fecha de creación del episodio. Fechas sin zona o `desde >= hasta` → `422`.
El frontend manda el día elegido desde las 00:00 hasta las 00:00 del día siguiente, en la hora de la compu.

### Exportación en Excel real (.xlsx) — propuesta Barby 26/10

`formato: "excel"` devuelve ahora un `.xlsx` (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) con tres hojas: **Resumen** (una fila por episodio, fechas y números como valores de Excel, filtro y color pintado), **Eventos** (una fila por evento con tipo, fecha de registro, profesional, fecha de la toma, registro corregido y detalle legible) e **Info** (usuario, fecha, filtros, avisos). Horas en UTC-03:00. Requiere `openpyxl` (si falta → `503 EXCEL_NO_DISPONIBLE`). `formato: "csv"` sigue disponible (una fila por evento). La columna DNI aparece solo si la ruta la agrega (decisión del grupo pendiente).

### Exportar un solo DNI · DNI enmascarado · archivo con la contraseña del auditor — propuesta Barby 26/10

El cuerpo de `POST /api/demo/episodios/exportar` suma un campo:

| Campo | Qué hace |
|---|---|
| `dni` (opcional) | Exporta **un solo paciente**: se busca su código con el índice cifrado (sin crear pacientes) y se exportan **todas sus atenciones**, sin aplicar `estado` ni fechas. DNI desconocido → `404 PACIENTE_NO_ENCONTRADO`. El DNI no se escribe en el log (se registra el código `PAC-…`). |
| — | El archivo se protege con la **misma `password` del auditor** (decisión 26/10: el auditor no comparte los archivos exportados). Excel: cifrado nativo de Office (`msoffcrypto-tool`), Excel la pide al abrir. PDF: AES-256 (`pikepdf`), el lector la pide al abrir. No se guarda en ningún lado. |

- En ambos formatos el **DNI sale enmascarado**: solo los últimos 3 números (`••.•••.222`).
- `formato` acepta `"excel"` o `"pdf"` (el CSV quedó fuera porque no se puede proteger con clave).
- Si falta una librería → `503 PROTECCION_NO_DISPONIBLE` con el comando para instalarla. Nuevas dependencias en `requirements.txt`: `msoffcrypto-tool`, `pikepdf`.


## 15. Propuestas del 28/10 (Barby) · a revisar por Maricel y el grupo

### Cancelar (anular) un caso cargado por error — `POST /api/demo/episodios/<codigo>/anular`

Entrada: `{"motivo": "Datos cargados por error. …", "version_esperada": 1}` (la versión de `GET …/estado`).

- Solo **enfermería y médicos** (el auditor no puede escribir).
- Solo si el episodio está **en ingreso o sin estado** y **no tiene una decisión registrada**. Si ya pasó a la lista de espera → `409 EPISODIO_NO_ANULABLE`.
- No borra nada: el estado pasa a **`anulado`** y se agrega el evento **`EPISODIO_ANULADO`** con `motivo`, `estado_anterior` y versión.
- Un caso anulado no aparece en `/api/demo/espera` ni en la sala, no acepta decisiones ni cambios de estado, y el auditor lo ve en el historial (filtro **Anulados**) y en la exportación.
- Errores: `400 CAMPOS_INVALIDOS`, `404 EPISODIO_NO_ENCONTRADO`, `409 VERSION_DESACTUALIZADA`, `409 EPISODIO_NO_ANULABLE`, `422 ANULACION_INVALIDA` (sin motivo).
- **Migración:** `estados_episodio` tiene un `CHECK` con los estados permitidos. Al arrancar, `inicializar_registro` rehace la tabla si no incluye `anulado`, copiando los datos (`_migrar_estado_anulado`). No hace falta borrar la base.

### Cierre de sesión por inactividad

- El servidor guarda `ultima_actividad` en la sesión. Si pasan **15 minutos** sin actividad (`HRRG_SESION_INACTIVIDAD_MIN`), la próxima consulta devuelve `401 SESION_VENCIDA` y se borra la sesión.
- Las consultas automáticas (lista de espera que se recarga sola, `sala.html?personal=1`) mandan el encabezado **`X-HRRG-Auto: 1`** y **no cuentan** como actividad. Antes, esas recargas renovaban la cookie y la sesión no vencía nunca.
- `GET /api/sesion` devuelve además `inactividad_min`.
- En el navegador (`api.js`): cuenta la actividad real (teclado, mouse, toques) de todas las pestañas, avisa 1 minuto antes con "Seguir conectado" y, al vencer, cierra la sesión y vuelve al ingreso con el aviso.

### Reglas del hospital — perfil `jefatura` y rutas `/api/reglas/...`

Perfil nuevo **`jefatura`** (Jefatura de Guardia): solo administra reglas; no accede a la atención (`403` en las rutas clínicas). Se asigna desde la administración o con `flask asignar-rol --rol jefatura`.

Base propia: `~/.hrrg_pp2/reglas_hospital.db` (tablas `reglas`, `reglas_eventos`, `reglas_config`).

| Ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/reglas/campos` | enfermería, médico, auditor, jefatura | Catálogo de datos que puede usar una regla y sus operadores |
| `GET /api/reglas/activas` | enfermería, médico, auditor, jefatura | Reglas activas + `usar_ejemplo` (lo usa el motor) |
| `GET /api/reglas` | auditor, jefatura | Todas, con su historial |
| `POST /api/reglas` | jefatura | Crear (queda en **borrador**) |
| `POST /api/reglas/<id>` | jefatura | Editar: vuelve a **borrador** y sube la versión |
| `POST /api/reglas/<id>/activar` · `/desactivar` | jefatura | Cambiar el estado |
| `POST /api/reglas/<id>/eliminar` | jefatura | Solo borradores que nunca se activaron |
| `POST /api/reglas/config` | jefatura | `{"usar_ejemplo": true/false}`: usar o no las reglas de ejemplo del equipo |

Formato de una regla:

```json
{
  "nombre": "Hipoxemia moderada",
  "explicacion": "SpO₂ menor a 94 % en paciente con antecedente respiratorio: riesgo de descompensación",
  "color": "NARANJA",
  "combinacion": "todas",
  "condiciones": [
    {"campo": "saturacion_o2", "operador": "<", "valor": 94},
    {"campo": "ant_resp", "operador": "si", "valor": null}
  ]
}
```

- `color`: `ROJO`, `NARANJA`, `AMARILLO` o `VERDE` (piso: la sugerencia no puede ser menor).
- `combinacion`: `todas` o `alguna`. Entre 1 y 8 condiciones.
- Operadores: numéricos `<`, `<=`, `>`, `>=`, `=`, `!=`; opciones `es`, `no_es`; sí/no `si`, `no`.
- Los campos son los de la pantalla de Medición (signos vitales, conciencia, dolor, edad, sexo, categoría del motivo, banderas rojas y antecedentes). **No** hay DNI ni relato.
- Validación en el servidor con mensajes en castellano (`422 REGLA_INVALIDA`).

**Motor (`frontend/js/motor_reglas.js`):** la sugerencia pide las reglas activas cada vez que se toca *Pedir sugerencia*, así una regla recién activada interviene en el próximo paciente. Las que se cumplen fijan un piso y aparecen en el "Por qué" con la marca **HRRG**. La decisión guardada agrega `Reglas HRRG aplicadas: R-001 v1 (NARANJA).` en el motivo. **Un dato que falta nunca cumple una condición.**
