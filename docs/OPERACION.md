# Operación, errores y reproceso

## Cargar y consultar

1. Ejecutar `iniciar.cmd` y entrar en la aplicación.
2. Pegar hasta 1.000 enlaces, uno por línea, o importar un Excel con URLs en su primera columna. La carga real no necesita una columna con el número esperado de registros.
3. Revisar Seguimiento: registrar el lote solo encola; `Completado` confirma la carga. `YaCargada` reutiliza una consulta publicada y `CompletadoSinDatos` confirma una respuesta completa sin Items.
4. En Ejecución del servicio, filtrar por lote o trabajo para ver intentos, HTTP, etapas y métricas. Abrir Observaciones para incidencias de calidad.
5. Registros XML permite explorar 39 campos y abrir la trazabilidad del documento. Modelo navega las relaciones normalizadas. Auditoría muestra cambios, cargas y accesos.

## Matriz de errores

| Situación | Comportamiento | Acción del operador |
| --- | --- | --- |
| URL de otro host/ruta o parámetros inválidos | Se rechaza la entrada antes de crear el lote | Corregir los enlaces señalados |
| Enlace repetido dentro del lote | Se omite el duplicado | Revisar el resumen de la carga |
| Consulta con versión válida | Trabajo `YaCargada`; no descarga | Administrador puede usar Forzar revisión si necesita comprobar cambios |
| Timeout, red caída, HTTP 408/429/5xx | Reintento con espera creciente, hasta cuatro fallos | Esperar o revisar el servicio; después usar Reintentar |
| HTTP 3xx, 4xx restante | Trabajo fallido, respuesta conservada si llegó completa y dentro del límite | Revisar URL/contrato; no se siguen redirecciones |
| HTTP nulo | No se recibió respuesta | Consultar error de red; nunca equivale a HTTP 200 |
| XML truncado o contrato/tipo inválido | No publica, revierte todo el detalle de esa carga y conserva bytes | Revisar Intento y corregir origen o contrato antes de reintentar |
| Unidad vacía/espacios, ausente o `xsi:nil` | `NULL` y Advertencia; carga completa | Consultar código de observación; no rellenar valores ficticios |
| `TipoActProy` distinto de 2/3 | Guarda detalle representable y observación Error; no normaliza ni publica | Revisar contrato/origen; conserva vigente la versión anterior |
| Respuesta demasiado grande | Falla sin tratar el contenido parcial como un XML completo | Ajustar `MAX_XML_BYTES` si corresponde y reintentar |
| Error SQL o bloqueo temporal | Revierte la transacción y programa reintento si SQL responde | Revisar log; ante caída del motor la cola se recupera por lease |
| Worker interrumpido | Lease de 10 min; al vencer, vuelve a cola y el intento queda Interrumpido | Reiniciar worker; no recrear el lote para recuperar la cola |
| Sesión vencida/API reiniciada | Solicita login | Volver a iniciar sesión |

## Reintentar y forzar revisión

Reintentar está disponible para Administrador y Operador en trabajos fallidos. Reinicia el presupuesto de cuatro fallos y conserva todos los intentos anteriores; sus números siguen creciendo. La auditoría del cambio registra el usuario y el rol.

Forzar revisión está disponible para Administrador en trabajos completados, sin datos, ya cargados o fallidos. Encola una descarga nueva. Una huella idéntica reutiliza el documento; una distinta crea una versión. La anterior permanece consultable, y solo se cambia la vigente si la nueva validación completa resulta correcta.

Para reprocesar respuestas históricas almacenadas tras migrar el MVP:

```powershell
.\uv.cmd run --frozen python scripts/backfill_plan.py
.\uv.cmd run --frozen python scripts/verificar_integridad.py
```

El backfill no hace solicitudes HTTP. Solo recupera trabajos fallidos cuyos documentos conservados tienen HTTP 200 y ahora superan el contrato. Mantiene el intento fallido y agrega otro para el reproceso. También completa el modelo histórico cuando falta. Repetirlo no agrega registros duplicados.

## Configuración y límites

