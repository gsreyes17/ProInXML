# ProInXML: proyecto definitivo de integración

> Documento original de planificación. El contrato de base de datos se conserva. La implementación evolucionó a Vue 3 con pnpm y Python con uv; consulta [ARQUITECTURA.md](ARQUITECTURA.md) y el [README](../README.md) para la estructura y los comandos vigentes. Pausa y reanudación manual quedaron diferidas por decisión del usuario.

*Taller de Integraciones · 23 de octubre de 2026 · Alcance: sistema local, carga única de unas 5.000 URLs del servicio XML de gasto del MEF.*

## 1. Objetivo

Recibir todas las URLs de una vez, descargar cada XML, validarlo, guardarlo con trazabilidad completa y dejar el resultado consultable. El sistema debe ser **reanudable y repetible**: no vuelve a procesar lo que ya cargó bien, reintenta lo que falló y registra quién hizo cada acción y con qué rol.

## 2. Decisiones cerradas

1. Carga única, pero con un diseño que permite reprocesar sin duplicar.
2. Volumen aproximado: 5.000 URLs. El Excel de ejemplo es solo referencial; el real no traerá conteo de registros esperados.
3. Sistema local: Python, FastAPI y SQL Server, con worker separado de la API y la base como cola persistente.
4. Se conserva `AnoEje` y los 39 nombres de campo del XML.
5. Login con roles; cada cambio en auditoría guarda usuario y rol.
6. `Unidad_Medida` vacía se guarda como `NULL` con una observación (sección 5).
7. Se mantienen las tres capas de datos: respuesta original, detalle de 39 campos y modelo normalizado.

## 3. Arquitectura

| Componente | Responsabilidad |
| --- | --- |
| Interfaz web | Login, carga de URLs o Excel, seguimiento, consulta de datos, auditoría. |
| API (FastAPI) | Autenticación, recepción de lotes, consultas. |
| Worker (Python) | Toma trabajos de la cola, descarga, valida, persiste, reintenta. |
| SQL Server | Lotes, fuentes, trabajos, intentos, documentos, datos, modelo, seguridad y auditoría. |
| Servicio MEF | Origen de los XML. Solo se aceptan su host y su ruta conocidos (protección contra SSRF). |

Flujo: el usuario registra el lote → la API crea fuentes y trabajos en una transacción → el worker toma un trabajo, crea el intento y descarga → conserva los bytes y la huella SHA-256 → valida el documento completo → inserta detalle y modelo en una sola transacción → publica la versión como vigente → la interfaz muestra el resultado.

## 4. Carga masiva e idempotencia

**Regla por URL al registrar el lote:**

| Situación de la URL | Acción |
| --- | --- |
| Ya tiene un documento válido publicado | No se descarga de nuevo (se marca "ya cargada"). |
| Nunca se procesó | Se encola. |
| Último intento falló | Se encola de nuevo. |
| Se pide "forzar revisión" (solo administrador) | Se descarga, se compara el SHA-256 y solo si cambió se crea una versión nueva. |

**Robustez:**

- **Concurrencia configurable** (por defecto 3 a 5 descargas en paralelo). Los trabajos se toman con `UPDLOCK, READPAST` para que dos workers no tomen el mismo.
- **Reintentos** automáticos con espera creciente y variación aleatoria, hasta 4 intentos; después queda en estado fallido, con reintento manual desde la interfaz.
- **Reanudable:** si el proceso se cae, los trabajos con lease vencido vuelven a la cola.
- **Sin conteo esperado**, la completitud se controla así: XML bien formado y completo, `Item` leídos guardados por documento, y documentos con cero `Item` marcados como "completado sin datos" y filtrables.
- **Progreso por lote** visible: pendientes, en curso, completadas, fallidas y tiempo estimado.
- **Cortesía con el MEF:** límite de concurrencia, tiempos de espera acotados y pausa automática si hay una racha de errores.

