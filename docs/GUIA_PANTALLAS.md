# Guía de pantallas y acciones de ProInXML

Este documento describe las opciones que aparecen en la interfaz actual. **Consultar** y **Limpiar filtros** solo leen datos; las acciones que modifican la base se indican expresamente.

## Acceso y navegación

| Rol | Puede hacer |
| --- | --- |
| Consulta | Ver seguimiento, ejecución, métricas, registros XML, modelo y observaciones. |
| Operador | Lo anterior, además de registrar cargas y reintentar trabajos fallidos. |
| Administrador | Todas las opciones, incluidas revisión forzada, auditoría, usuarios y mantenimiento. |

**Entrar** comprueba usuario, contraseña y estado activo. La sesión dura una hora por defecto; el contador `HH:MM:SS` indica cuánto falta. **Salir** invalida la sesión. Los tres menús laterales se despliegan de uno en uno y el botón de la barra superior contrae o expande el sidebar.

En las tablas con filtros, **Consultar** aplica los criterios, **Limpiar** los borra y **Anterior/Siguiente** cambia de página. La paginación no modifica registros. Los números de **documento**, **trabajo**, **lote** y **registro** identifican cosas diferentes.

## Procesamiento

### Carga de datos

| Opción | Qué hace |
| --- | --- |
| Pegar enlaces y **Cargar datos** | Valida de 1 a 1.000 URLs, crea un lote y deja sus trabajos en la cola SQL. Registrar el lote no significa que los XML ya estén descargados. |
| **Usar ejemplo** | Coloca una URL de muestra en el campo; solo se procesa si después pulsas **Cargar datos**. |
| Seleccionar archivo y **Importar Excel** | Lee las URLs de la primera columna de un `.xlsx`, de la hoja `XML` o de la hoja activa. Admite hasta 50.000 filas; las celdas vacías y un encabezado reconocido se omiten. |
| **Cargas recientes** | Abre el seguimiento de una de las últimas ocho cargas. |

Antes de registrar un lote se validan todas las URLs. Las consultas repetidas dentro de la entrada se unifican; si una consulta ya tiene un documento válido publicado, queda como **YaCargada** sin volver a descargar. El worker procesa después los demás trabajos.

### Seguimiento

| Opción | Qué hace |
| --- | --- |
| **Seleccionar carga** | Muestra el avance y los trabajos de ese lote. La cola puede estar procesando otro lote mientras este espera. |
| **Actualizar** | Solicita el estado en ese momento; la pantalla también se actualiza aproximadamente cada tres segundos. |
| **Estado de enlaces** | Filtra la tabla por pendiente, en curso, completado, sin datos, ya cargado o fallido. |
| **Ver datos** | Muestra una muestra paginada de las filas del documento asociado al trabajo. |
| **Reintentar** | Disponible para Operador y Administrador si el trabajo quedó **Fallido**. Reinicia su contador operativo y lo devuelve a **Pendiente**; conserva el historial de intentos. |
| **Forzar revisión** | Disponible para Administrador en trabajos terminados. Encola otra descarga aunque ya exista un documento válido; si la nueva respuesta falla, la versión válida anterior sigue publicada. |
| **Ver intentos** | Abre Ejecución del servicio filtrada por ese trabajo. |
| **Inspeccionar respuesta** | Muestra el documento recibido, su estado, calidad y una vista previa del contenido guardado. |

**Reintentar** y **Forzar revisión** ponen un trabajo en la cola; no lo ejecutan dentro de la petición del botón. Los estados `CompletadoSinDatos` y `YaCargada` cuentan como finalizados, aunque el primero tenga cero Items y el segundo reutilice datos.

### Ejecución del servicio

Permite filtrar por lote, trabajo, HTTP, resultado o **Solo fallos e interrupciones**. Cada fila representa un **intento**, con hora de inicio y fin, etapa, código HTTP, error y conteos de registros. Una URL puede tener varios intentos: por ejemplo, HTTP 500 seguido de HTTP 200. **Sin respuesta HTTP** significa que no se registró un código, no que el servicio devolvió 500. **Inspeccionar respuesta** abre el cuerpo guardado si existe.

### Métricas de carga

Filtra por lote, concurrencia registrada y resultado. **Actualizar** vuelve a consultar; también hay actualización periódica. Muestra XML completados por minuto, filas nuevas por segundo, promedio y P95, tiempos por etapa, comparación de concurrencia y los intentos más lentos. Abrir un intento muestra su desglose. Estas métricas son de observación: no cambian el número de workers ni reprocesan documentos. Intentos anteriores a la instrumentación pueden aparecer sin desglose.

## Consultas

### Registros XML

**Última versión por consulta** muestra documentos vigentes; **Todas las versiones** incluye documentos anteriores. **Solo XML · 39 campos** presenta las columnas recibidas, mientras **XML con identificadores** añade trazabilidad. Se puede filtrar por año, ejecutora, proyecto, documento o registro. Abrir una fila muestra los 39 valores, su documento de origen y enlaces hacia el gasto del modelo y las observaciones. Esta pantalla no edita el XML.

### Modelo 3FN

