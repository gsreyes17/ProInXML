# Validaci?n del proyecto

La instalaci?n y el arranque no requieren ejecutar pruebas. Para comprobar el backend y el cliente desde la ra?z del proyecto:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path (Get-Location) '.runtime\pycache'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
pnpm --dir frontend build
```

Las pruebas de `test_sql_integration.py` se omiten por defecto. Para ejecutarlas, prepara primero una base aislada y configura `MSSQL_DATABASE=ProInXML_Validacion` junto con `PROINXML_RUN_SQL_TESTS=1`. No ejecutes estas pruebas sobre la base principal: algunos casos ejercitan limpieza y concurrencia.

`scripts/desarrollo/build_model_sql.py` es una herramienta de mantenimiento: regenera `sql/002_modelo.sql` y `sql/003_normalizacion.sql` a partir de `app/domain/model_schema.py`. Los SQL entregados ya est?n generados; no hace falta ejecutar el generador para instalar ni iniciar.

El XML de `tests/fixtures/` es una muestra peque?a y cerrada para probar el lector sin consultar el servicio externo.
