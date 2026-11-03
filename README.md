# ProInXML 1.0

Integración de XML del MEF con **FastAPI, SQL Server y Vue 3**. Registra URLs o un Excel, procesa descargas con reintentos y permite consultar los datos originales, el modelo relacional, la calidad y la auditoría.

## Preparar e iniciar

Requisitos: Windows, Python 3.11+, Node 22.12+, pnpm 11, SQL Server 2019+ en ejecución y Microsoft ODBC Driver 18.

En una instalación nueva, desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/preparar.ps1
Copy-Item .env.example .env
# Ajustar la conexión SQL en .env.
$env:PYTHONPYCACHEPREFIX = Join-Path (Get-Location) '.runtime\pycache'
.\.venv\Scripts\python.exe scripts/aplicar_sql.py
.\iniciar.cmd
```

Abre **http://127.0.0.1:5173**. `iniciar.cmd` inicia FastAPI en 8000, Vue/Vite en 5173 y el worker. Ctrl+C detiene los procesos iniciados. La instalación crea dos cuentas de laboratorio:

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| `administrador` | `Admin123456!` | Administrador |
| `operador` | `Operador123456!` | Operador |

Estas claves son deliberadamente sencillas para el laboratorio. Cámbialas desde Usuarios antes de publicar el sistema en una red compartida.

`preparar.ps1` crea `.venv` con Python y ejecuta `pip install -r requirements.txt`; Vue se instala con pnpm. También puedes instalar solo Python con `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. `iniciar.cmd` y `preparar.ps1` centralizan la caché de Python en `.runtime/pycache`; para comandos Python manuales usa la variable de entorno del ejemplo anterior.

Para servir Vue compilado desde FastAPI en un único puerto, ejecuta `iniciar.cmd --compilado` y abre http://127.0.0.1:8000. Este modo no necesita Node durante la ejecución. Compila los cambios de Vue con `pnpm --dir frontend build`.

## Actualizar esta instalación

Conserva `.env`, las cuentas y la base. Detén API y worker, respalda SQL Server y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/preparar.ps1
$env:PYTHONPYCACHEPREFIX = Join-Path (Get-Location) '.runtime\pycache'
.\.venv\Scripts\python.exe scripts/aplicar_sql.py
.\iniciar.cmd
```

Los cinco SQL son repetibles sobre el esquema actual y no vacían las cargas. El instalador migra `datos.Gasto` a `staging.Gasto` conservando filas e IDs y carga los nombres INEI de `data_models/ubigeo_distrito.csv`. Para aplicar únicamente el normalizador: `.\.venv\Scripts\python.exe scripts/aplicar_sql.py sql/003_normalizacion.sql`. El antiguo prototipo con `integracion.Fuente` requiere una migración previa y no forma parte del instalador.

## Navegación

| Grupo | Pantallas |
| --- | --- |
| Procesamiento | Carga de datos, Seguimiento, Ejecución del servicio, Métricas de carga |
| Consultas | Registros XML, Modelo 3FN, Observaciones |
| Administración | Auditoría, Usuarios, Mantenimiento |

Las opciones de administración son exclusivas de Administrador. Operador puede cargar y reintentar; Consulta dispone de las pantallas de lectura. Seguimiento y métricas se actualizan cada tres segundos. En móvil, el botón Menú permite abrir la navegación agrupada.

## Estructura

```text
app/
  run.py                 Inicia API, worker y cliente Vue
  api/                   Rutas HTTP, autenticación y entrega de Vue
  integration/           Cola, descarga, reintentos, métricas y normalización
  domain/                Contrato XML y definición del modelo relacional
  infrastructure/        Configuración, conexión SQL y bloqueos
frontend/src/            Pantallas y componentes Vue/TypeScript
sql/                     Scripts ordenados de instalación y reinicio
scripts/
  preparar.ps1           Instala dependencias y compila Vue
  aplicar_sql.py         Crea o actualiza la base
  cargar_ubigeo.py       Repite la carga de nombres INEI si cambia el CSV
  crear_admin.py         Crea otro administrador cuando haga falta
  desarrollo/            Generador de los SQL 002 y 003
tests/                   Pruebas de integridad, permisos, cola y API
data_models/URLs.xlsx    Libro de URLs de referencia del laboratorio
data_models/ubigeo_distrito.csv  Nombres geográficos INEI para las tablas del modelo
docs/                    Arquitectura, contrato XML, operación y diagrama
iniciar.cmd              Inicia API, worker y Vue
requirements.txt         Dependencias Python para pip
frontend/pnpm-lock.yaml  Dependencias Vue
```

La configuración está en `.env`; `.env.example` contiene los valores de referencia. La base predeterminada es `ProInXML`, con autenticación Windows local. También admite autenticación SQL. El worker usa **8 descargas simultáneas**, configurable entre 1 y 20; la carga manual admite **1.000 URLs**.

Los originales se conservan con gzip y SHA-256. `staging.Gasto` guarda los 39 campos y `modelo` sus entidades relacionadas. Se conserva `AnoEje`, los ceros de los códigos y los decimales exactos. `modelo.TipoActProy` guarda cada código numérico observado sin nombre ni significado supuesto. `Unidad_Medida` vacía, ausente o nil se guarda como NULL con advertencia. Los nombres de departamento, provincia, región y distrito se enriquecen desde el CSV INEI; códigos especiales sin correspondencia conservan el nombre NULL. Una consulta ya válida se reutiliza.

## Verificación opcional

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
pnpm --dir frontend build
```

Las pruebas SQL están desactivadas por defecto. Su preparación y ejecución aislada se explican en [VALIDACION.md](docs/VALIDACION.md). No es necesario ejecutar pruebas ni generadores para iniciar la aplicación.

## Documentación

- [Flujos y comportamiento del sistema](docs/FLUJOS_SISTEMA.md) y [presentación PowerPoint](docs/presentacion/ProInXML_flujos_1.0.pptx)
- [Guía de pantallas y acciones](docs/GUIA_PANTALLAS.md)
- [Arquitectura y base de datos](docs/ARQUITECTURA.md)
- [Diagrama visual de la arquitectura](docs/DIAGRAMA_ARQUITECTURA.md)
- [Contrato de los 39 campos](docs/CONTRATO_XML.md) y [modelo relacional](docs/MODELO_3FN.md)
- [Operación y configuración](docs/OPERACION.md)
- [Métricas](docs/METRICAS.md)
- [Diagrama para dbdiagram](docs/DIAGRAMA_BD.md)
- API: http://127.0.0.1:8000/docs

`.gitignore` excluye `.env`, el entorno virtual, dependencias, compilados, cachés, logs y respaldos. Las contraseñas de las cuentas de laboratorio se almacenan como hashes Argon2id. Las sesiones de la API están en memoria de una única instancia; reiniciar requiere iniciar sesión de nuevo. Pausar/reanudar lotes manualmente queda pendiente.
