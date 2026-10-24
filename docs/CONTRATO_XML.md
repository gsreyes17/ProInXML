# Contrato de los 39 campos XML

Perfil previo a la migración: 7 documentos reales almacenados, 10.719 Items. Ningún documento resultó ilegible. Los 39 campos estuvieron presentes en todos los Items. Hubo 71 unidades de medida vacías; los demás campos no tuvieron valores vacíos ni formatos anómalos en esta muestra. No se observaron etiquetas ausentes ni `xsi:nil` reales; esos casos se cubren con pruebas automatizadas.

Todos los valores se recortan en los extremos. Los códigos conservan los ceros originales, sin rellenarlos ni asignar nombres. El parser exige el namespace `http://www.mef.gob.pe/` y la raíz `DataGasto`. Rechaza DTD, entidades, campos duplicados, campos desconocidos y documentos incompletos.

| Orden | Campo | Tipo SQL | Obligación | Vacíos observados | Si llega vacío o falta |
| --- | --- | --- | --- | --- | --- |
| 1 | `AnoEje` | SMALLINT | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 2 | `MesEje` | TINYINT | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 3 | `IdNivelGobierno` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 4 | `Sub_tipo_gobierno` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 5 | `IdSector` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 6 | `IdPliego` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 7 | `IdEjecutora` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 8 | `SecEjec` | INT | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 9 | `Funcion` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 10 | `Programa` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 11 | `Programa_ppto` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 12 | `Categ_gasto` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 13 | `Tipo_transaccion` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 14 | `Generica` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 15 | `Subgenerica` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 16 | `Subgenerica_det` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 17 | `Especifica` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 18 | `Especifica_det` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 19 | `SecFunc` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 20 | `IdFuente` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 21 | `IdRubro` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 22 | `IdTipoRecurso` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 23 | `IdComponente` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 24 | `IdProyecto` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 25 | `TipoActProy` | BIGINT | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 26 | `IdMeta` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 27 | `IdFinalidad` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 28 | `IdProyectoSNIP` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 29 | `Departamento` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 30 | `Provincia` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 31 | `Distrito` | VARCHAR(32) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 32 | `Unidad_Medida` | VARCHAR(32) | Opcional | 71 | NULL + Advertencia con código del caso |
| 33 | `PIA` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 34 | `PIM` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 35 | `Certificado` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 36 | `CompAnual` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 37 | `AtencionCompMensual` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 38 | `Devengado` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |
| 39 | `Girado` | DECIMAL(19,4) | Obligatorio | 0 | Rechazar documento; conservar respuesta original |

Reglas adicionales:

- `AnoEje`, `IdNivelGobierno` y `SecEjec` deben coincidir con los parámetros de la consulta; el año está entre 1900 y 2100 y la ejecutora es positiva.
- `MesEje` admite 0 a 12. No se inventa el significado de 0.
- Los códigos requieren de 1 a 32 caracteres, salvo Unidad_Medida opcional. `036` permanece `036`.
- Los importes deben ser finitos, tener hasta cuatro decimales y caber en DECIMAL(19,4). No se redondea un valor que excede la escala.
- `TipoActProy` 2/3 admite normalización. Otro entero representable se conserva en el detalle con `TIPO_ACT_PROY_INVALIDO`, severidad Error; el documento no se publica.
- Unidad vacía o espacios genera `UNIDAD_VACIA`; ausente, `UNIDAD_AUSENTE`; `xsi:nil=true/1`, `UNIDAD_NIL`. Las tres producen NULL y Advertencia, sin bloquear.
- En los 71 vacíos reales, `IdMeta` e `IdFinalidad` fueron ambos `99999`. Es un hallazgo de la muestra, no una dependencia impuesta a toda la fuente.

El script `scripts/perfilar_xml.py` acepta carpeta/lista de XML o `--base-datos`; genera un JSON con presentes, vacíos, ausentes, nil y formatos raros para cada campo. Si el servicio presenta otros casos, el contrato debe revisarse explícitamente antes de ampliar campos nulos.