## 5. Contrato de los 39 campos y regla de `Unidad_Medida`

**Caso observado** (XML real, fila con códigos genéricos):

```xml
<Unidad_Medida/>
```

**Regla:**

- Etiqueta vacía, solo espacios, etiqueta ausente o `xsi:nil` → `NULL` en el detalle y en `Meta`.
- Cada caso genera una observación distinta (`UNIDAD_VACIA`, `UNIDAD_AUSENTE`, `UNIDAD_NIL`) para no perder qué ocurrió.
- Un código real como `036` se conserva exactamente.
- No se inventa un código ni un nombre. La respuesta original sigue guardada.

**Cambios técnicos asociados:** columna nula en `datos.Gasto`, FK opcional de `Meta` hacia `UnidadMedida`, comparaciones de clave que toleran nulos, `LEFT JOIN` en la reconstrucción, y la interfaz muestra la celda vacía sin error.

**Perfilado previo (primer paso del proyecto):** barrer una muestra amplia de XML y listar, por cada uno de los 39 campos, cuántas veces llega vacío, ausente o con formato raro. Con eso se completa una **tabla de contrato** (campo, tipo, obligatorio u opcional, qué hacer si viene vacío). Hipótesis a confirmar: la unidad vacía coincide con `IdMeta`/`IdFinalidad` genéricos (`99999`).

**Otros códigos especiales vistos en la muestra** y que se conservan tal cual, sin asignarles significado: `MesEje=0`, `SecFunc=0`, `IdTipoRecurso=0`, `IdProyectoSNIP=0`, `Distrito=99`, `IdProyecto=2999999`, `IdComponente=6999999`. Los códigos se guardan como texto (sin rellenar ceros) y los importes como `DECIMAL(19,4)`; el ejemplo trae decimales (`408195.81`).

## 6. Modelo de datos

**Control e integración:** `Lote`, `Fuente` (se propone renombrarla `Consulta`, para no confundirla con `IdFuente` de financiamiento), `Trabajo`, `Intento`, `Documento`. Se añaden `Servicio` (endpoint y versión de contrato) y `ObservacionDato` (incidencias no bloqueantes por documento, ordinal y campo, con unicidad para no duplicarlas al reprocesar).

**Datos:** `datos.Gasto` (39 campos más identificadores técnicos), vista `datos.GastoActual` (última versión válida por consulta) y vista `datos.vw_GastoXML` (exactamente los 39 campos, sin `DISTINCT`).

**Modelo normalizado:** 29 entidades más `modelo.Gasto`, con la misma identidad del registro de origen; se añade `modelo.GastoActual` (solo versiones vigentes) y se mantiene `modelo.GastoReconstruido` como prueba de integridad. Se presenta como un modelo relacional conservador, **pendiente de maestros del MEF** para afirmar una 3FN completa.

**Seguridad:** `seguridad.Usuario` (hash de contraseña, activo), `seguridad.Rol`, `seguridad.EventoAcceso` (inicios de sesión exitosos y fallidos).

**Reportes:** vista `reportes.EjecucionServicio`, una fila por intento: HTTP, inicio, fin, duración, error, URL solicitada, resultado y métricas de registros.

## 7. Login, roles y auditoría

| Rol | Permisos |
| --- | --- |
| Administrador | Crear lotes, reintentar, forzar revisión, ver auditoría y gestionar usuarios. |
| Operador | Crear lotes y reintentar fallidas; consultar datos y seguimiento. |
| Consulta | Solo lectura de datos y seguimiento. |

