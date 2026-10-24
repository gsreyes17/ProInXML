# Evaluación de rendimiento de las cargas

Evaluación del 23 de octubre de 2026, hora de Lima. Se consultaron las mediciones de `analisis.MetricaIntento`, estados de trabajos, índices y Query Store de `ProInXML`. No se modificaron datos, procedimientos, índices ni configuración. La captura detallada está en `.runtime/evaluacion_rendimiento_actual.json`, excluida del repositorio.

## Resultado del nuevo lote

| Medida | Lote 10052 | Lote 10053 |
| --- | ---: | ---: |
| Concurrencia registrada | 8 | 8 |
| Consultas completadas, incluyendo respuestas sin Items | 325 | 999 |
| Filas nuevas | 241.892 | 412.413 |
| Respuestas sin Items | 0 | 631 |
| Duración observada | 6 min 18 s | 34 min 12 s |
| Filas nuevas/s | 639,55 | 201,01 |
| Descarga promedio por intento | 3,62 s | 14,05 s |
| Espera SQL promedio por intento | 4,30 s | 1,06 s |
| Total promedio por intento | 9,11 s | 15,86 s |
| Total P95 por intento | 17,27 s | 26,07 s |
| Intentos fallidos | 0 | 8 |

Los ocho fallos del lote 10053 fueron `ReadTimeout: timed out` tras unos 45 segundos, con HTTP NULL. Los trabajos asociados terminaron `Completado`. No hubo fallos de bloqueo SQL en ese lote. Sus 999 trabajos finales se distribuyen en 368 `Completado` y 631 `CompletadoSinDatos`.

La descarga supone aproximadamente el 89 % del total promedio del nuevo lote. Sus respuestas con Items tardaron 15,15 s en promedio; las vacías tardaron 13,00 s aunque su cuerpo tenía solo 183 bytes. Esto apunta a latencia de respuesta; las mediciones actuales no separan conexión, espera de cabeceras y transferencia para distinguir su causa.

Los conjuntos son diferentes: el lote nuevo tiene muchas consultas sin datos y documentos de hasta 15.735 filas. Las filas/s incluyen el tiempo dedicado a consultar respuestas vacías. Esta caída de rendimiento no demuestra una regresión de la persistencia ni permite decidir la concurrencia óptima con estos lotes distintos.

## Hallazgos del código y SQL

1. `app/worker.py` crea y cierra un cliente HTTP por intento. Reutilizar un cliente por consumidor permitiría aprovechar conexiones persistentes, si el origen las admite. La ganancia requiere medición: no garantiza eliminar los 13 segundos de respuesta de una consulta vacía. [Clientes HTTPX](https://www.python-httpx.org/advanced/clients/).
2. Un XML válido sin Items ejecuta actualmente todo el normalizador. En las 631 respuestas vacías, esa fase promedió 109,87 ms: unos 69,3 segundos acumulados de trabajo serializado. Es tiempo SQL sumado; no se puede traducir directamente en 69,3 segundos menos de duración del lote porque coincide con descargas paralelas.
3. La inserción utiliza `cursor.executemany` en bloques de 500 filas, sin `fast_executemany`. Conviene ensayar envío de parámetros por lotes con tipos explícitos, conservando ceros, NULL y `Decimal`, y comprobar rollback completo. El tiempo de inserción promedio de los 368 documentos con datos fue 697,57 ms. [Documentación de pyodbc](https://github.com/mkleehammer/pyodbc/wiki/Cursor#executemanysql-params-with-fast_executemanytrue).
4. Query Store ya está activo. En las ventanas consultadas de las últimas cuatro horas, las sentencias que insertan `SecuenciaFuncional` y `Meta` fueron las mayores consumidoras acumuladas de CPU del normalizador. Es historial de múltiples cargas, no una atribución exclusiva al último lote. Ambas se ejecutaron unas 3.827 veces; sus tiempos medios observados fueron aproximadamente 146 y 168 ms respectivamente.
5. El normalizador resuelve repetidamente jerarquías mediante joins y utiliza temporales `#origen` y `#hechos`. Los candidatos son reutilizar claves ya resueltas, estudiar estimaciones y compilaciones y probar índices concretos a partir de los planes. Los planes guardados son planes compilados del historial, sin contadores de ejecución real por operador.
6. El motor sugiere índices sobre `datos.Gasto` y `modelo.SecuenciaFuncional`, entre otros. Ya existe un índice único `(DocumentoId,Ordinal)` en el detalle. La sugerencia de cubrir todas las columnas XML duplicaría una cantidad considerable de datos; requiere medir lecturas, espacio y coste de inserción antes de adoptarla. No se añadieron índices automáticamente.

Query Store conserva consultas, planes y estadísticas por intervalos. Sus datos sirven para seleccionar experimentos, pero no identifican por sí solos el tiempo de una solicitud concreta del lote. [Documentación de Microsoft](https://learn.microsoft.com/en-us/sql/relational-databases/performance/monitoring-performance-by-using-the-query-store).

## Orden de experimentos propuesto

1. **Separar tiempos HTTP:** medir hasta recepción de cabeceras y después lectura del cuerpo; para conexión/DNS utilizar instrumentación del transporte. Mantener el tiempo total actual y diferenciar timeout de red, HTTP fallido y espera SQL en el resumen. Mostrar también XML con/sin Items para interpretar filas/s.
2. **Ensayar reutilización del cliente HTTP:** mantener inicialmente ocho consumidores, límites, circuito y política de reintentos. Medir una muestra pequeña y equivalente antes/después, sin una nueva descarga masiva.
3. **Evitar normalización de documentos vacíos:** solo después de validar el XML completo y confirmar que tiene cero Items. Mantener publicación, auditoría, idempotencia y estado `CompletadoSinDatos`. Verificarlo en la base aislada.
4. **Comparar inserción actual con envío de parámetros por lotes:** reproducir originales guardados en `ProInXML_Validacion`, con el mismo estado inicial. Verificar los 39 campos, precisión decimal, unidades NULL y reversión de documentos truncados. Cambiar una variable por ensayo.
5. **Optimizar `Meta` y `SecuenciaFuncional`:** contrastar planes, lecturas y CPU con documentos de tamaños y estructuras variados. Medir antes de decidir índices, recompilaciones o reescrituras.
6. **Revisar concurrencia después:** una prueba controlada de 8 frente a 12 puede ser útil cuando domina la latencia HTTP, pero puede volver a saturar la etapa SQL en lotes densos o aumentar la presión sobre el origen. Los lotes existentes no demuestran que 12 sea mejor.

La referencia de SQL debe reproducir los mismos bytes originales sobre una base aislada restablecida al mismo punto. Forzar revisión de documentos ya válidos mide reutilización; un fixture con un único Item no representa estas cargas. Las descargas reales se prueban por separado porque el servicio y la red varían con el tiempo.

La arquitectura actual conserva un bloqueo global durante la validación, inserción y normalización. Acortar ese tramo sigue siendo una mejora posible para lotes con muchos datos; paralelizar escrituras requiere revisar entidades compartidas e interbloqueos. El nuevo lote muestra que ese trabajo debe distinguirse de las esperas del servicio HTTP.