Editar `.env` y reiniciar los procesos para aplicar cambios. `WORKER_CONCURRENCY` admite 1 a 20 (predeterminado 20). Un valor existente en `.env` tiene prioridad sobre ese predeterminado. Se conserva una única cola SQL con hasta 20 descargas en paralelo por worker; la inserción y normalización siguen coordinadas por el bloqueo global. `MEF_CIRCUIT_FAILURES=5` y `MEF_CIRCUIT_PAUSE_SECONDS=30` controlan la pausa automática ante errores transitorios. No constituyen una pausa manual de lote, que queda pendiente por decisión del usuario.

Abrir **Métricas de carga** para identificar descarga, espera SQL, validación, inserción y normalización. Filtrar por lote para evitar que ensayos separados distorsionen las tasas. La [guía de métricas](METRICAS.md) explica el P95 y cómo comparar 4, 8, 12 y 20 descargas. En instalaciones existentes, aplicar también `sql/006_metricas.sql` con respaldo y procesos detenidos.

La API utiliza una instancia de proceso; las sesiones no se comparten entre instancias. `COOKIE_SECURE=no` corresponde al HTTP local; si se sirve mediante HTTPS, usar `yes`. Las cuentas se administran en Usuarios y las contraseñas se guardan con Argon2.

Antes de una migración, detener API/worker y respaldar la base. Los scripts no purgan documentos, auditoría histórica ni datos anteriores. Los informes de ejecución y accesos tienen paginación; para grandes volúmenes conviene filtrar por lote/trabajo/documento.

Para actualizar dependencias se utilizan `uv` y `pnpm`, conservando sus lockfiles. Ejecuta `scripts/preparar.ps1` al clonar o después de cambiar dependencias. Tras modificar Vue, compila con `pnpm --dir frontend build` antes de usar `iniciar.cmd`. Para desarrollo con recarga de componentes utiliza `pnpm --dir frontend dev` junto con FastAPI en el puerto 8000.

## Ensayo de carga

`scripts/prueba_carga_local.py` requiere `MSSQL_DATABASE=ProInXML_Validacion`. Usa los parámetros de las URLs de `XML_models/URLs.xlsx`, SQL Server real y respuestas HTTP simuladas con un Item por documento; algunas unidades vienen vacías y una fracción de consultas falla una vez con HTTP 503. Simula un corte de lease, acelera únicamente las esperas de reintento del ensayo, repite el lote y compara detalle/modelo. Se conserva como herramienta de validación opcional; no forma parte del arranque ni se ejecuta automáticamente.

## Limpieza para repetir el laboratorio

1. Aplicar `sql/005_mantenimiento.sql` con una copia de seguridad y con API y worker detenidos; en una instalación nueva se incluye automáticamente al aplicar todos los scripts.
2. Entrar como Administrador y abrir **Mantenimiento**. Inspeccionar o filtrar documentos antes de elegir **Eliminar documento** o **Vaciar todas las cargas**. Los filtros de la tabla no limitan el vaciado global.
3. Revisar los conteos, indicar el motivo y escribir la confirmación exacta. Si hay trabajos en curso, esperar a que terminen y solicitar una nueva vista previa. Si el worker quedó interrumpido, volver a iniciarlo para que recupere sus leases; no se agregó pausa manual de lotes.
4. Eliminar un documento retira su respuesta, detalle, observaciones y hechos del modelo; se podan únicamente entidades sin referencias. Se conservan trabajos/intentos como historial, cancelando los trabajos vinculados. No se publica una versión anterior automáticamente. Para volver a cargar, registrar la URL en un lote nuevo.
5. Vaciar todas las cargas retira también lotes, consultas, trabajos e intentos y vacía el modelo. Conserva usuarios, roles, configuración del servicio, catálogo, auditoría y métricas de análisis. No equivale a eliminar la base ni reinicia IDs. Las bitácoras y métricas siguen conteniendo IDs históricos de documentos y lotes eliminados; el filtro de métricas conserva esos lotes.

La eliminación y el evento de auditoría forman una transacción: cualquier fallo revierte los cambios. Conservar las bitácoras implica que el tamaño de la base no vuelve a cero. Un resultado ambiguo por pérdida de conexión debe verificarse consultando nuevamente antes de repetir la operación.

No consulta al MEF. Sus tiempos miden ese conjunto sintético y la máquina local; no estiman cuánto tardarán ni cuánto ocuparán los XML reales. La validación externa completa consiste en importar el Excel real desde la interfaz y dejar terminar los lotes, revisando tasa de error, duración y tamaño de la base en ese entorno.