- La API autentica con sesión y token; las contraseñas se guardan con hash (argon2 o bcrypt).
- Cada petición establece el usuario y el rol en la conexión (`SESSION_CONTEXT`), y los triggers lo leen para llenar `Actor` y `Rol` en `auditoria.Cambio`.
- El worker actúa como usuario "sistema", pero cada lote y trabajo conserva quién lo originó (`Lote.CreadoPor`).
- `auditoria.Cambio` pasa a incluir `UsuarioId` y `Rol`. El usuario SQL de la aplicación no tiene UPDATE ni DELETE sobre la auditoría.
- **Cambio de criterio para el volumen:** en las cargas masivas se audita a nivel de documento (usuario, lote, huella, filas insertadas), porque guardar antes y después de 39 campos por cada fila multiplicaría el almacenamiento y frenaría la carga. En configuración, catálogos, usuarios y maestros se mantiene la auditoría fila a fila.
- Los eventos de acceso (login fallido, cambio de rol) se registran aparte.

## 8. Consultas y pantallas

| Pantalla | Función |
| --- | --- |
| Login | Autenticación y rol. |
| Carga | Pegar URLs o importar Excel; resumen de nuevas, ya cargadas y repetidas. |
| Seguimiento | Progreso del lote, estado por URL, reintento manual. |
| Ejecución del servicio | `reportes.EjecucionServicio`: HTTP, tiempos y resultado por intento. |
| Registros XML | Modo "Solo XML" (39 campos) y detalle de trazabilidad aparte. |
| Observaciones | Incidencias de datos, filtrables por campo y código. |
| Auditoría | Eventos con usuario, rol, antes y después. |
| Modelo | Explorador de entidades y claves foráneas. |

## 9. Plan por fases

1. **Perfilado** de una muestra amplia de XML y tabla de contrato de campos.
2. **Correcciones de datos:** `Unidad_Medida` opcional, observaciones y pruebas con registros mixtos y reprocesos.
3. **Seguridad:** login, roles, contexto de usuario en la conexión y ajuste de la auditoría.
4. **Operación:** intentos ampliados, `reportes.EjecucionServicio`, estados y reintento manual, concurrencia configurable.
5. **Vistas y pantallas:** `vw_GastoXML`, modo Solo XML, `GastoActual` del modelo, pantalla de observaciones.
6. **Prueba de carga** con un subconjunto grande y luego con las \~5.000 URLs; medir tiempos, tamaño de la base y tasa de error.
7. **Cierre:** documentación de arquitectura, mapeo XML a modelo, matriz de errores y guía de reproceso.

## 10. Criterios de aceptación

- Cargar las \~5.000 URLs sin intervención y reanudar tras un corte sin duplicar gastos.
- Una URL ya cargada correctamente no se vuelve a descargar salvo "forzar revisión".
- Un documento con `Unidad_Medida` vacía se carga completo, con `NULL` y observación.
- Cada acción manual queda en auditoría con usuario y rol.
- Cero diferencias entre los 39 campos originales y su reconstrucción desde el modelo.
- Para cada intento se puede consultar HTTP, inicio, fin, duración y resultado.

## 11. Riesgos y preguntas abiertas

- El servicio `_old_2` parece heredado; puede cambiar o limitar la tasa de consultas. Mitigación: concurrencia baja y contrato versionado.
- El URL del MEF usa `http`; verificar si redirige a `https` y decidir si se acepta.
- Pueden existir otros campos vacíos o con formatos inesperados; el perfilado lo determinará.
- El tamaño total (respuesta original más detalle más modelo) es desconocido; medirlo en la prueba de carga y evaluar comprimir la respuesta original.
- La 3FN completa depende de contar con los maestros del MEF.

## 12. Especificación de base de datos (nivel de implementación)

Base `ProInXML` en SQL Server 2019 o superior. Los scripts van numerados en `sql/` (`001_...`, `002_...`), son repetibles y se aplican en orden. Esta sección es la fuente de verdad del esquema: si algo no está aquí, el agente debe preguntar en lugar de inventarlo.

### 12.1 Convenciones

