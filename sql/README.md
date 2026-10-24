# Instalación SQL Server

Ejecutar desde la raíz del proyecto:

```powershell
.\uv.cmd run --frozen python scripts/aplicar_sql.py
```

Lee la conexión y `MSSQL_DATABASE` de `.env`. `--base-datos Nombre` permite elegir otra base. Necesita permisos administrativos para la instalación inicial.

| Orden | Contenido |
| --- | --- |
| 001_base.sql | Base, esquemas, tablas de integración/datos/seguridad/auditoría, relaciones y semillas |
| 002_modelo.sql | Entidades normalizadas y tabla de hechos |
| 003_normalizacion.sql | Procedimiento y vista de reconstrucción |
| 004_operacion.sql | Vistas de consulta, cola, triggers y permisos |
| 005_metricas.sql | Mediciones por intento e índices de análisis |

También se pueden ejecutar en ese orden desde SSMS sobre la base `ProInXML`. El instalador Python interpreta los separadores GO y adapta el nombre de base.

Los scripts crean el esquema final y se pueden reaplicar sobre una instalación actual. No borran cargas, usuarios o auditoría. No convierten automáticamente el antiguo prototipo `integracion.Fuente`; esa migración debe completarse antes de usar esta versión.

Para actualizar solo el normalizador con API y worker detenidos y una copia de seguridad:

```powershell
.\uv.cmd run --frozen python scripts/aplicar_sql.py sql/003_normalizacion.sql
```

002 y 003 se generan desde `app/model_schema.py` usando `scripts/desarrollo/build_model_sql.py`. Los SQL entregados ya están generados y listos para ejecutar.
