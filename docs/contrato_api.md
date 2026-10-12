# Contrato de API — HRRG

Estado: borrador para revisión del equipo.
Las rutas de extracción todavía no están implementadas.

## 1. Autenticación disponible

- POST /api/login: inicia sesión con usuario y password.
- GET /api/sesion: devuelve el usuario de la sesión activa.
- POST /api/logout: cierra la sesión del cliente. Recibe {} como JSON.

Las cuentas se administran desde la terminal.
No existe registro público de profesionales.

Las API del proceso de triage requieren una sesión válida.

## 2. Identificación y trazabilidad

Cada proceso de triage debe vincularse con:

- codigo_paciente: código interno del paciente.
- codigo_episodio: identificador de una atención concreta.
- Profesional responsable: obtenido por Flask desde la sesión.
- Fecha y hora de los eventos: generadas por el backend.

Un paciente puede tener varios episodios.

Pendiente de acordar: quién genera el código de episodio.

## 3. Extracción propuesta

POST /api/extraer
Content-Type: application/json

Entrada propuesta, pendiente de revisión del equipo:

{
  "codigo_paciente": "PAC-DEMO-001",
  "codigo_episodio": "EPI-DEMO-001",
  "texto": "Paciente ficticio de 42 años con dolor de tobillo."
}

Los identificadores se tratarán como texto para conservar ceros
iniciales y posibles letras.

El backend enviará a la función de extracción solamente el relato
necesario, sin credenciales ni identificadores del paciente.

## 4. Respuesta de extracción

Pendiente de acordar con Darío y Tomás:

- Campos clínicos, tipos y unidades.
- Representación de valores desconocidos.
- Estructura de faltantes y advertencias.
- Identificación del modelo y de la versión del esquema.
- Forma de distinguir una respuesta simulada de una real.

Una falla no debe devolver una extracción simulada como si fuera real.
La extracción no asignará por sí sola una prioridad Manchester.

## 5. Formato común de errores

{
  "ok": false,
  "mensaje": "Descripción del problema.",
  "codigo": "IDENTIFICADOR_DEL_ERROR"
}

Estados previstos:

- 400: solicitud mal formada.
- 401: sesión requerida o credenciales inválidas.
- 415: formato de contenido no admitido.
- 422: contenido que no cumple el esquema acordado.
- 502: respuesta inválida del servicio de IA.
- 503: servicio no disponible.
- 504: tiempo de espera de la IA agotado.

Los errores de integración se implementarán al conectar los servicios.

## 6. Persistencia y auditoría requeridas

Debe conservarse el proceso de triage asociado al paciente,
al episodio y al profesional, incluyendo las correcciones
y la decisión profesional.

El registro técnico sistema.log no reemplaza esta auditoría.

El guardado actual del formulario es provisional y no representa
todavía el historial completo del proceso.

Pendiente: estructura de almacenamiento, permisos, conservación
y registro de cambios.