**Explorar tabla** permite elegir las entidades agrupadas o la tabla final **Gasto**. Se puede buscar código o valor, filtrar por identificador, abrir el detalle de una fila y seguir las claves foráneas hacia sus tablas relacionadas. **Quitar filtro de relación** vuelve a mostrar la tabla completa. Los enlaces al registro XML permiten comparar la representación normalizada con el origen. Esta pantalla es de solo lectura y puede mostrar entidades de documentos históricos.

### Observaciones

Filtra por documento, campo, código y severidad (`Info`, `Advertencia`, `Error`). Cada fila señala el Item o campo que produjo una observación. **Ver dato observado** abre el documento y, cuando corresponde, resalta el valor de origen. Una advertencia, como `Unidad_Medida` vacía, no equivale por sí sola a un documento rechazado.

## Administración

### Auditoría

| Pestaña | Qué muestra |
| --- | --- |
| **Cambios de registros** | Altas, modificaciones y eliminaciones auditadas, con actor, rol y comparación **Antes/Después**. |
| **Cargas por documento** | Resultado, HTTP, cantidad de registros y filas insertadas o reutilizadas. Permite filtrar documentos sin datos, con datos, rechazados o eliminados. |
| **Eventos de acceso** | Intentos de inicio de sesión y salidas, exitosos o fallidos. |

**Ver respuesta guardada** abre la evidencia conservada por ProInXML. **Abrir XML de origen** visita la URL actual del MEF; el origen puede haber cambiado o estar caído, por lo que la evidencia histórica es la respuesta guardada. La vista previa del original se limita a los primeros 64 KiB.

### Usuarios

**Guardar usuario** crea una cuenta o actualiza la cuenta seleccionada con **Editar**. Se pueden cambiar nombre, rol, contraseña y estado **Cuenta activa**; dejar la contraseña vacía al editar conserva la actual. **Nueva cuenta** limpia el formulario. Cambiar una cuenta existente invalida sus sesiones. La identidad `sistema` está reservada al worker y no se edita. No hay botón para borrar usuarios.

### Mantenimiento

La tabla **Documentos recibidos** permite filtrar por documento, año, ejecutora, HTTP y calidad. **Inspeccionar** abre la respuesta guardada. Las otras opciones tienen efectos distintos:

#### Reconstruir modelo

Actúa **solo sobre el documento elegido**. Comprueba que exista, que haya superado la validación y que `staging.Gasto` contenga exactamente la cantidad de filas declarada en el documento. Después vuelve a ejecutar la normalización SQL: crea las entidades que falten e inserta o actualiza las filas correspondientes de `modelo.Gasto`. Comprueba que el número final de hechos coincida con el detalle XML y registra la operación en `auditoria.Cambio`.

Usa esta acción si el detalle XML ya está guardado pero necesitas regenerar o verificar su representación normalizada, por ejemplo tras corregir el procedimiento de normalización. **No vuelve a llamar al MEF, no cambia la respuesta original y no corrige un XML rechazado.** Si la validación o los conteos no coinciden, la operación se rechaza sin publicar una reconstrucción parcial. El mensaje final muestra filas XML, filas del modelo antes y después.

#### Eliminar documento

**Eliminar documento** primero abre una vista previa con los conteos y la URL. Para confirmar se exige un motivo de al menos cinco caracteres y escribir exactamente `ELIMINAR DOCUMENTO <id>`. Elimina el original, sus filas en `staging`, sus hechos en `modelo` y sus observaciones; las entidades del modelo que queden sin referencias se podan. Los trabajos asociados pasan a **Cancelado** y se conservan como historial junto con sus intentos. Si era el documento vigente, la consulta queda sin publicación; no se reactiva automáticamente una versión anterior.

#### Vaciar todas las cargas

**Vaciar todas las cargas** también exige vista previa, motivo y la frase exacta `VACIAR CARGAS`. Elimina los lotes, consultas, trabajos, intentos, documentos, observaciones, detalle XML y modelo de las cargas. **Conserva usuarios, roles, configuración del servicio, auditoría y métricas; tampoco reinicia los identificadores.** No equivale al script manual `sql/099_vaciar_base.sql`, que tiene otro alcance.

Ambas eliminaciones son definitivas. El sistema las bloquea si hay trabajos `EnCurso` o si los datos cambiaron desde la vista previa. Ninguna de estas opciones repara una base con errores físicos de lectura o escritura.

## Qué acción elegir

| Situación | Opción |
| --- | --- |
| Un XML devolvió un fallo temporal y agotó intentos | **Seguimiento → Reintentar**. |
| Quieres consultar de nuevo una URL ya completada | **Seguimiento → Forzar revisión** (Administrador). |
| El XML válido está guardado, pero falta su representación en `modelo` | **Mantenimiento → Reconstruir modelo**. |
| Quieres demostrar por qué un XML tiene cero registros | **Auditoría → Cargas por documento → Ver respuesta guardada**. |
| Quieres retirar solo una respuesta de prueba | **Mantenimiento → Eliminar documento**. |
| Quieres repetir todas las cargas del laboratorio | **Mantenimiento → Vaciar todas las cargas**. |

Para el flujo interno de la cola, las transacciones y los reintentos, consulta [Flujos del sistema](FLUJOS_SISTEMA.md).
