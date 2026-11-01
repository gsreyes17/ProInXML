# Arquitectura y base de datos

ProInXML 1.0 utiliza Vue 3, Vue Router y Pinia; FastAPI; un worker Python con hilos; y SQL Server. La cola permanece en SQL para recuperar trabajos después de una interrupción.

## Organización del backend

```text
app/
├── run.py                 Lanzador de los procesos
├── api/                   FastAPI, rutas, autenticación y entrega de Vue
│   ├── main.py            Entrada HTTP y registro de rutas
│   ├── security.py        Sesiones, roles y acceso
│   ├── explorer.py        Consultas de datos y auditoría
│   ├── analysis.py        Análisis de tiempos
│   ├── maintenance.py     Limpieza y mantenimiento
│   └── ui.py              Archivos compilados de Vue
├── integration/           Flujo asíncrono de documentos
│   ├── service.py         Lotes, trabajos y persistencia
│   ├── worker.py          Descarga, reintentos y ejecución
│   ├── normalizer.py      Paso de staging al modelo
│   └── metrics.py         Medidas de cada intento
├── domain/                Reglas de los datos
│   ├── xml_reader.py      URL, contrato y lectura del XML
│   └── model_schema.py    Entidades y relaciones del modelo
└── infrastructure/        Recursos compartidos
    ├── config.py          Variables de entorno
    ├── db.py              Conexión y transacciones SQL
    └── locks.py           Coordinación de operaciones
```

La API registra lotes y consulta estados. `integration.worker` ejecuta los trabajos de la cola SQL, descarga el XML y usa `integration.service` para guardarlo; `integration.normalizer` proyecta el detalle a `modelo`. Las reglas del XML y las definiciones relacionales viven en `domain`. Los módulos comparten conexión, configuración y bloqueos de `infrastructure`. `app.run` lanza API y worker como procesos separados.

```mermaid
flowchart LR
    Usuario --> Vue[Vue / TypeScript]
    Vue --> API[FastAPI]
    API --> Cola[(Lote / Consulta / Trabajo)]
    Cola --> Worker[Worker Python]
    Worker --> MEF[Servicio XML MEF]
    MEF --> Original[(Documento gzip + SHA-256)]
    Original --> Validacion[Validación del contrato]
    Validacion --> Detalle[(staging.Gasto: 39 campos)]
    Detalle --> Modelo[(modelo: entidades + gasto)]
    Modelo --> Publicacion[Documento vigente]
    Worker --> Metricas[(analisis.MetricaIntento)]
    API --> Lecturas[Consultas / auditoría / métricas]
```

## Procesamiento

1. La API valida host, ruta y parámetros de las URLs antes de registrar el lote. Repetidas dentro del lote se omiten; consultas publicadas generan trabajos `YaCargada`.
2. El worker toma trabajos mediante el procedimiento `integracion.TomarTrabajo`, con `UPDLOCK`, `READPAST`, token y lease. La concurrencia predeterminada es ocho.
3. La respuesta completa se guarda comprimida; SHA-256 se calcula sobre los bytes originales. El documento se identifica por consulta y huella.
4. El lector valida raíz, namespace, campos y tipos. La respuesta original permanece aunque el documento sea rechazado. El detalle se inserta por bloques de 500 dentro de una única transacción por documento.
5. Un bloqueo de aplicación coordina validación, inserción y normalización. Publicar el documento y completar el trabajo pertenecen a la misma transacción. Los XML truncados revierten su detalle.
6. Las métricas se confirman por separado para conservar el diagnóstico de errores. Los fallos de observabilidad se registran en logs sin volver fallida una carga correcta.

El normalizador deduplica las claves de `SecuenciaFuncional` y `Meta` antes de resolver sus relaciones. Las respuestas válidas sin Items salen antes de recorrer las entidades. No cambia las reglas de unicidad ni la reconstrucción de los campos XML.

## Tablas y vistas

Son **45 tablas**. El [DBML](DIAGRAMA_BD.dbml.txt) contiene 278 columnas, 47 FK y 13 grupos funcionales. `AnoEje` y `MesEje` permanecen en `modelo.Gasto`; `ContextoEjecutora` conserva solo la ejecutora y `SecEjec`. Las fechas de eventos se conservan en documentos, trabajos, cuentas, auditoría y métricas. `dbo.sysdiagrams` pertenece a SSMS y queda fuera del modelo del proyecto.

