# ProInXML 1.0

Integración de XML del MEF con **FastAPI, SQL Server y Vue 3**. Registra URLs o un Excel, procesa descargas con reintentos y permite consultar los datos originales, el modelo relacional, la calidad y la auditoría.

## Preparar e iniciar

Requisitos: Windows, Python 3.11+, Node 22.12+, pnpm 11, SQL Server 2019+ en ejecución y Microsoft ODBC Driver 18.

En una instalación nueva, desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/preparar.ps1
Copy-Item .env.example .env
# Ajustar la conexión SQL en .env.
.\uv.cmd run --frozen python scripts/aplicar_sql.py
.\uv.cmd run --frozen python scripts/crear_admin.py
.\iniciar.cmd
```

Abre **http://127.0.0.1:5173**. `iniciar.cmd` inicia FastAPI en 8000, Vue/Vite en 5173 y el worker. Ctrl+C detiene los procesos iniciados. No hay credenciales predeterminadas; el administrador se crea con una contraseña elegida en terminal.

`preparar.ps1` instala uv dentro de `.tools` y sincroniza Python y Vue con sus lockfiles. Con uv ya instalado se puede usar `uv sync --frozen`. Python trabaja en `.venv`; Vue se gestiona con pnpm.

Para servir Vue compilado desde FastAPI en un único puerto, ejecuta `iniciar.cmd --compilado` y abre http://127.0.0.1:8000. Este modo no necesita Node durante la ejecución. Compila los cambios de Vue con `pnpm --dir frontend build`.

## Actualizar esta instalación

Conserva `.env`, las cuentas y la base. Detén API y worker, respalda SQL Server y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/preparar.ps1
.\uv.cmd run --frozen python scripts/aplicar_sql.py
.\iniciar.cmd
```

Los cinco SQL son repetibles sobre el esquema actual y no vacían las cargas. Para aplicar únicamente el normalizador 1.0: `uv.cmd run --frozen python scripts/aplicar_sql.py sql/003_normalizacion.sql`. El antiguo prototipo con `integracion.Fuente` requiere una migración previa y no forma parte del instalador 1.0.

## Navegación

| Grupo | Pantallas |
| --- | --- |
| Procesamiento | Carga de datos, Seguimiento, Ejecución del servicio, Métricas de carga |
| Consultas | Registros XML, Modelo 3FN, Observaciones |
| Administración | Auditoría, Usuarios, Mantenimiento |

Las opciones de administración son exclusivas de Administrador. Operador puede cargar y reintentar; Consulta dispone de las pantallas de lectura. Seguimiento y métricas se actualizan cada tres segundos. En móvil, el botón Menú permite abrir la navegación agrupada.

## Estructura

```text
app/                     API, seguridad, persistencia y worker Python
frontend/src/            Pantallas y componentes Vue/TypeScript
sql/                     Cinco scripts ordenados de instalación
scripts/
  preparar.ps1           Instala dependencias y compila Vue
  aplicar_sql.py         Crea o actualiza la base
  crear_admin.py         Crea la cuenta inicial
  desarrollo/            Generación del modelo, diagrama y comprobaciones SQL
tests/                   Pruebas de integridad, permisos, cola y API
XML_models/URLs.xlsx     Libro de URLs de referencia del laboratorio
docs/                    Arquitectura, contrato XML, operación y diagrama
iniciar.cmd              Inicia API, worker y Vue
uv.lock                  Dependencias Python
frontend/pnpm-lock.yaml  Dependencias Vue
```

La configuración está en `.env`; `.env.example` contiene los valores de referencia. La base predeterminada es `ProInXML`, con autenticación Windows local. También admite autenticación SQL. El worker usa **8 descargas simultáneas**, configurable entre 1 y 20; la carga manual admite **1.000 URLs**.

Los originales se conservan con gzip y SHA-256. `datos.Gasto` guarda los 39 campos y `modelo` sus entidades relacionadas. Se conserva `AnoEje`, los ceros de los códigos y los decimales exactos. `Unidad_Medida` vacía, ausente o nil se guarda como NULL con advertencia. Una consulta ya válida se reutiliza.

## Verificación opcional

```powershell
.\uv.cmd run --frozen python -m unittest discover -s tests -v
pnpm --dir frontend build
```

Las pruebas SQL están desactivadas por defecto. Su preparación y ejecución aislada se explican en [VALIDACION.md](docs/VALIDACION.md). No es necesario ejecutar pruebas ni generadores para iniciar la aplicación.

## Documentación

- [Arquitectura y base de datos](docs/ARQUITECTURA.md)
- [Contrato de los 39 campos](docs/CONTRATO_XML.md) y [modelo relacional](docs/MODELO_3FN.md)
- [Operación y configuración](docs/OPERACION.md)
- [Métricas](docs/METRICAS.md) y [resultados del normalizador 1.0](docs/RENDIMIENTO.md)
- [Diagrama para dbdiagram](docs/DIAGRAMA_BD.md)
- API: http://127.0.0.1:8000/docs

`.gitignore` excluye `.env`, entornos, dependencias, compilados, cachés, logs y respaldos. `proinxml.egg-info` es metadata generada al instalar Python; tampoco se publica. No se incluyen claves ni usuarios predeterminados. Las sesiones de la API están en memoria de una única instancia; reiniciar requiere iniciar sesión de nuevo. Pausar/reanudar lotes manualmente queda pendiente.
