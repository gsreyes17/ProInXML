# Validación

## Preparación para repositorio y migración Vue

Fecha: 23 de octubre de 2026. Windows, Python 3.11.9, uv 0.13.5, Node 26.5.1, pnpm 11.18.0, Vue 3.5.44, Vite 8.3.5, SQL Server Developer 17.0.1000.7 y ODBC Driver 18.

| Comprobación | Resultado |
| --- | --- |
| uv.lock y sincronización del venv existente | Correctos |
| pnpm-lock.yaml e instalación congelada | Correctos |
| TypeScript (`vue-tsc --noEmit`) y compilación Vite | Aprobados |
| Pruebas Python sin SQL | 34 aprobadas; 14 SQL omitidas por configuración |
| Prueba SQL seleccionada con un archivo XML | Aprobada con rollback en ProInXML_Validacion |
| Navegador Edge, frontend compilado servido por FastAPI | Aprobado |
| Modo desarrollo Vite y proxy hacia FastAPI | Aprobado; rutas SPA y respuesta 401 de la sesión protegida |
| Seguimiento automático HTTP 500 → HTTP 200 | Aprobado con un XML simulado y actualización cada 3 segundos |
| Navegación entre pantallas sin recargar documento | Aprobada |
| Cancelación de polling al salir de Seguimiento | Aprobada |
| XML, trazabilidad, FK, auditoría, ejecución, observaciones y usuarios | Aprobados |
| Móvil de 390 px | Sin desbordamiento horizontal de la página |

La suite contiene 48 pruebas en total. En esta preparación se ejecutaron las 34 que no necesitan SQL y una de las 14 de integración, para limitar el trabajo a un archivo XML. No se repitió la prueba masiva.

La prueba seleccionada utiliza `tests/fixtures/mef_partial_fixture.xml`: siete Items completos de la muestra, con la raíz cerrada para pruebas. No representa una descarga completa del MEF. Inserta, normaliza y compara los 39 campos, comprueba la política de auditoría y revierte la transacción.

QA visual realiza login/logout real y consultas a la base existente. Las modificaciones de lotes, el fallo HTTP, la recuperación y las acciones manuales son simulados en el navegador; no crea lotes reales ni descarga XML. Los eventos reales de acceso sí se registran. Evidencias locales: `.runtime/qa_vue.json`, `preview.log` y capturas `vue-*.png`.

La compilación genera páginas separadas por carga diferida. En la medición actual, el JavaScript principal comprimido ocupa aproximadamente 43,2 kB y el CSS 4,85 kB; las pantallas se cargan según la ruta. Los tamaños pueden cambiar con futuras modificaciones.

## Integridad de los datos existentes

`scripts/verificar_integridad.py` se ejecutó en modo de lectura sobre la base real:

| Medida | Resultado |
| --- | --- |
| Tablas del proyecto | 44, más dbo.sysdiagrams de SSMS |
| Documentos almacenados / válidos | 18 / 16 |
| Filas en detalle / modelo | 23.091 / 23.091 |
| Unidades NULL / observaciones | 71 / 71 |
| Columnas de datos.vw_GastoXML | 39 |
| Diferencias de reconstrucción, en ambos sentidos | 0 |
| Huellas incorrectas tras descomprimir | 0 |
| Estado de los trabajos | 16 Completado y 1 YaCargada |

Las cifras son una fotografía de validación; las cargas del usuario pueden incrementarlas. No se modificó el esquema SQL durante la migración a Vue. La evidencia se guarda en `.runtime/validacion_actual.json`, excluida del repositorio.

## Evidencias de la implementación anterior del backend

Antes de migrar el esquema se creó `.runtime/backups/ProInXML_antes_plan_definitivo.bak` mediante COPY_ONLY y CHECKSUM y se verificó con RESTORE VERIFYONLY. El respaldo se conserva localmente y no debe formar parte del repositorio.

La instalación desde cero y reaplicación de los cuatro SQL se verificó en ProInXML_Validacion, con archivos dentro de `.runtime/validacion_sql`: 44 tablas, todas con CreadoUtc y vista XML de 39 columnas. La batería anterior de 47 pruebas pasó incluyendo concurrencia, lease, roles, auditoría, errores, unidades nulas, idempotencia y versiones.

También se recuperaron dos documentos rechazados por Unidad_Medida vacía: 1.952 y 2.285 registros, desde los bytes conservados y sin descargar otra vez. Los intentos previos se mantuvieron.

Un ensayo sintético previo de 5.000 consultas, con cuatro consumidores y un Item por documento, terminó en 127,172 segundos; recuperó 52 fallos transitorios y un intento interrumpido. Al repetir el lote hubo 5.000 YaCargada y cero diferencias de modelo. El ensayo utilizó SQL real y HTTP simulado, acelerando exclusivamente las esperas de reintento. No estima el tiempo ni el tamaño de los XML reales y no se volvió a ejecutar durante la migración frontend.

## Reproducir comprobaciones

