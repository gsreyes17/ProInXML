# ProInXML

Integración de XML del MEF con **FastAPI, SQL Server y Vue 3**. Permite cargar URLs o Excel, seguir reintentos, explorar los 39 campos originales y su modelo relacional, y consultar observaciones y auditoría.

Python se gestiona con **uv**; el frontend utiliza **pnpm, Vite, TypeScript, Vue Router y Pinia**. La actualización de Seguimiento se mantiene cada tres segundos, sin recargar la página.

## Inicio rápido

Requisitos: Windows, Python 3.11, Node 22.12 o superior, pnpm 11, SQL Server 2019+ y Microsoft ODBC Driver 18.

Desde la carpeta del proyecto:

```powershell
# Instala uv local, sincroniza .venv y compila Vue con los lockfiles.
powershell -ExecutionPolicy Bypass -File scripts/preparar.ps1

Copy-Item .env.example .env
# Ajustar la conexión SQL en .env antes de continuar.
.\uv.cmd run --frozen python scripts/aplicar_sql.py
.\uv.cmd run --frozen python scripts/crear_admin.py
.\iniciar.cmd
```

Abre [http://127.0.0.1:5173](http://127.0.0.1:5173). El script de administrador pide una contraseña; no existen credenciales predeterminadas en el repositorio. En una instalación existente conserva `.env`, la base y sus cuentas: basta preparar las dependencias y reiniciar la aplicación. Detén API y worker y respalda la base antes de aplicar una migración SQL.

`preparar.ps1` instala uv en `.tools/uv`, sin modificar el PATH global. `uv.cmd` permite usarlo desde este checkout. Si ya tienes uv instalado, puedes utilizar directamente `uv sync --frozen` y `uv run --frozen ...`. Los almacenes de paquetes están configurados dentro de `.runtime/`.

`iniciar.cmd` levanta FastAPI en el puerto 8000, Vue/Vite en el 5173 y el worker de cargas. Vue refleja los cambios de código automáticamente. El proxy de Vite conserva las cookies y CSRF, incluidos documentos y mantenimiento, sin configurar CORS. Los logs quedan en `.runtime/worker.log` y `.runtime/vue.log`; Ctrl+C detiene los procesos iniciados por la aplicación. Si un componente se detiene, se cierra el conjunto para evitar dejar la aplicación a medias.

Para servir el frontend ya compilado desde FastAPI en un único puerto y sin Node en ejecución, usa `iniciar.cmd --compilado` después de compilar con pnpm. En ese modo abre [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Desarrollo

En una terminal, inicia la API:

```powershell
.\uv.cmd run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En otra, inicia Vue:

```powershell
pnpm --dir frontend dev
```

Abre la URL que indique Vite. Su proxy envía las consultas a FastAPI en el puerto 8000 y conserva la sesión con cookies y CSRF. Para procesar cargas, ejecuta también el worker:

```powershell
.\uv.cmd run --frozen python -m app.worker
```

Para volver a usar únicamente el puerto 8000, compila con `pnpm --dir frontend build`. FastAPI entrega `frontend/dist/`, incluidas las rutas profundas `/ui/...`.

## Estructura

```text
app/                 API, seguridad, persistencia, lector y worker Python
frontend/src/
  components/        Tabla, paginación y diálogo reutilizables
  composables/       Seguimiento periódico con cancelación
  services/          Cliente API, CSRF y formatos
  stores/            Sesión y permisos con Pinia
  views/             Pantallas Vue
sql/                 Seis scripts numerados y repetibles
scripts/             Preparación, migración y verificaciones
tests/               Pruebas Python y fixture XML
XML_models/URLs.xlsx Libro de referencia con 5.655 URLs
docs/                Arquitectura, contrato, modelo y operación
uv.lock              Dependencias Python
frontend/pnpm-lock.yaml  Dependencias frontend
```

El repositorio excluye `.venv`, `.tools`, `.runtime`, `node_modules`, `frontend/dist`, `.env`, backups y archivos de SQL Server. Los archivos compilados se regeneran con los comandos anteriores.

`proinxml.egg-info/` contiene metadatos generados por setuptools al instalar el proyecto en modo editable con uv: nombre, versión, dependencias y archivos del paquete. No se edita ni se sube al repositorio; se regenera al instalar el proyecto.

## Funciones

| Pantalla | Función |
| --- | --- |
| Login | Sesión con roles Administrador, Operador y Consulta |
| Carga | Hasta 1.000 URLs manuales o un Excel con enlaces en la primera columna |
| Seguimiento | Progreso, HTTP, errores, reintento y revisión forzada según rol |
| Ejecución del servicio | Tiempos, etapas y métricas por intento |
| Métricas de carga | Tiempos por fase, P95, rendimiento y comparación por concurrencia; actualización cada 3 segundos |
| Registros XML | 39 campos y trazabilidad separada |
| Observaciones | Incidencias por documento, campo y código |
| Auditoría | Cambios de registros, cargas por documento y accesos |
| Modelo 3FN | Entidades y navegación de claves foráneas |
| Usuarios | Cuentas, roles y estado activo |
| Mantenimiento | Inspección de documentos y eliminación de cargas del laboratorio, solo Administrador |

Para presentar la base, copia el código de [DIAGRAMA_BD.dbml.txt](docs/DIAGRAMA_BD.dbml.txt) en dbdiagram. Las [instrucciones del diagrama](docs/DIAGRAMA_BD.md) explican sus 13 grupos por función y cómo regenerarlo desde los metadatos de SQL Server.

Se conserva `AnoEje`, los ceros de los códigos y la precisión decimal. Unidad de medida vacía, ausente o `xsi:nil` se guarda como NULL con observación. Una consulta ya válida se reutiliza; documentos sin cambios no duplican gastos. Los originales se conservan comprimidos con gzip y SHA-256.

La cola está en SQL Server. El worker utiliza hasta **20 descargas simultáneas** por defecto (`WORKER_CONCURRENCY=1..20`), reintentos con espera creciente y recuperación por lease. La inserción y normalización conservan su bloqueo SQL global; subir las descargas puede aumentar esa espera. La publicación de detalle y modelo es transaccional. **Pausa/reanudación manual de lotes permanece pendiente**, según la decisión de alcance.

Las nuevas mediciones se guardan por intento en `analisis.MetricaIntento`, incluidos los fallidos. Para una instalación existente, aplica `sql/006_metricas.sql` con respaldo y los procesos detenidos. Los intentos anteriores no reciben tiempos inventados. Consulta [cómo interpretar y comparar las métricas](docs/METRICAS.md).

La documentación API está en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Autenticación por cookie/CSRF o token Bearer. Las sesiones viven en memoria de una única instancia API y se invalidan al reiniciarla.

### Limpieza e inspección del laboratorio

Administrador puede abrir **Mantenimiento** para inspeccionar respuestas originales, filtrar documentos por HTTP/calidad y eliminar un documento o todas las cargas. Cada eliminación exige vista previa, motivo y confirmación escrita; se rechaza si hay trabajos en curso o si cambió el alcance revisado. Se conservan cuentas, roles, configuración, toda la auditoría y el historial de métricas para comparar ensayos. No se reinician los identificadores.

En una instalación existente, antes de usar la limpieza aplica la migración de mantenimiento con API y worker detenidos y una copia de seguridad:

```powershell
.\uv.cmd run --frozen python scripts/aplicar_sql.py sql/005_mantenimiento.sql
```

**Ejecución del servicio** permite mostrar solo fallos e interrupciones. **Observaciones** filtra por severidad/campo/código y permite ver el Item afectado con su valor y la respuesta original. Las respuestas se muestran como texto, incluso si el servidor devolvió HTML.

## Conexión a SQL Server

El proyecto utiliza una instancia de SQL Server ya instalada, configurada mediante `.env`. Para una instancia local con autenticación de Windows, conserva `MSSQL_TRUSTED_CONNECTION=yes`. Para autenticación SQL, usa `MSSQL_TRUSTED_CONNECTION=no` y completa `MSSQL_USER` y `MSSQL_PASSWORD`.

La preparación inicial de la base necesita permisos administrativos; el rol `proinxml_app` define los permisos para una cuenta de aplicación. Python continúa en `.venv` y Vue se compila con pnpm.

## Verificación

```powershell
pnpm --dir frontend build
.\uv.cmd run --frozen python -m unittest discover -s tests -v
```

Las pruebas SQL son opcionales. Para ejecutar solo una prueba con un archivo XML, en una base aislada:

```powershell
.\uv.cmd run --frozen python scripts/verificar_esquema.py
$env:MSSQL_DATABASE='ProInXML_Validacion'
$env:PROINXML_RUN_SQL_TESTS='1'
.\uv.cmd run --frozen python -m unittest tests.test_sql_integration.SqlIntegrationTests.test_reconstruction_of_39_columns_and_no_bulk_row_audit -v
Remove-Item Env:MSSQL_DATABASE
Remove-Item Env:PROINXML_RUN_SQL_TESTS
```

Para revisar el navegador con Edge instalado:

```powershell
.\uv.cmd run --frozen --group browser python scripts/verify_ui.py
```

El script solicita la contraseña de administrador, usa el puerto temporal 8765 y cierra servidor/navegador al terminar. Consulta la base real y simula la carga de un XML para verificar HTTP 500 → recuperación, navegación SPA y pantallas de escritorio/móvil; no crea lotes ni descarga XML del MEF. Los accesos reales de QA quedan registrados.

Más información: [arquitectura](docs/ARQUITECTURA.md), [contrato XML](docs/CONTRATO_XML.md), [modelo relacional](docs/MODELO_3FN.md), [operación y reproceso](docs/OPERACION.md), [validación](docs/VALIDACION.md) y [especificación original](docs/ESPECIFICACION.md).
