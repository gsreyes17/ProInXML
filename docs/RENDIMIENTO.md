# Normalizador de la versión 1.0

## Cambios

Las claves de entrada de `SecuenciaFuncional` y `Meta` se deduplican antes de resolver sus relaciones. Esto reduce joins repetidos sobre múltiples filas de gasto que comparten una misma clave. Se mantienen el bloqueo global, las restricciones únicas, la comparación de unidades nulas y la transacción por documento.

Una respuesta completamente validada con cero Items termina el normalizador antes de recorrer las entidades. La aplicación sigue publicándola como `CompletadoSinDatos` y conserva su auditoría y métricas.

No se agregó el índice experimental por código de secuencia: las mediciones no mostraron una mejora consistente. Tampoco se incluyeron dos variantes que actualizaban o enlazaban más tablas temporales: añadían coste en varios casos.

## Ensayo aislado

Se creó `ProInXML_V1_Validacion`, se instalaron los cinco SQL dos veces y se copiaron los catálogos reales: unas 264.899 metas y 263.531 secuencias. Se utilizaron seis documentos existentes, sin solicitudes HTTP. El procedimiento anterior y el candidato procesaron las mismas filas, alternando orden, con una vuelta de calentamiento y tres mediciones por variante. Se informa la mediana.

Las secuencias y metas correspondientes a cada documento se retiraron dentro de la transacción del ensayo para medir claves nuevas; cada medición se revirtió. Se comprobó el conteo y la reconstrucción de los 39 campos. Los hechos de la base aislada no tenían el volumen completo de producción.

| Items | Procedimiento anterior | Versión 1.0 | Diferencia observada |
| ---: | ---: | ---: | ---: |
| 0 | 7,80 ms | 2,64 ms | 66,2 % menos |
| 122 | 38,34 ms | 37,65 ms | 1,8 % menos |
| 787 | 109,42 ms | 102,77 ms | 6,1 % menos |
| 2.164 | 228,75 ms | 204,37 ms | 10,7 % menos |
| 8.266 | 680,06 ms | 679,58 ms | Similar |
| 15.735 | 984,57 ms | 1.010,69 ms | 2,7 % más |

Son mediciones locales de una muestra pequeña, no una promesa de mejora para todos los XML. En los documentos grandes no hay una mejora concluyente; la inserción del hecho y sus relaciones sigue costando tiempo. Los datos crudos del ensayo están en `.runtime/benchmark_normalizador_v1.json`.

## Referencia para próximas pruebas

La configuración predeterminada queda en ocho workers. Los ensayos con veinte mostraron esperas y timeouts del bloqueo; el lote posterior con ocho y muchas respuestas vacías estuvo dominado por latencia HTTP. Concurrencia y tiempos del origen deben evaluarse por separado del normalizador.

Para comparar cambios SQL, reproducir los mismos bytes sobre una base aislada con el mismo estado inicial. Reingresar URLs ya publicadas o forzar revisión con la misma huella mide reutilización. Las métricas actuales no distinguen conexión, espera de cabeceras y transferencia; ese desglose HTTP y la reutilización del cliente son posibles mejoras posteriores.