- PK `Id BIGINT IDENTITY(1,1)`, salvo `catalogo.TipoActProy` (Id explícito 2 y 3) y `modelo.Gasto` (su `Id` es el de `datos.Gasto`, sin IDENTITY).
- Toda tabla tiene `CreadoUtc DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()`.
- Códigos del MEF: `VARCHAR(32)`, se conservan tal cual (sin rellenar ceros, solo se recortan espacios en los extremos). Importes: `DECIMAL(19,4)`.
- Claves naturales con restricción `UNIQUE` explícita; FK con nombre; ningún `ON DELETE CASCADE`.
- `integracion.Consulta` y `integracion.Documento` se referencian entre sí (documento vigente y consulta de origen): crear las tablas primero y añadir esa FK después con `ALTER TABLE`.

### 12.2 Esquema `integracion`

| Tabla | Columnas | Claves y reglas |
| --- | --- | --- |
| `Servicio` | Id, Nombre, UrlBase, Ruta, VersionContrato, Activo | UNIQUE (UrlBase, Ruta) |
| `Lote` | Id, Nombre, CreadoPorUsuarioId (FK `seguridad.Usuario`) |  |
| `Consulta` (antes `Fuente`) | Id, ServicioId, Url NVARCHAR(1000), AnoEje SMALLINT, NivelGobierno VARCHAR(8), SecEjec INT, DocumentoActualId NULL | UNIQUE (ServicioId, AnoEje, NivelGobierno, SecEjec): la consulta se identifica por sus parámetros, no por el texto de la URL |
| `Trabajo` | Id, LoteId, ConsultaId, Estado, Intentos, MaxIntentos (4), ProximoIntentoUtc, LeaseHastaUtc, Token, UltimoError, DocumentoId NULL, FinalizadoUtc NULL | UNIQUE (LoteId, ConsultaId) |
| `Intento` | Id, TrabajoId, Numero, Estado, Etapa, InicioUtc, FinUtc NULL, HttpStatus NULL, UrlSolicitada, DocumentoId NULL, Error NULL, RegistrosLeidos, RegistrosInsertados, RegistrosReutilizados, RegistrosRechazados, Observaciones NULL | UNIQUE (TrabajoId, Numero). `HttpStatus` nulo si no hubo respuesta |
| `Documento` | Id, ConsultaId, IntentoId, Sha256 CHAR(64), Respuesta VARBINARY(MAX) (comprimida), ContentType, EsValido, CantidadRegistros NULL, ErrorValidacion NULL | UNIQUE (ConsultaId, Sha256) |
| `ObservacionDato` | Id, DocumentoId, OrdinalItem, Campo, CodigoObservacion, Severidad, Detalle, FechaUtc | UNIQUE (DocumentoId, OrdinalItem, Campo, CodigoObservacion) |

**Estados de `Trabajo`:** Pendiente → EnCurso → Completado, CompletadoSinDatos o Fallido. Además: YaCargada (la consulta ya tenía un documento válido) y Cancelado. Un trabajo EnCurso cuyo lease venció vuelve a Pendiente.

**Severidad de observaciones:** Info, Advertencia o Error. Solo Error bloquea la publicación del documento. `Unidad_Medida` vacía es Advertencia.

### 12.3 Esquemas `seguridad`, `catalogo` y `auditoria`

| Tabla | Columnas | Claves y reglas |
| --- | --- | --- |
| `seguridad.Rol` | Id, Nombre | UNIQUE (Nombre). Datos iniciales: Administrador, Operador, Consulta |
| `seguridad.Usuario` | Id, NombreUsuario, NombreCompleto, HashContrasena, RolId, Activo | UNIQUE (NombreUsuario) |
| `seguridad.EventoAcceso` | Id, UsuarioId NULL, NombreIntentado, Evento, Exitoso, Ip, FechaUtc | Solo inserción |
| `catalogo.TipoActProy` | Id (2 o 3), Nombre | 2 = Proyecto, 3 = Actividad |
| `auditoria.Cambio` | Id, Tabla, RegistroId, Operacion, FechaUtc, UsuarioId NULL, Actor, Rol, LoginSql, Correlacion, Antes NVARCHAR(MAX), Despues NVARCHAR(MAX) | Índice por (Tabla, RegistroId) y por FechaUtc |
| `auditoria.CargaDocumento` | Id, DocumentoId, LoteId, UsuarioId NULL, Rol, FilasInsertadas, FilasReutilizadas, FechaUtc | Una fila por documento procesado |

