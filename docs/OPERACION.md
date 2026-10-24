# Operación y configuración

## Configurar la conexión

Copiar `.env.example` como `.env` en una instalación nueva. Para SQL Server local con autenticación Windows: `MSSQL_TRUSTED_CONNECTION=yes`. Para una cuenta SQL: usar `no` y completar `MSSQL_USER` y `MSSQL_PASSWORD`. La instalación requiere permisos para crear base, tablas, procedimientos y roles; `proinxml_app` define los permisos de una cuenta de ejecución.

El instalador respeta `MSSQL_DATABASE`; también admite `--base-datos Nombre`. Los SQL escritos para SSMS apuntan a `ProInXML`; el instalador adapta el nombre. No crear el usuario administrador otra vez al actualizar una instalación existente.

| Variable | Referencia |
| --- | --- |
| `WORKER_CONCURRENCY` | 8; admite 1 a 20 |
| `WORKER_POLL_SECONDS` | 5 segundos sin trabajo pendiente |
| `MAX_XML_BYTES` | 32 MiB por respuesta |
| `MEF_CIRCUIT_FAILURES` | 5 fallos transitorios consecutivos |
| `MEF_CIRCUIT_PAUSE_SECONDS` | 30 segundos de pausa automática |
| `SESSION_SECONDS` | 28.800 segundos |
| `COOKIE_SECURE` | `no` para HTTP local, `yes` al servir HTTPS |

Reiniciar API y worker para aplicar cambios de entorno. La descarga mantiene conexión de 10 s, lectura de 45 s y presupuesto total de 180 s comprobado entre bloques. El lease es de diez minutos y el bloqueo de normalización espera hasta 60 s. Aumentar ese último tiempo no aumenta por sí solo la capacidad SQL.

## Cargar y revisar

1. Abrir Carga de datos y pegar hasta 1.000 URLs o importar un XLSX con URLs en la primera columna. El encabezado es opcional; no se exige año ni conteo en otras columnas. El Excel admite 50.000 filas y 10 MiB.
2. Seguimiento muestra el resultado por trabajo y sus registros. Registrar el lote solo encola; `Completado` confirma persistencia. `CompletadoSinDatos` confirma un XML completo sin Items.
3. Ejecución del servicio muestra cada intento, HTTP y error; Métricas permite comparar fases y concurrencia. Revisar por lote para no mezclar ensayos separados por largos intervalos.
4. Registros XML y Modelo 3FN consultan los datos; Observaciones permite abrir el valor afectado y el original. Auditoría conserva cambios, cargas y accesos.

La cantidad de URLs y los workers son independientes: ocho workers pueden procesar un lote de mil URLs.

## Errores y reintentos

| Situación | Resultado |
| --- | --- |
| URL no permitida | Rechazo antes de registrar el lote |
| Consulta ya publicada | `YaCargada`, sin descargar otra vez |
| Red/timeout, HTTP 408/429/5xx | Hasta cuatro fallos, con espera creciente y variación aleatoria |
| HTTP restante distinto de 200 | Fallo para revisión; se conserva la respuesta completa si se recibió |
| XML truncado, contrato o tipo inválido | Conserva original y revierte el detalle del documento |
| Unidad de medida vacía/ausente/nil | NULL y advertencia; permite completar |
| TipoActProy distinto de 2/3 | Conserva detalle representable con Error; no normaliza ni publica |
| Worker interrumpido | Recupera por lease y conserva el intento como Interrumpido |
| Fallo SQL | Revierte la transacción; reintenta si puede marcar el fallo |

HTTP NULL significa que no se recibió una respuesta con cabeceras; no implica HTTP 500. Los fallos transitorios recuperados permanecen en el historial aunque el trabajo termine completado. La cuenta `sistema` identifica al worker y no permite login.

Administrador y Operador pueden reintentar trabajos fallidos. Administrador puede forzar revisión de una consulta publicada: una huella idéntica reutiliza el documento; una distinta conserva una versión nueva. El historial de intentos nunca se reinicia.

## Limpiar el laboratorio

Administrador puede eliminar un documento o vaciar las cargas desde Mantenimiento. Requiere vista previa, motivo y confirmación exacta. Una vista previa obsoleta o un trabajo en curso impiden la operación. Si quedó un lease pendiente, iniciar el worker para recuperarlo; la pausa manual de lotes sigue pendiente.

Eliminar un documento retira original, detalle, observaciones y hechos, y poda entidades sin referencias. Conserva intentos y cancela los trabajos vinculados. Si era vigente, la consulta queda sin documento publicado; no se promociona una versión anterior.

Vaciar las cargas elimina también lotes, consultas, trabajos e intentos. Se conservan cuentas, roles, servicio, catálogo, auditoría y análisis. La operación y su evento de auditoría forman una transacción. No se usa TRUNCATE ni se reinician IDs. Las métricas y bitácoras retenidas siguen ocupando espacio.

## Actualizar y diagnosticar

Detener los procesos y respaldar la base antes de aplicar SQL. Preparar dependencias y ejecutar `scripts/aplicar_sql.py`; no vacía datos. La aplicación guarda logs del worker y Vue en `.runtime/worker.log` y `.runtime/vue.log`. Para las pruebas y herramientas opcionales, ver [VALIDACION.md](VALIDACION.md).