Desde la raíz:

```powershell
pnpm --dir frontend build
.\uv.cmd run --frozen python -m unittest discover -s tests -v
.\uv.cmd run --frozen python scripts/verificar_integridad.py
.\uv.cmd run --frozen --group browser python scripts/verify_ui.py
```

Para la prueba SQL aislada, consulta el comando del [README](../README.md). El script visual solicita credenciales por teclado; `--stdin` permite pasarlas por entrada estándar sin incluirlas en argumentos ni archivos.

Permanecen pendientes pausa/reanudación manual de lotes, descarga completa real del Excel y contraste con maestros oficiales. La recuperación por lease y la pausa automática por fallos del servicio sí están implementadas.

## Mantenimiento e inspección de calidad

Con SQL Server disponible se verificaron TypeScript y compilación de Vue y se ejecutó la batería completa en `ProInXML_Validacion`: **57 pruebas aprobadas, incluidas 20 SQL, sin omisiones**. Incluye permisos de Administrador, CSRF, alcance, motivo y confirmación, limpieza con el rol SQL limitado `proinxml_app`, recuperación de fallos y rollback.

`scripts/verify_maintenance_ui.py` comprueba la interfaz compilada en Edge con todas las API simuladas, sin conectar a SQL ni eliminar datos. Verifica filtros de calidad y fallos, original escapado, confirmación, cancelación, bloqueo por trabajos en curso, revisión obsoleta, eliminación individual/global simuladas, dato observado resaltado, navegación por rol y móvil sin desborde. La evidencia queda en `.runtime/qa_mantenimiento.json` y capturas `.runtime/mantenimiento-*.png`.

```powershell
.\uv.cmd run --frozen --group browser python scripts/verify_maintenance_ui.py
```

En la revisión de mantenimiento se aplicó la migración 005 en `ProInXML`: `CargaDocumento` conserva solo la FK de usuario y sus identificadores de documento/lote son históricos. Entonces se instalaron y reaplicaron cinco SQL en la base aislada: 44 tablas, todas con CreadoUtc y vista XML de 39 columnas. La revisión posterior de métricas, al final de este documento, amplía el esquema a 45 tablas.

Se reprodujo también el vaciado sobre los datos disponibles en aquella revisión **dentro de una transacción revertida siempre**: 21 documentos, 26.792 registros XML y otros tantos hechos del modelo, 71 observaciones y 4.459 entidades normalizadas. Las tablas de carga quedaron vacías dentro de la transacción; usuarios, catálogo, servicio y auditoría permanecieron. Tras el rollback, se compararon los conteos e identidades de las 44 tablas y las referencias de publicación/trabajos: todo quedó restaurado. Evidencia: `.runtime/limpieza_sql_actual.json`. No se ejecutó una limpieza permanente de datos del usuario y no se reprodujo un bloqueo SQL del vaciado.

La comprobación de integridad posterior confirmó 19 documentos válidos, 26.792 filas de detalle/modelo, 71 unidades nulas con sus observaciones, cero diferencias de reconstrucción en ambos sentidos y ninguna huella incorrecta.

Las pruebas SQL ejecutadas con rollback cubren eliminación individual/versiones compartidas, vaciado global conservando cuentas/auditoría, reimportación sin reutilizar IDs, trabajos en curso, vista previa obsoleta, reversión completa ante un fallo e inspección de errores/valores originales. Solo permiten probar mantenimiento en `ProInXML_Validacion`:

```powershell
.\uv.cmd run --frozen python scripts/verificar_esquema.py
$env:MSSQL_DATABASE='ProInXML_Validacion'
$env:PROINXML_RUN_SQL_TESTS='1'
try {
    .\uv.cmd run --frozen python -m unittest tests.test_sql_integration -v
} finally {
    Remove-Item Env:MSSQL_DATABASE
    Remove-Item Env:PROINXML_RUN_SQL_TESTS
}
```

El ensayo concurrente de cola conserva sus dos trabajos técnicos como Cancelado en la base aislada; las demás pruebas se revierten. No utiliza XML externos. En otras instalaciones corresponde aplicar la migración con una copia de seguridad, siguiendo [OPERACION.md](OPERACION.md).

## Legibilidad, densidad y diagrama

Se aumentó el tamaño del texto de tablas de 12 a 13 px, los encabezados y ayudas de 11 a 12 px, y se usa la familia de fuentes del sistema sin descargas externas. Se reforzaron textos secundarios y estados, y el botón principal usa verde oscuro con texto blanco. El diálogo explica qué requisito falta para habilitar el borrado y el resultado informa documentos y filas eliminados.