| Esquema | Contenido |
| --- | --- |
| `integracion` | Servicio, Lote, Consulta, Trabajo, Intento, Documento, ObservacionDato |
| `staging` | Gasto con los 39 campos, DocumentoId y Ordinal |
| `modelo` | 30 entidades y Gasto; el hecho utiliza la identidad del detalle |
| `seguridad` | Rol, Usuario y EventoAcceso |
| `auditoria` | Cambio y CargaDocumento |
| `analisis` | MetricaIntento, con duraciones, HTTP, filas y concurrencia |

`Consulta` es única por servicio, año, nivel de gobierno y ejecutora. Su FK compuesta al documento vigente garantiza que publica una versión de esa misma consulta. El detalle es único por documento y ordinal. `Meta` incluye secuencia funcional, código, finalidad y unidad opcional en su clave.

| Vista | Propósito |
| --- | --- |
| `staging.GastoActual` | Detalle de documentos vigentes |
| `staging.vw_GastoXML` | Exactamente los 39 campos XML, en orden y sin DISTINCT |
| `modelo.GastoActual` | Hechos de documentos vigentes |
| `modelo.GastoReconstruido` | Reconstrucción de los 39 campos a partir del modelo |
| `reportes.EjecucionServicio` | HTTP, estados, tiempos y conteos por intento |

## Organización SQL

| Script | Responsabilidad |
| --- | --- |
| `001_base.sql` | Esquemas, 14 tablas base, FK, índices, rol SQL, catálogos iniciales y migración de `datos` a `staging` |
| `002_modelo.sql` | 30 entidades y tabla de hechos, con claves, nombres geográficos y actualización de tablas anteriores |
| `003_normalizacion.sql` | Procedimiento de normalización y reconstrucción |
| `004_operacion.sql` | Cola, vistas, limpieza de vistas antiguas, triggers de auditoría y permisos |
| `005_metricas.sql` | Tabla de mediciones e índices de análisis |

La instalación crea directamente el esquema final y migra instalaciones anteriores sin borrar registros. Al aplicar todos los SQL, `scripts/aplicar_sql.py` ejecuta `scripts/cargar_ubigeo.py` con `data_models/ubigeo_distrito.csv`. El modelo recibe nombre de departamento, provincia, región y distrito según el código INEI; códigos especiales sin correspondencia quedan con nombre NULL. `scripts/desarrollo/build_model_sql.py` genera 002 y 003 desde `app/domain/model_schema.py`; no se ejecuta durante el arranque.

## Seguridad y auditoría

La API comprueba sesión, cuenta activa y rol en cada petición. Las contraseñas usan Argon2; las cookies son HttpOnly/SameSite Strict y las modificaciones desde navegador requieren CSRF. Se admite Bearer para API. Las sesiones viven en memoria y se utiliza una instancia de proceso API.

El contexto SQL identifica usuario, actor, rol y correlación. `auditoria.Cambio` registra cambios de configuración, usuarios y cola, excluyendo hashes de contraseñas. El volumen XML se resume en `CargaDocumento`; no se genera una fila de auditoría por Item. Los triggers y permisos protegen la inmutabilidad de las bitácoras.

Mantenimiento toma un bloqueo exclusivo y exige que no existan trabajos en curso. La limpieza de cargas preserva cuentas, configuración, auditoría y métricas. Las referencias históricas de auditoría y análisis no tienen FK a documentos/lotes eliminables; no se reinician identidades.

## Ejecución local

`iniciar.cmd` administra API, worker y Vite como procesos separados. El navegador usa el proxy de Vite y conserva el mismo origen para cookies/CSRF; no necesita configurar CORS. `--compilado` sirve Vue desde FastAPI sin Node activo. Ctrl+C detiene los procesos del lanzador y una salida inesperada de un hijo cierra el conjunto.

El seguimiento consulta cada tres segundos, evita solicitudes superpuestas, descarta respuestas obsoletas y pausa al ocultar la pestaña. La navegación se agrupa en procesamiento, consultas y administración; la API vuelve a comprobar los permisos independientemente del menú.
