# Modelo relacional propuesto y datos de origen

El proyecto conserva dos representaciones. `staging.Gasto` registra los 39 campos
de cada Item, su documento y su ordinal. El esquema `modelo` organiza esos valores
en 30 entidades y una tabla de gasto con claves foraneas. No se elimina ni se
sustituye el registro de origen. `modelo.Gasto.Id` comparte la clave primaria de
`staging.Gasto`: cada ocurrencia y cada version mantiene su identidad.

## Correspondencia con el modelo resumido de siete áreas

La propuesta resumida `NivelGobierno / Sector / Pliego / UnidadEjecutora`,
`ClasificadorGasto`, `ProgramaPresupuestal / ProyectoActividad /
MetaPresupuestal`, `RubroRecurso`, `Departamento / Provincia / Distrito` y
`EjecucionGasto` representa las mismas áreas de negocio. El esquema existente
las descompone en tablas con claves y dependencias comprobables:

| Área propuesta | Tablas implementadas | Motivo de la descomposición |
|---|---|---|
| Institución | NivelGobierno, SubtipoGobierno, Sector, Pliego, Ejecutora, ContextoEjecutora | Los códigos hijos se identifican dentro de su padre; el contexto conserva SecEjec, mientras AnoEje pertenece al gasto. |
| Clasificador | CategoriaGasto, TipoTransaccion, Generica, Subgenerica, SubgenericaDetalle, Especifica, EspecificaDetalle | Cada nivel del clasificador tiene su propia clave y FK; una tabla con todos los códigos repetiría la jerarquía. |
| Presupuesto y meta | Funcion, ProgramaFuncional, ProgramaPresupuestal, Proyecto, ProyectoSNIP, Componente, SecuenciaFuncional, Meta, Finalidad, UnidadMedida | No se presupone que un IdMeta o un código de proyecto determine por sí solo los otros códigos. |
| Financiamiento | FuenteFinanciamiento, Rubro, TipoRecurso | El rubro depende de su fuente y el tipo de recurso de su rubro. |
| Ubicación | Departamento, Provincia, Distrito | Provincia se identifica dentro del departamento y distrito dentro de la provincia. Guardar también DepartamentoId en Distrito duplicaría la dependencia. |
| Otros | TipoActProy | Conserva códigos enteros observados, sin nombre ni familia presupuestal confirmada. |
| Transacción | Gasto | Contiene las FK, AnoEje, MesEje y los siete montos. Su Id coincide con el de staging.Gasto. |

Los Id de provincia, distrito, pliego, meta y ejecutora del XML no son claves
globales por sí solos. Por eso las restricciones UNIQUE incluyen el padre o el
contexto cuando corresponde. El código conserva ceros iniciales y
`Unidad_Medida` puede ser NULL.

La respuesta XML completa permanece comprimida en
`integracion.Documento.Respuesta`, con su SHA-256. La extracción plana permanece
en `staging.Gasto`. Ni la carga normal ni la reconstrucción manual sustituyen
esas dos representaciones: permiten comparar el origen con el modelo y volver a
normalizar sin consultar otra vez el enlace externo.

Un administrador puede usar **Mantenimiento → Reconstruir modelo** sobre un
documento válido. La operación toma las filas ya guardadas en `staging.Gasto`,
comprueba su cantidad, ejecuta el mismo normalizador transaccional de la carga,
verifica la cantidad del modelo y registra la acción en `auditoria.Cambio`.
No publica otra versión, no crea un lote y no altera el XML original. La carga
ordinaria continúa normalizando automáticamente cada documento válido.

La pantalla Modelo 3FN es el explorador de esta propuesta. La normalizacion se
basa en las dependencias y claves declaradas aqui; no equivale a disponer de un
modelo oficial completo del MEF. Las dependencias adicionales, nombres y vigencias
deben contrastarse con los maestros y el contrato completo del servicio antes de
cerrar un diseno definitivo de 3FN. Dividir una tabla en muchas no demuestra, por
si solo, la tercera forma normal.

## Entidades y claves

Todas las entidades tienen `Id` como PK. Sus combinaciones de codigo/contexto
tienen restricciones UNIQUE. Los campos que representan un padre tienen FK.

| Grupo | Tablas | Contexto de la clave |
|---|---|---|
| Instituciones | NivelGobierno, SubtipoGobierno, Sector, Pliego, Ejecutora | Codigo del nivel; codigo mas padre para cada hijo |
| Contexto institucional | ContextoEjecutora | EjecutoraId + SecEjec |
| Presupuesto | Funcion, ProgramaFuncional, ProgramaPresupuestal, CategoriaGasto | Codigo; el programa funcional se identifica dentro de Funcion |
| Clasificadores | TipoTransaccion, Generica, Subgenerica, SubgenericaDetalle, Especifica, EspecificaDetalle | Codigo mas el clasificador padre |
| Financiamiento | FuenteFinanciamiento, Rubro, TipoRecurso | Codigo; rubro dentro de fuente y recurso dentro de rubro |
| Proyectos | Proyecto, ProyectoSNIP, Componente | Cada codigo recibido, incluidos codigos genericos y cero |
| Metas | Finalidad, UnidadMedida, SecuenciaFuncional, Meta | Secuencia dentro de ContextoEjecutora; meta dentro de secuencia, finalidad y unidad |
| Ubicaciones | Departamento, Provincia, Distrito | Codigo departamental; provincia dentro de departamento; distrito dentro de provincia |
| Otros | TipoActProy | Código observado, sin nombre supuesto |
| Gasto normalizado | Gasto | Id compartido con el registro XML, FK a las entidades, año, mes y siete importes |

