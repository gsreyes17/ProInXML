# Diagrama de ProInXML para dbdiagram

El código listo para copiar está en [DIAGRAMA_BD.dbml.txt](DIAGRAMA_BD.dbml.txt). Abre un diagrama en [dbdiagram.io](https://dbdiagram.io), reemplaza su ejemplo con **todo el contenido del TXT** y utiliza DBML. El archivo es texto DBML sin marcas de Markdown: no debes incluir comillas de bloque ni convertirlo a SQL.

Se generó leyendo los metadatos reales de `ProInXML`: **45 tablas, 313 columnas, 47 claves foráneas y 13 grupos**. Incluye nombres físicos, tipos, nulabilidad, identidades, claves primarias, restricciones únicas, checks y valores predeterminados. Se validó con el analizador oficial `@dbml/core` 10.3.1. No contiene registros, hashes de usuarios ni credenciales de conexión.

## Agrupación por función

| Grupo | Tablas | Función |
| --- | ---: | --- |
| Sistema | 3 | Usuarios, roles y configuración del servicio |
| Integracion_y_cola | 4 | Lotes, consultas, trabajos e intentos con HTTP y tiempos |
| XML_y_calidad | 3 | Original recibido, 39 campos de detalle y observaciones |
| Auditoria | 3 | Cambios, cargas por documento y eventos de acceso |
| Analisis | 1 | Mediciones por intento, fases, filas y concurrencia para comparar ensayos |
| Catalogo | 1 | Tipo de actividad o proyecto |
| Modelo_gasto | 1 | Hecho normalizado de gasto |
| Modelo_instituciones | 6 | Gobierno, sector, pliego y ejecutoras por ejercicio |
| Modelo_presupuesto | 4 | Función, programas y categoría de gasto |
| Modelo_clasificadores | 6 | Jerarquía del clasificador de gasto |
| Modelo_financiamiento | 3 | Fuente, rubro y tipo de recurso |
| Modelo_proyectos_y_metas | 7 | Proyectos, componentes, metas, finalidad y unidad de medida |
| Modelo_ubicaciones | 3 | Departamento, provincia y distrito |

Los grupos y colores utilizan la sintaxis [TableGroup de DBML](https://dbml.dbdiagram.io/syntax/enrichment-visualization/#tablegroup). No alteran los esquemas SQL: por ejemplo, `seguridad.EventoAcceso` aparece junto a las otras bitácoras y `integracion.Servicio` junto a la configuración del sistema. Puedes mover los grupos visualmente en el editor para organizar la presentación.

## Cómo leer las relaciones

- `integracion.Documento` conserva la respuesta original comprimida. `datos.Gasto` contiene sus Items tipados; `modelo.Gasto` utiliza la misma identidad del detalle y lo relaciona con las entidades normalizadas.
- `Consulta.DocumentoActualId` referencia un documento de esa misma consulta mediante una FK compuesta. No es una relación simple que permita publicar un documento de otra URL.
- `Meta.UnidadMedidaId` admite NULL. No se crea una unidad ficticia para representar la ausencia de valor.
- `auditoria.CargaDocumento.DocumentoId` y `LoteId` son referencias históricas **sin FK** en el esquema final: la auditoría debe sobrevivir a la limpieza. Por ello no se dibujan líneas que simulen restricciones inexistentes. La FK de usuario permanece.
- `auditoria.Cambio.RegistroId` es un identificador asociado a `Tabla`; no es una FK a una única tabla. El valor 0 representa el evento de vaciado global cuando `Tabla=integracion.Documento`.
- `analisis.MetricaIntento` conserva identificadores históricos de intento, trabajo, lote y documento sin FK. Los datos de análisis sobreviven al vaciado del laboratorio para comparar ensayos; no se dibujan relaciones físicas inexistentes.

Las vistas `datos.GastoActual`, `datos.vw_GastoXML`, `modelo.GastoActual`, `modelo.GastoReconstruido` y `reportes.EjecucionServicio` no son tablas adicionales. Tampoco se incluyen procedimientos, triggers ni índices no únicos. Sus comportamientos se describen en [ARQUITECTURA.md](ARQUITECTURA.md). `dbo.sysdiagrams` pertenece a la herramienta de diagramas de SSMS y se excluye del modelo de la aplicación.

Las sesiones actuales de FastAPI están en memoria y no tienen una tabla física en este diagrama. La evolución hacia PostgreSQL sigue siendo una propuesta; este archivo representa SQL Server.

## Regenerar el TXT

Con la conexión habitual configurada en `.env` y la base actualizada:

```powershell
.\uv.cmd run --frozen python scripts/desarrollo/exportar_dbdiagram.py
```

El script consulta exclusivamente metadatos y escribe el TXT; no modifica la base. Para representar la base de validación, configura temporalmente `MSSQL_DATABASE=ProInXML_Validacion`. La sintaxis de tablas y referencias sigue la [documentación oficial de DBML](https://dbml.dbdiagram.io/docs/).
