# Validación de la versión 1.0

## Pruebas opcionales

Estas herramientas son para desarrollo. La instalación y el arranque solo necesitan los comandos del README.

```powershell
.\uv.cmd run --frozen python -m unittest discover -s tests -v
pnpm --dir frontend build
```

Las pruebas SQL se omiten salvo activación explícita. Para prepararlas y ejecutarlas en la base aislada:

```powershell
.\uv.cmd run --frozen python scripts/desarrollo/verificar_esquema.py
$env:MSSQL_DATABASE='ProInXML_Validacion'
$env:PROINXML_RUN_SQL_TESTS='1'
try {
    .\uv.cmd run --frozen python -m unittest discover -s tests -v
} finally {
    Remove-Item Env:MSSQL_DATABASE
    Remove-Item Env:PROINXML_RUN_SQL_TESTS
}
```

Mantenimiento y concurrencia se prueban exclusivamente en `ProInXML_Validacion`. Las pruebas de integración revierten sus transacciones; el ensayo de 20 descargas simuladas conserva sus documentos técnicos en esa base. No se realizan solicitudes al MEF.

Para revisar la interfaz con Edge instalado:

```powershell
.\uv.cmd sync --frozen --group browser
.\uv.cmd run --frozen --group browser python tests/verificar_interfaz.py
```

El servidor temporal usa 8766 y se cierra al terminar. Todas las respuestas API se simulan; no crea lotes ni borra datos reales. Las capturas y resultados quedan en `.runtime`.

## Comprobaciones realizadas

- **69 pruebas**: API, permisos, CSRF, lector, decimales, NULL, idempotencia, versiones, cola, reintentos, leases, métricas, limpieza y reconstrucción de los 39 campos.
- Caso nuevo de 600 Items con claves repetidas, distintos contextos y unidades nulas; conserva tres metas diferentes y es idempotente al normalizar otra vez.
- XML vacío confirmado sin crear entidades ni hechos.
- Instalación limpia y reaplicación de los cinco SQL en `ProInXML_V1_Validacion`: 45 tablas, todas con CreadoUtc, y vista XML de 39 columnas.
- También se comprobó la instalación final en `ProInXML_Instalacion_Validacion`, y la API/Vite reales con conexión aislada y sin worker.
- Vue/TypeScript y navegador de escritorio/móvil: navegación por grupos, menú móvil, restricciones por rol, métricas automáticas, entrada de 1.000 URLs y mantenimiento simulado.
- Comparación del procedimiento anterior con el nuevo usando seis documentos reales guardados y catálogos copiados a una base aislada. Los resultados y límites están en [RENDIMIENTO.md](RENDIMIENTO.md).

Las pruebas conservadas protegen operaciones de datos y seguridad. Se retiraron scripts de migración del prototipo, perfilado puntual y ensayos sintéticos que no representaban los XML actuales.

## Herramientas de desarrollo

| Archivo | Uso |
| --- | --- |
| `scripts/desarrollo/build_model_sql.py` | Regenera 002 y 003 desde el contrato Python |
| `scripts/desarrollo/exportar_dbdiagram.py` | Regenera el DBML leyendo metadatos |
| `scripts/desarrollo/verificar_esquema.py` | Instala y reaplica SQL en la base aislada |
| `scripts/desarrollo/verificar_integridad.py` | Verifica originales, huellas y reconstrucción completa; puede ser costoso con millones de filas |

Los generadores no forman parte del arranque. Los respaldos, originales técnicos de los ensayos y archivos sustituidos durante esta preparación se conservaron dentro de `.runtime`, excluida de Git.

El procedimiento 1.0 se aplicó a `ProInXML` después de un respaldo COPY_ONLY con CHECKSUM y RESTORE VERIFYONLY. Se conservaron 3.830 documentos, 2.857.769 filas XML y sus hechos, 264.899 metas, 263.531 secuencias y 3.349 mediciones. La evidencia está en `.runtime/version_1_aplicada.json`; no se ejecutaron cargas externas ni una limpieza permanente.
