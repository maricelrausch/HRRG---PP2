# Preparación de la identificación cifrada

Ejecutar los comandos desde la carpeta backend, con Flask detenido.

## Instalar las dependencias

```powershell
# Instala las dependencias del proyecto en el entorno Python elegido.
python -m pip install -r requirements.txt
```

## Instalación nueva o configuración ya migrada

```powershell
# Crea las claves si corresponde o verifica las existentes.
python scripts/preparar_identificacion.py
```

## Actualización de una base con DNI sin cifrar

```powershell
# Crea un respaldo verificado y migra las identificaciones.
python scripts/preparar_identificacion.py --migrar
```

La migración conserva los códigos de paciente.
No modifica los episodios ni sus eventos.

## Iniciar el servidor

Solo continuar si la preparación termina correctamente.

```powershell
# Inicia el prototipo local.
python -m flask --app app run --port 5001
```

## Archivos locales

- Base: ~/.hrrg_pp2/triage_demo.db
- Claves: ~/.hrrg_pp2_claves/identificacion.json
- Respaldos: ~/.hrrg_pp2/respaldos/

Cada instalación independiente utiliza sus propias claves.
No publicar claves, bases ni respaldos en Git.

Conservar un respaldo de las claves separado del respaldo de la base.
Una base cifrada necesita las claves con las que fue preparada.
No borrar ni regenerar las claves para resolver un error.

Los respaldos anteriores a la migración contienen DNI sin cifrar.
El cifrado implementado protege el DNI en la tabla de identificación;
no cifra toda la base de datos ni sus respaldos anteriores.

Estar fuera del repositorio no configura permisos de acceso del sistema
operativo.

## Alcance

Este preparador configura la identificación de pacientes.
Las cuentas de profesionales se administran mediante los comandos
existentes del proyecto.