La comparación con la misma pantalla simulada a 1440×1050 situó el inicio de la tabla en 635,17 px antes y 464,67 px después: **170,50 px menos de desplazamiento vertical**. El bloque de filtros pasó de 209 a 159 px de alto. Se revisaron capturas de escritorio y móvil de 390 px, sin desborde horizontal del documento ni errores JavaScript. Los cocientes de contraste medidos sobre estos elementos fueron 9,32:1 para filas/etiquetas, 5,53:1 para encabezados, 6,14:1 para ayudas y 6,91:1 para el botón principal; no es una certificación completa de accesibilidad. Evidencia: `.runtime/comparacion_ui.json` y capturas `mantenimiento-*-antes.png`/`mantenimiento-*-despues.png`.

[DIAGRAMA_BD.dbml.txt](DIAGRAMA_BD.dbml.txt) se regeneró desde metadatos reales incluyendo la migración 006 y se validó con el analizador oficial `@dbml/core` 10.3.1: **45 tablas, 313 columnas, 47 relaciones y 13 grupos**. Los detalles de agrupación, alcance y regeneración están en [DIAGRAMA_BD.md](DIAGRAMA_BD.md).

## Arranque conjunto de FastAPI y Vue

Se ejecutó `iniciar.cmd` con `MSSQL_DATABASE=ProInXML_Validacion`: FastAPI en 8000, Vite en 5173 y el worker. Se comprobó la entrada de Vite, la ruta profunda de mantenimiento, salud de API/SQL, Swagger y OpenAPI a través del frontend. `/documentos` y el POST de `/mantenimiento/vista-previa` devolvieron el 401 JSON esperado sin sesión: confirma que el proxy los entrega a FastAPI. Estas dos rutas faltaban en el proxy de desarrollo y se incorporaron, junto con la documentación.

Se comprobó Ctrl+C, sin traceback, y después se verificó que no quedaran hijos del proceso lanzador ni los puertos 8000/5173 ocupados. TypeScript y compilación Python del lanzador pasaron. La prueba no creó lotes ni ejecutó borrados. Evidencia de respuestas: `.runtime/qa_arranque.json`. El modo de frontend compilado permanece disponible con `iniciar.cmd --compilado`.

## Métricas, 20 descargas y 1.000 URLs

La revisión de métricas pasó **67 pruebas: 39 de API/lector/worker y 28 de SQL**, con `PROINXML_RUN_SQL_TESTS=1` y `MSSQL_DATABASE=ProInXML_Validacion`. Los seis scripts SQL se aplicaron y reaplicaron en esa base: 45 tablas con `CreadoUtc` y la vista XML de 39 columnas. TypeScript y `pnpm --dir frontend build` pasaron.

Se verificaron tiempos no negativos por fase, API de resumen/P95, persistencia tras limpieza, fallos de red sin HTTP o fases SQL inventadas, XML truncado después del primer bloque de inserción con rollback y cero filas nuevas, error de calidad con detalle confirmado pero cero normalizadas, reutilización sin inflar filas nuevas, recuperación de lease y un fallo de métricas que no invalida la carga.

La prueba concurrente sincroniza **20 descargas HTTP simuladas**, cada una con el mismo fixture de siete Items adaptado a su ejecutora, y utiliza conexiones SQL independientes. Completó 20 trabajos, 140 filas y 20 mediciones con concurrencia registrada 20. Este ensayo conserva sus datos técnicos solo en `ProInXML_Validacion`. El ensayo anterior de dos tomas conserva sus trabajos técnicos cancelados; el resto de las pruebas SQL se revierte. Evidencia de la muestra medida y las respuestas reales de análisis: `.runtime/qa_metricas_sql.json`. Los resultados prueban funcionamiento, no estiman el rendimiento de los XML del MEF.

La nueva pantalla se comprobó con Edge y API simulada, reutilizando valores del ensayo SQL: siete fases, filtros, detalle, estado vacío, aviso histórico y actualización automática cada tres segundos. También se validó el envío de 1.000 URLs y el rechazo de 1.001 en interfaz/API. Se revisaron capturas a 1440 y 390 px, sin desborde del documento ni errores JavaScript. Evidencia: `.runtime/qa_mantenimiento.json`, `metricas-desktop.png` y `metricas-movil.png`. No se enviaron esas URLs al MEF.

Se comprobó además Vite con FastAPI reales y SQL de validación, sin worker: la ruta Vue `/ui/metricas` respondió correctamente, las tres rutas `/metricas/*` llegaron a la API y exigieron sesión con 401 JSON, y OpenAPI confirmó `maxItems=1000`. Evidencia: `.runtime/qa_proxy_metricas.json`. Los servidores de prueba se cerraron al terminar.

Antes de instalar 006 en `ProInXML` se generó un respaldo `COPY_ONLY` con `CHECKSUM` y se verificó mediante `RESTORE VERIFYONLY`. La migración aditiva dejó intactos **500 documentos y 475.012 filas XML**. Evidencia: `.runtime/migracion_metricas.json`; respaldo verificado en `.runtime/backups/ProInXML_antes_metricas_20261023_215953.bak`. No se limpiaron permanentemente datos del usuario. Las métricas empiezan con los nuevos intentos; no se reconstruyó un desglose para las cargas anteriores.
