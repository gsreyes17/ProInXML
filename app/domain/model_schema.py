"""Modelo relacional propuesto para los codigos presentes en el XML.

Las claves de contexto conservan las combinaciones recibidas; no se presuponen
maestros oficiales ni dependencias adicionales proyecto/SNIP o meta/finalidad.
"""

from dataclasses import dataclass

from app.domain.xml_reader import MONEY_FIELDS


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str = "varchar(32)"
    source: str | None = None
    reference: str | None = None
    nullable: bool = False


def code(source, name="Codigo"):
    return Column(name, source=source)


def ref(table, name=None, nullable=False):
    return Column(name or table + "Id", "bigint", reference=table, nullable=nullable)


# Orden topologico: primero cada padre, despues los hijos.
ENTITIES = {
    "NivelGobierno": (
        "Instituciones",
        "Niveles de gobierno",
        [code("IdNivelGobierno")],
    ),
    "SubtipoGobierno": (
        "Instituciones",
        "Subtipos de gobierno",
        [ref("NivelGobierno"), code("Sub_tipo_gobierno")],
    ),
    "Sector": ("Instituciones", "Sectores", [ref("SubtipoGobierno"), code("IdSector")]),
    "Pliego": ("Instituciones", "Pliegos", [ref("Sector"), code("IdPliego")]),
    "Ejecutora": (
        "Instituciones",
        "Unidades ejecutoras",
        [ref("Pliego"), code("IdEjecutora")],
    ),
    "ContextoEjecutora": (
        "Instituciones",
        "Contextos de ejecutora",
        [
            ref("Ejecutora"),
            Column("SecEjec", "int", "SecEjec"),
        ],
    ),
    "Funcion": ("Presupuesto", "Funciones", [code("Funcion")]),
    "ProgramaFuncional": (
        "Presupuesto",
        "Programas funcionales",
        [ref("Funcion"), code("Programa")],
    ),
    "ProgramaPresupuestal": (
        "Presupuesto",
        "Programas presupuestales",
        [code("Programa_ppto")],
    ),
    "CategoriaGasto": ("Presupuesto", "Categorias de gasto", [code("Categ_gasto")]),
    "TipoTransaccion": (
        "Clasificadores",
        "Tipos de transaccion",
        [code("Tipo_transaccion")],
    ),
    "Generica": (
        "Clasificadores",
        "Genericas",
        [ref("TipoTransaccion"), code("Generica")],
    ),
    "Subgenerica": (
        "Clasificadores",
        "Subgenericas",
        [ref("Generica"), code("Subgenerica")],
    ),
    "SubgenericaDetalle": (
        "Clasificadores",
        "Subgenericas en detalle",
        [ref("Subgenerica"), code("Subgenerica_det")],
    ),
    "Especifica": (
        "Clasificadores",
        "Especificas",
        [ref("SubgenericaDetalle"), code("Especifica")],
    ),
    "EspecificaDetalle": (
        "Clasificadores",
        "Especificas en detalle",
        [ref("Especifica"), code("Especifica_det")],
    ),
    "FuenteFinanciamiento": (
        "Financiamiento",
        "Fuentes de financiamiento",
        [code("IdFuente")],
    ),
    "Rubro": (
        "Financiamiento",
        "Rubros",
        [ref("FuenteFinanciamiento"), code("IdRubro")],
    ),
    "TipoRecurso": (
        "Financiamiento",
        "Tipos de recurso",
        [ref("Rubro"), code("IdTipoRecurso")],
    ),
    "Proyecto": ("Proyectos y metas", "Codigos de proyecto", [code("IdProyecto")]),
    "ProyectoSNIP": ("Proyectos y metas", "Codigos SNIP", [code("IdProyectoSNIP")]),
    "Componente": ("Proyectos y metas", "Componentes", [code("IdComponente")]),
    "Finalidad": ("Proyectos y metas", "Finalidades", [code("IdFinalidad")]),
    "UnidadMedida": (
        "Proyectos y metas",
        "Unidades de medida",
        [code("Unidad_Medida")],
    ),
    "SecuenciaFuncional": (
        "Proyectos y metas",
        "Secuencias funcionales",
        [ref("ContextoEjecutora"), code("SecFunc")],
    ),
    "Meta": (
        "Proyectos y metas",
        "Metas por contexto",
        [
            ref("SecuenciaFuncional"),
            code("IdMeta"),
            ref("Finalidad"),
            ref("UnidadMedida", nullable=True),
        ],
    ),
    "Departamento": ("Ubicaciones", "Departamentos", [code("Departamento")]),
    "Provincia": (
        "Ubicaciones",
        "Provincias",
        [ref("Departamento"), code("Provincia")],
    ),
    "Distrito": ("Ubicaciones", "Distritos", [ref("Provincia"), code("Distrito")]),
    "TipoActProy": (
        "Otros",
        "Codigos TipoActProy",
        [Column("Codigo", "bigint", "TipoActProy")],
    ),
}
FACT_COLUMNS = [
    ref(t)
    for t in (
        "Meta",
        "ProgramaFuncional",
        "ProgramaPresupuestal",
        "CategoriaGasto",
        "EspecificaDetalle",
        "TipoRecurso",
        "Proyecto",
        "ProyectoSNIP",
        "Componente",
        "Distrito",
        "TipoActProy",
    )
] + [
    Column("AnoEje", "smallint", "AnoEje"),
    Column("MesEje", "tinyint", "MesEje"),
]
FACT_COLUMNS += [Column(name, "decimal(19,4)", name) for name in MONEY_FIELDS]


def registry():
    result = []
    for name, (group, label, columns) in ENTITIES.items():
        result.append(
            {
                "tabla": name,
                "nombre": label,
                "grupo": group,
                "columnas": ["Id"]
                + [c.name for c in columns]
                + (
                    ["Nombre"]
                    if name in ("Departamento", "Provincia", "Distrito")
                    else []
                )
                + (["NombreRegion"] if name == "Provincia" else []),
                "relaciones": [
                    {"columna": c.name, "tabla": c.reference}
                    for c in columns
                    if c.reference
                ],
            }
        )
    result.append(
        {
            "tabla": "Gasto",
            "nombre": "Gasto normalizado",
            "grupo": "Gasto normalizado",
            "columnas": ["Id"] + [c.name for c in FACT_COLUMNS],
            "relaciones": [
                {"columna": c.name, "tabla": c.reference}
                for c in FACT_COLUMNS
                if c.reference
            ]
            + [
                {"columna": "Id", "tabla": "XML"},
            ],
        }
    )
    return result