### 12.4 Esquema `datos` (detalle de los 39 campos)

`datos.Gasto` guarda cada `Item` tal como llegó. **No lleva FK al catálogo ni a las entidades**, para que un valor inesperado nunca impida guardar el dato original. Todas las columnas son `NOT NULL` salvo `Unidad_Medida`, hasta que el perfilado de datos indique otra cosa.

```sql
CREATE TABLE datos.Gasto (
  Id BIGINT IDENTITY(1,1) PRIMARY KEY,
  DocumentoId BIGINT NOT NULL,          -- FK integracion.Documento
  Ordinal INT NOT NULL,                 -- posición del Item en el XML
  AnoEje SMALLINT NOT NULL,
  MesEje TINYINT NOT NULL,              -- 0 a 12
  IdNivelGobierno VARCHAR(32) NOT NULL,
  Sub_tipo_gobierno VARCHAR(32) NOT NULL,
  IdSector VARCHAR(32) NOT NULL,
  IdPliego VARCHAR(32) NOT NULL,
  IdEjecutora VARCHAR(32) NOT NULL,
  SecEjec INT NOT NULL,
  Funcion VARCHAR(32) NOT NULL,
  Programa VARCHAR(32) NOT NULL,
  Programa_ppto VARCHAR(32) NOT NULL,
  Categ_gasto VARCHAR(32) NOT NULL,
  Tipo_transaccion VARCHAR(32) NOT NULL,
  Generica VARCHAR(32) NOT NULL,
  Subgenerica VARCHAR(32) NOT NULL,
  Subgenerica_det VARCHAR(32) NOT NULL,
  Especifica VARCHAR(32) NOT NULL,
  Especifica_det VARCHAR(32) NOT NULL,
  SecFunc VARCHAR(32) NOT NULL,
  IdFuente VARCHAR(32) NOT NULL,
  IdRubro VARCHAR(32) NOT NULL,
  IdTipoRecurso VARCHAR(32) NOT NULL,
  IdComponente VARCHAR(32) NOT NULL,
  IdProyecto VARCHAR(32) NOT NULL,
  TipoActProy BIGINT NOT NULL,
  IdMeta VARCHAR(32) NOT NULL,
  IdFinalidad VARCHAR(32) NOT NULL,
  IdProyectoSNIP VARCHAR(32) NOT NULL,
  Departamento VARCHAR(32) NOT NULL,
  Provincia VARCHAR(32) NOT NULL,
  Distrito VARCHAR(32) NOT NULL,
  Unidad_Medida VARCHAR(32) NULL,       -- vacío en el XML => NULL + observación
  PIA DECIMAL(19,4) NOT NULL,
  PIM DECIMAL(19,4) NOT NULL,
  Certificado DECIMAL(19,4) NOT NULL,
  CompAnual DECIMAL(19,4) NOT NULL,
  AtencionCompMensual DECIMAL(19,4) NOT NULL,
  Devengado DECIMAL(19,4) NOT NULL,
  Girado DECIMAL(19,4) NOT NULL,
  CreadoUtc DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  CONSTRAINT UQ_datos_Gasto_Doc_Ord UNIQUE (DocumentoId, Ordinal)
);
```

Vistas: `datos.GastoActual` (filas cuyo documento es el `DocumentoActualId` de su consulta) y `datos.vw_GastoXML` (los 39 campos en este orden, sin `DISTINCT`).

### 12.5 Esquema `modelo` (propuesta en tercera forma normal)

Cada tabla tiene `Id` como PK y una columna de código (`Codigo VARCHAR(32) NOT NULL`) salvo indicación. Las FK a padres se llaman `<Padre>Id`.