`modelo.TipoActProy` guarda únicamente `Id` interno y `Codigo` entero del XML.
No contiene `Nombre` ni una equivalencia asumida. El hecho referencia su `Id`;
la vista reconstruida obtiene el código de `modelo.TipoActProy.Codigo`.

El gasto contiene referencias a Meta, ProgramaFuncional, ProgramaPresupuestal,
CategoriaGasto, EspecificaDetalle, TipoRecurso, Proyecto, ProyectoSNIP, Componente,
Distrito y TipoActProy. El año y el mes permanecen en el hecho; ejecutora y
secuencia se recuperan recorriendo Meta -> SecuenciaFuncional ->
ContextoEjecutora -> Ejecutora. Los codigos de
clasificadores y de ubicacion se recuperan recorriendo sus padres. No se repiten
esos codigos ancestrales en el hecho normalizado.

## Claves conservadoras

- `AnoEje` y `MesEje` describen cada gasto, por lo que no forman parte de la clave
  de `ContextoEjecutora`. Las metas con los mismos códigos y contexto pueden
  compartir una fila entre ejercicios; el año de cada ocurrencia sigue en Gasto.
- No se fuerza una relacion uno a uno entre IdProyecto e IdProyectoSNIP ni se
  asignan nombres a codigos genericos como 3999999 o 0. El gasto conserva ambas
  referencias para cada ocurrencia.
- No se fuerza que una pareja SecFunc/IdMeta determine siempre la misma finalidad
  y unidad de medida. Esos valores forman parte de la clave de contexto de Meta,
  para conservar las variantes sin sobrescribirlas. Si el maestro confirma una
  dependencia mas estricta, se podra ajustar la restriccion natural y validar sus
  conflictos como una regla de negocio adicional.
- Los codigos de provincia y distrito se identifican con sus padres; un distrito
  `01` no se mezcla con el `01` de otra provincia. Los codigos especiales recibidos
  se conservan, sin atribuirles nombres o equivalencias no presentes en la fuente.
- El modelo conserva AnoEje, MesEje=0, ceros iniciales y DECIMAL(19,4).

```mermaid
erDiagram
    NivelGobierno ||--o{ SubtipoGobierno : contiene
    SubtipoGobierno ||--o{ Sector : contiene
    Sector ||--o{ Pliego : contiene
    Pliego ||--o{ Ejecutora : contiene
    Ejecutora ||--o{ ContextoEjecutora : contexto
    ContextoEjecutora ||--o{ SecuenciaFuncional : contiene
    SecuenciaFuncional ||--o{ Meta : contiene
    Finalidad ||--o{ Meta : identifica
    UnidadMedida |o--o{ Meta : mide
    Meta ||--o{ Gasto : referencia
    Proyecto ||--o{ Gasto : referencia
    TipoRecurso ||--o{ Gasto : financia
    EspecificaDetalle ||--o{ Gasto : clasifica
    Distrito ||--o{ Gasto : ubica
    RegistroXML ||--|| Gasto : misma_identidad
```

## Sincronizacion, auditoria y comprobacion

`modelo.NormalizarDocumento` carga las entidades en orden de dependencias y luego
el gasto. Se ejecuta en la misma transaccion que confirma los registros extraidos.
El bloqueo de aplicacion serializa la actualizacion del modelo y evita carreras
en las claves naturales. Una segunda ejecucion con el mismo contenido no agrega
entidades ni gastos, ni genera eventos por modificaciones inexistentes.

Las 30 tablas del modelo se auditan por documento mediante
`auditoria.CargaDocumento`, junto con el detalle. No tienen triggers por fila.
Los cambios operativos y de usuarios permanecen en `auditoria.Cambio`.
Las pantallas de exploración son de solo lectura; el modelo no sincroniza
ediciones SQL directas del detalle automáticamente.

`modelo.GastoReconstruido` obtiene los 39 campos desde las entidades y las FK,
sin tomarlos de las columnas del registro original. Las pruebas de integración
verifican reconstrucción e idempotencia con la muestra XML de pruebas.

`sql/002_modelo.sql` crea las entidades y restricciones; `sql/003_normalizacion.sql` instala el normalizador y la vista de reconstrucción. Ambos se generan desde el contrato Python.

`Unidad_Medida` es opcional: `Meta.UnidadMedidaId` acepta NULL, su clave natural
incluye ese valor y la comparación tolera nulos. Se usa LEFT JOIN al reconstruir;
no se crea una unidad ficticia. Las entidades y el hecho no duplican la fecha
de recepción del documento. Departamento, Provincia y Distrito admiten nombres
INEI; Provincia conserva además el nombre de región, incluido el caso especial
de Lima. Los códigos sin correspondencia mantienen el nombre NULL.
`modelo.GastoActual` limita el hecho a documentos vigentes. El bloqueo de
normalización se toma antes de insertar el detalle para evitar conflictos entre
documentos procesados en paralelo.

Referencias para revisar el diseno:
- [Principios de diseno y tercera forma normal, Microsoft](https://support.microsoft.com/en-us/access/database-design-basics).
- [Diccionario presupuestario, portal de datos del MEF](https://datosabiertos.mef.gob.pe/dataset/presupuesto-y-ejecucion-de-gasto-devengado-sectores/resource/cbb9626c-7fba-407e-95a0-60015c27b9fc).
- [Clasificadores presupuestarios del MEF](https://mef.gob.pe/index.php?Itemid=100290&id=356&lang=es&option=com_content&view=article).
