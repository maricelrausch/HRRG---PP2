# Contrato de API — HRRG

Estado: propuesta para revisión de Bárbara, Tomás, Darío y Maricel.
Versión propuesta del contrato: 0.2.

La autenticación y las rutas de episodios están implementadas.
POST /api/extraer está pendiente de implementación en D03.

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

### GET /api/sesion

Respuesta correcta: HTTP 200.

```json
{
  "ok": true,
  "usuario": "prueba_enfermeria",
  "nombre": "Enfermería de prueba",
  "rol": "enfermeria"
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

Para la extracción se propone usar el formato de DatosTriage:

^[A-Z]{2,4}-[A-Z0-9-]{3,20}$

Ejemplos: PAC-DEMO-001 y EPI-DEMO-001.

En las pruebas los códigos se suministran explícitamente.
La generación automática definitiva queda pendiente de acuerdo.

Rutas disponibles:

- POST /api/demo/episodios:
  recibe codigo_paciente y codigo_episodio;
  crea un episodio asociado al profesional de la sesión.
- GET /api/demo/episodios/<codigo_episodio>:
  consulta un episodio del propio profesional y su historial.

La validación actual de estas rutas admite textos de 1 a 100
caracteres; su unificación con el patrón de DatosTriage está pendiente.

El auditor no puede crear episodios.
La consulta global para auditoría todavía no está implementada.

## 4. Extracción propuesta — D03

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

Reglas de entrada propuestas:

- Los tres campos son obligatorios y deben ser textos.
- No se aceptan campos adicionales.
- Los códigos deben cumplir el patrón de la sección 3.
- texto debe tener entre 1 y 5000 caracteres después de quitar
  espacios al principio y al final.
- Un texto vacío o con formato inválido devuelve HTTP 422.

Esta ruta no crea episodios ni guarda decisiones en D03.
Devuelve los códigos recibidos para vincular la respuesta.
No comprueba todavía que esos códigos existan en el registro.

La futura integración con el modelo recibirá únicamente el relato,
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

## 6. Respuesta de extracción propuesta

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
  "codigo": "CASO_SIMULADO_NO_ENCONTRADO"
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

### Crear un episodio

POST /api/demo/episodios

Entrada:

```json
{
  "codigo_paciente": "PAC-DEMO-001",
  "codigo_episodio": "EPI-DEMO-001"
}
```

Respuesta correcta: HTTP 201, con ok, modo y episodio.

Se registra automáticamente el evento EPISODIO_CREADO.
Un código de episodio duplicado devuelve HTTP 409.

Actualmente esta ruta acepta identificadores de texto de entre
1 y 100 caracteres, luego de quitar espacios exteriores.
La unificación con el patrón de /api/extraer está pendiente.

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

No existe todavía una ruta para listar todos los episodios
de un paciente por codigo_paciente.

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

POST /api/extraer sigue devolviendo una respuesta simulada.
Actualmente no crea episodios ni guarda automáticamente eventos
de extracción, mediciones o correcciones.