| Grupo | Tabla | Columnas adicionales | UNIQUE |
| --- | --- | --- | --- |
| Instituciones | `NivelGobierno` |  | (Codigo) |
|  | `SubtipoGobierno` | NivelGobiernoId | (NivelGobiernoId, Codigo) |
|  | `Sector` | SubtipoGobiernoId | (SubtipoGobiernoId, Codigo) |
|  | `Pliego` | SectorId | (SectorId, Codigo) |
|  | `Ejecutora` | PliegoId | (PliegoId, Codigo) |
|  | `ContextoEjecutora` | EjecutoraId, AnoEje SMALLINT, SecEjec INT (sin Codigo) | (EjecutoraId, AnoEje, SecEjec) |
| Presupuesto | `Funcion` |  | (Codigo) |
|  | `ProgramaFuncional` | FuncionId | (FuncionId, Codigo) |
|  | `ProgramaPresupuestal` |  | (Codigo) |
|  | `CategoriaGasto` |  | (Codigo) |
| Clasificadores | `TipoTransaccion` |  | (Codigo) |
|  | `Generica` | TipoTransaccionId | (TipoTransaccionId, Codigo) |
|  | `Subgenerica` | GenericaId | (GenericaId, Codigo) |
|  | `SubgenericaDetalle` | SubgenericaId | (SubgenericaId, Codigo) |
|  | `Especifica` | SubgenericaDetalleId | (SubgenericaDetalleId, Codigo) |
|  | `EspecificaDetalle` | EspecificaId | (EspecificaId, Codigo) |
| Financiamiento | `FuenteFinanciamiento` |  | (Codigo) |
|  | `Rubro` | FuenteFinanciamientoId | (FuenteFinanciamientoId, Codigo) |
|  | `TipoRecurso` | RubroId | (RubroId, Codigo) |
| Proyectos | `Proyecto`, `ProyectoSNIP`, `Componente` |  | (Codigo) en cada una |
| Metas | `Finalidad`, `UnidadMedida` |  | (Codigo) en cada una |
|  | `SecuenciaFuncional` | ContextoEjecutoraId | (ContextoEjecutoraId, Codigo) |
|  | `Meta` | SecuenciaFuncionalId, FinalidadId, UnidadMedidaId **NULL**, Codigo (IdMeta) | (SecuenciaFuncionalId, Codigo, FinalidadId, UnidadMedidaId) |
| Ubicaciones | `Departamento` |  | (Codigo) |
|  | `Provincia` | DepartamentoId | (DepartamentoId, Codigo) |
|  | `Distrito` | ProvinciaId | (ProvinciaId, Codigo) |

**`modelo.Gasto`** (hecho): `Id` (igual al de `datos.Gasto`, FK hacia él), `MetaId`, `ProgramaFuncionalId`, `ProgramaPresupuestalId`, `CategoriaGastoId`, `EspecificaDetalleId`, `TipoRecursoId`, `ProyectoId`, `ProyectoSNIPId`, `ComponenteId`, `DistritoId`, `TipoActProyId` (FK `catalogo.TipoActProy`), `MesEje TINYINT`, y los siete importes `DECIMAL(19,4)`. No repite año, ejecutora, función, clasificadores ni ubicación padre: se obtienen recorriendo las FK.

**Notas de diseño:**

- En SQL Server una restricción `UNIQUE` trata los nulos como iguales, así que `Meta` admite una sola fila con `UnidadMedidaId` nulo por cada combinación de secuencia, código y finalidad. Es el comportamiento deseado.
- Si `TipoActProy` llega con un valor distinto de 2 o 3, se registra una observación de severidad Error y el documento no se publica (la regla del Excel es 2 o 3).
- Alcance de la 3FN: con las dependencias declaradas arriba (cada código se identifica dentro de su padre) no quedan dependencias transitivas entre las FK del hecho. No se afirma más: sin los maestros del MEF no se pueden confirmar dependencias adicionales (por ejemplo entre proyecto, SNIP y meta). Por eso `Meta` incluye finalidad y unidad en su clave, para conservar las variantes recibidas.
- `modelo.GastoActual`: gasto cuyo `Id` pertenece a un documento vigente. `modelo.GastoReconstruido`: los 39 campos recompuestos desde las entidades, usando `LEFT JOIN` donde hay FK opcional.

