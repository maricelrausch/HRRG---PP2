# Política de registros — prototipo HRRG

Estado: política de desarrollo del prototipo.
Pendiente de revisión del equipo y autorización institucional
antes de cualquier uso con datos reales.

## Alcance

Se almacenan únicamente episodios y datos ficticios.
El historial implementado comprende creación de episodios,
mediciones y correcciones de mediciones.

No representa todavía el historial completo del proceso de triage.

## Acceso

Las cuentas activas con rol medico o enfermeria pueden consultar
episodios, agregar mediciones y corregir valores registrados
por otros profesionales.

Las cuentas con rol auditor pueden consultar el historial,
pero no crear episodios, agregar mediciones ni corregirlas.

Flask verifica la sesión y el rol antes de ejecutar las rutas.
El autor se obtiene de la sesión; no se acepta desde el formulario.

## Autoría e historial

El episodio conserva la identidad de su creador.
Cada evento conserva la identidad de quien realizó esa acción.

Las correcciones se agregan como eventos nuevos.
Conservan el vínculo con la versión anterior, los valores anteriores,
los nuevos, la fecha de registro y el motivo.

No se ofrecen rutas para borrar eventos ni sobrescribir originales.
Esto no constituye protección contra modificaciones directas
del archivo SQLite por alguien con acceso al equipo.

## Fechas

medido_en indica cuándo se tomó la medición.
ocurrido_en indica cuándo se registró el evento en el servidor.

Las fechas se almacenan en UTC.
El frontend debe mostrarlas en la zona horaria local,
incluyendo la fecha cuando sea necesario.

## Almacenamiento

Los episodios y eventos se guardan localmente en:

~/.hrrg_pp2/triage_demo.db

Las cuentas se guardan en una base separada:

~/.hrrg_pp2/usuarios.db

Estos archivos no se suben al repositorio.
Tampoco se suben claves de sesión, contraseñas ni registros locales.

sistema.log contiene eventos técnicos y no reemplaza
el historial de episodios.

## Conservación y pendientes

Actualmente no hay eliminación automática de registros.
Las pruebas con bases temporales eliminan únicamente su propia base
al finalizar; no afectan la base utilizada por Flask.

Queda pendiente definir y aprobar:

- Plazos de conservación y procedimiento de eliminación.
- Copias de respaldo y recuperación.
- Protección del almacenamiento y permisos del equipo.
- Registro de quién consulta cada historial.
- Auditoría de extracción, fallos y decisiones profesionales.
- Alcance del acceso compartido para uso institucional.
- Revisión y aprobación del equipo.