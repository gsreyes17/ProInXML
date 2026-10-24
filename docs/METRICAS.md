# Métricas de carga

La pantalla **Métricas de carga** (`/ui/metricas`) se actualiza cada tres segundos y está disponible para los tres roles. Permite filtrar por lote, concurrencia registrada y resultado, consultar promedios/P95, comparar rendimiento y abrir el detalle de cada intento.

El límite de entrada manual es **1.000 URLs por lote**. El worker usa **8 descargas simultáneas por defecto**, configurable con `WORKER_CONCURRENCY=1..20` en `.env`; reinicia los procesos para aplicar el cambio. Son trabajadores sobre una misma cola SQL, no colas independientes. Si `.env` conserva un valor anterior, ese valor tiene prioridad.

## Qué se mide

Cada intento nuevo crea una fila en `analisis.MetricaIntento`. Las duraciones se miden con reloj monotónico y se almacenan en milisegundos, con tres decimales. La interfaz convierte automáticamente a segundos cuando corresponde.

| Columna | Alcance |
| --- | --- |
| `DescargaMs` | Creación del cliente HTTP, conexión, respuesta, lectura completa del cuerpo y cierre; también se mide si falla |
| `OriginalMs` | Huella, compresión y transacción que conserva el original; incluye sus esperas SQL y confirmación |
| `EsperaSqlMs` | Adquisición de bloqueos de integración, normalización, trabajo y consulta en la transacción de detalle |
| `ValidacionMs` | Lectura de Items y validación del contrato, acumulada por bloques de hasta 500 filas |
| `InsercionMs` | Preparación de valores e inserción de los bloques del detalle mediante ODBC |
| `NormalizacionMs` | Ejecución de la normalización del documento en SQL Server |
| `ConfirmacionMs` | Confirmación y cierre de la transacción de detalle; no incluye la confirmación del original |
| `TotalMs` | Tiempo desde que el worker comienza el intento hasta preparar la medición final, incluidas tareas administrativas y gestión del fallo |

El total no tiene que coincidir con la suma de las fases: también hay conexiones SQL, consultas de metadatos, observaciones, publicación, auditoría y persistencia intermedia de métricas. La espera del trabajo antes de ser tomado, el backoff entre reintentos y la pausa del circuito no son fases de ese intento. `EsperaSqlMs` no es un diagnóstico de todos los bloqueos internos del motor; una espera durante una sentencia puede estar incluida en inserción, normalización u original.

Un guion (`NULL`) indica que no se ejecutó la fase; cero significa que se midió una duración muy pequeña. Promedio y P95 excluyen las mediciones interrumpidas/incompletas y los NULL de cada fase. P95 es el percentil 95 de la muestra, calculado mediante interpolación: requiere suficientes observaciones para sacar conclusiones. Los filtros pueden incluir tanto éxitos como errores; filtra por resultado para comparar un grupo homogéneo.

## Conteos y rendimiento

- `RegistrosLeidos`: Items entregados por el lector, incluso si un error posterior revierte la carga. Un Item que no logra superar la validación no llega a contarse como leído.
- `RegistrosInsertados`: filas nuevas cuya transacción se confirmó; una inserción revertida cuenta cero.
- `RegistrosReutilizados`: filas ya presentes; no se presentan como filas nuevas por segundo.
- `RegistrosNormalizados`: filas del documento normalizado durante ese intento confirmado. Un error de calidad conserva el detalle representable, pero cuenta cero normalizadas.
- `BytesRecibidos`: bytes entregados por HTTP al consumidor, incluidos los recibidos antes de un fallo. No mide tráfico comprimido exacto en la red.
- XML/minuto: intentos completados, incluyendo respuestas válidas sin Items, divididos por la ventana de tiempo real seleccionada.
- Filas/segundo: filas nuevas confirmadas divididas por esa misma ventana. Puede incluir detalle conservado de documentos rechazados por calidad; no equivale a filas publicadas.

La ventana va del primer inicio al último final (o al momento actual si hay intentos en curso), por lo que incluye intervalos y reintentos entre intentos seleccionados. Las duraciones de trabajadores paralelos no se suman para calcular rendimiento. Conviene filtrar por lote: seleccionar ensayos separados por horas reduce artificialmente la tasa respecto a cada ejecución individual.

Se registra la **concurrencia configurada del worker**, no el número de descargas activas en cada instante. La API muestra además su configuración actual como referencia; si API y worker usan entornos diferentes, pueden discrepar. Reintentos de una URL producen mediciones diferentes. Un trabajo `YaCargada` no descarga ni crea intento nuevo.

## Persistencia y fallos

La medición tiene una transacción independiente del documento: registra el inicio, una actualización tras guardar el original y el resultado final. Los tiempos de validación/SQL se hacen visibles al terminar, no en cada bloque de filas. Un fallo de observabilidad se registra en el log y no vuelve fallida una carga correcta. Si SQL está caído, no se garantiza recuperar mediciones que no llegaron a guardarse.

Al recuperar un lease vencido se marca la medición pendiente como `Interrumpido`, se conserva el desglose parcial y se estima el total con las marcas UTC. `MedicionFinalizada=0` evita mezclar esa estimación con los promedios/P95 de mediciones monotónicas completas.

Los intentos anteriores a esta instrumentación siguen en Ejecución del servicio; no se les inventa un desglose. Mantenimiento conserva las métricas, sus IDs y el nombre del lote incluso al eliminar todas las cargas. Esos identificadores históricos no tienen FK. Las identidades de las cargas no se reinician.

Para actualizar otra instalación, detener API/worker, respaldar y aplicar:

```powershell
.\uv.cmd run --frozen python scripts/aplicar_sql.py sql/005_metricas.sql
```

La migración es aditiva y repetible. La cuenta SQL de aplicación puede leer, insertar y actualizar métricas, y tiene denegado borrarlas o alterar su esquema.

## Comparar concurrencias

1. Elegir un conjunto pequeño de URLs de tamaños variados pero conocidos; anotar XML, filas y tamaño. Usar conjuntos equivalentes para las comparaciones.
2. Configurar `WORKER_CONCURRENCY=4`, reiniciar y ejecutar el lote. Esperar a que termine y anotar filas/s, XML/min, P95 total, errores y fase dominante.
3. Repetir con 8, 12 y 20. Para medir la carga completa de los mismos documentos hay que retirarlos antes desde Mantenimiento, que conserva las métricas, o usar una base de laboratorio independiente. Reingresar URLs publicadas genera `YaCargada`; forzar revisión con la misma respuesta mide reutilización, no una inserción nueva.
4. Comparar por lote y concurrencia, con el mismo estado y tamaños similares. Una mejora del promedio sin mejora de filas/s puede significar que cambió el tamaño de la muestra.
5. Si aumenta la espera SQL sin aumentar filas/s, bajar concurrencia; si domina normalización o inserción, estudiar esas consultas/índices antes de añadir más descargas. Vigilar también CPU, memoria, disco y tasa de error HTTP.

La inserción y normalización siguen serializadas por el bloqueo global existente. Subir de 4 a 20 puede ocultar latencia de red, pero no garantiza multiplicar el rendimiento y puede aumentar la memoria usada por documentos en espera. El límite sigue siendo 32 MiB por respuesta, además de copias, objetos del lector y buffers; no es un límite global de memoria. Se mantienen tiempos de espera y circuito automático ante fallos del servicio.

La validación del cambio utilizó SQL Server real con 20 descargas **simuladas** concurrentes y un XML de prueba por trabajo. Comprueba funcionamiento y medición; no predice el rendimiento de seis o siete millones de registros reales.