**Orden de carga de `NormalizarDocumento`** (misma transacción que el detalle): instituciones, contexto de ejecutora, presupuesto, clasificadores, financiamiento, proyectos y componentes, finalidad y unidad, secuencia funcional, meta, ubicaciones y por último `modelo.Gasto`. Cada paso inserta lo que falta (por clave natural) y reutiliza lo existente: ejecutarlo dos veces no agrega nada.

### 12.6 Cobertura de auditoría

| Tablas | Mecanismo |
| --- | --- |
| `seguridad.Usuario`, `catalogo.*`, `integracion.Servicio`, `Lote`, `Consulta`, `Trabajo` | Trigger fila a fila (INSERT, UPDATE, DELETE) hacia `auditoria.Cambio` |
| `datos.Gasto`, `modelo.*`, `Documento`, `Intento` | Sin trigger por fila (son inserción única y de gran volumen). Cada documento deja una fila en `auditoria.CargaDocumento` |
| Inicios de sesión | `seguridad.EventoAcceso` |

Los triggers leen `SESSION_CONTEXT('usuario_id')` y `SESSION_CONTEXT('rol')` para llenar `UsuarioId`, `Actor` y `Rol`. La aplicación los establece en cada conexión; el worker usa el usuario "sistema" y el lote conserva quién lo creó.

## 13. Especificación para el agente de desarrollo

Esta sección convierte el documento en instrucciones ejecutables. Reglas generales: no inventar nombres de tablas ni columnas (usar los de la sección 12); si algo no está definido, dejar un comentario `TODO` y preguntar; entregar cada fase con sus pruebas.

### 13.1 Estructura del repositorio

```
ProInXML/
  app/
    main.py            # FastAPI, rutas de API y de pantallas
    config.py          # variables de entorno
    db.py              # conexión pyodbc y contexto de usuario (SESSION_CONTEXT)
    security.py        # login, hash de contraseñas, roles, dependencias de permiso
    service.py         # lotes, trabajos, reglas de idempotencia
    worker.py          # descarga, validación y persistencia
    xml_reader.py      # contrato de los 39 campos y observaciones
    normalizer.py      # llamada a modelo.NormalizarDocumento
    explorer.py        # consultas de datos, auditoría y modelo
    static/            # HTML, CSS y JavaScript
  sql/                 # 001_..., 002_... (esquema, triggers, vistas, datos iniciales)
  scripts/             # perfilado de XML, backfill
  tests/
  iniciar.cmd
```

### 13.2 Orden de construcción

1. **Base de datos:** scripts `sql/` de la sección 12, roles iniciales y un usuario administrador creado por script. Prueba: el esquema se crea desde cero y se puede volver a ejecutar.
2. **Lector XML y perfilado:** `xml_reader.py` con los 39 campos, regla de `Unidad_Medida` y observaciones; `scripts/perfilar_xml.py` que lee una carpeta o lista de XML y genera un informe de campos vacíos, ausentes o con formato raro. Prueba: el XML de ejemplo del documento produce `Unidad_Medida = NULL` y una observación `UNIDAD_VACIA`.
3. **Persistencia:** inserción de `datos.Gasto` y `NormalizarDocumento`. Prueba: ejecutar dos veces el mismo documento no duplica nada y `modelo.GastoReconstruido` coincide con `datos.Gasto` en los 39 campos.
4. **Seguridad:** login, roles y `SESSION_CONTEXT`. Prueba: una acción del Operador queda en `auditoria.Cambio` con su usuario y rol.
5. **Worker y cola:** toma de trabajos con `UPDLOCK, READPAST`, intentos con HTTP y tiempos, reintentos, lease, concurrencia configurable. Prueba: simular un corte a mitad de lote y reanudar sin duplicados.
6. **API y pantallas** de la sección 8.
7. **Prueba de carga** con un subconjunto grande y luego con todas las URLs.

### 13.3 Reglas de procesamiento (resumen de la sección 4)

- Una URL se valida contra el servicio configurado (host y ruta permitidos) y se descompone en `anoEje`, `nivelGobierno` y `sec_ejec`.
- Si la consulta ya tiene documento válido publicado, el trabajo queda `YaCargada` y no se descarga.
- Se publica un documento solo si el XML está completo, todos los `Item` son válidos y no hay observaciones de severidad Error.
- Con HTTP 200 y cero `Item` el trabajo queda `CompletadoSinDatos`.
- Si el SHA-256 coincide con un documento existente de la consulta, se reutiliza y no se insertan filas.
- Cada fallo guarda etapa (descarga, validación, persistencia), HTTP si hubo y mensaje. Nunca se rellena un HTTP inventado.

### 13.4 API

| Método y ruta | Función | Roles |
| --- | --- | --- |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Sesión | Todos |
| `POST /lotes` | Crear lote con URLs en texto o archivo Excel (máximo 500 por entrada manual) | Administrador, Operador |
| `GET /lotes`, `GET /lotes/{id}`, `GET /lotes/{id}/trabajos` | Seguimiento y progreso | Todos |
| `POST /trabajos/{id}/reintentar` | Reintento manual | Administrador, Operador |
| `POST /lotes/{id}/pausar`, `POST /lotes/{id}/reanudar` | Control del lote | Administrador |
| `POST /trabajos/{id}/forzar-revision` | Descargar de nuevo una consulta ya cargada | Administrador |
| `GET /reportes/ejecucion` | `reportes.EjecucionServicio` | Todos |
| `GET /datos/xml`, `GET /datos/xml/{id}` | Registros (39 campos), filtros y paginación | Todos |
| `GET /observaciones` | Incidencias de datos | Todos |
| `GET /auditoria` | Eventos con usuario, rol, antes y después | Administrador |
| `GET /modelo/tablas`, `GET /modelo/tablas/{nombre}` | Explorador del modelo | Todos |
| `GET/POST /usuarios` | Gestión de usuarios | Administrador |

Todas las consultas son de solo lectura, con paginación obligatoria. Los errores se devuelven con un código y un mensaje claros.

### 13.5 Interfaz

HTML, CSS y JavaScript servidos por FastAPI, sin framework obligatorio. Pantallas y funciones según la sección 8. Requisitos: tabla paginada con filtros, indicador de progreso del lote con actualización periódica, modo "Solo XML" con las 39 columnas, detalle de trazabilidad en un panel aparte, y los botones de acción visibles solo según el rol.

### 13.6 Pruebas mínimas

- Lector XML: caso normal, `Unidad_Medida` vacía, ausente y con `xsi:nil`, XML truncado, `TipoActProy` inválido, importes con decimales.
- Idempotencia: mismo documento dos veces; mismo contenido desde dos consultas distintas.
- Cola: dos workers concurrentes no toman el mismo trabajo; lease vencido recupera el trabajo.
- Seguridad: rol Consulta no puede crear lotes; login fallido queda en `EventoAcceso`.
- Auditoría: cambio de configuración registra usuario, rol, antes y después.
- Integridad: reconstrucción del modelo sin diferencias frente al detalle.

### 13.7 Fuera de alcance por ahora

Despliegue en servidor, HTTPS propio, integración con directorio de usuarios corporativo, importar XML de otros servicios, y maestros oficiales del MEF (nombres y vigencias). Quedan registrados como mejoras futuras.
