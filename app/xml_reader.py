"""Contrato observado en la muestra; no se reparan documentos incompletos."""
from decimal import Decimal, InvalidOperation
from io import BytesIO
import hashlib
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from defusedxml.ElementTree import iterparse

NS = "http://www.mef.gob.pe/"
ENDPOINT = "/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2"
INTEGER_FIELDS = ("AnoEje", "MesEje", "SecEjec", "TipoActProy")
CODE_FIELDS = (
    "IdNivelGobierno", "Sub_tipo_gobierno", "IdSector", "IdPliego", "IdEjecutora",
    "Funcion", "Programa", "Programa_ppto", "Categ_gasto", "Tipo_transaccion",
    "Generica", "Subgenerica", "Subgenerica_det", "Especifica", "Especifica_det",
    "SecFunc", "IdFuente", "IdRubro", "IdTipoRecurso", "IdComponente", "IdProyecto",
    "IdMeta", "IdFinalidad", "IdProyectoSNIP", "Departamento", "Provincia",
    "Distrito", "Unidad_Medida",
)
MONEY_FIELDS = ("PIA", "PIM", "Certificado", "CompAnual", "AtencionCompMensual", "Devengado", "Girado")
FIELDS = (
    "AnoEje", "MesEje", "IdNivelGobierno", "Sub_tipo_gobierno", "IdSector", "IdPliego",
    "IdEjecutora", "SecEjec", "Funcion", "Programa", "Programa_ppto", "Categ_gasto",
    "Tipo_transaccion", "Generica", "Subgenerica", "Subgenerica_det", "Especifica", "Especifica_det",
    "SecFunc", "IdFuente", "IdRubro", "IdTipoRecurso", "IdComponente", "IdProyecto", "TipoActProy",
    "IdMeta", "IdFinalidad", "IdProyectoSNIP", "Departamento", "Provincia", "Distrito", "Unidad_Medida",
    *MONEY_FIELDS,
)


def canonical_source(url: str) -> dict:
    parts = urlsplit(url.strip())
    if (parts.scheme not in ("http", "https") or parts.netloc.lower() != "s3.mef.gob.pe"
            or parts.path != ENDPOINT or parts.fragment):
        raise ValueError("Se admite solamente el endpoint MEF del Excel, por HTTP o HTTPS.")
    query = parse_qs(parts.query, keep_blank_values=True)
    if set(query) != {"anoEje", "nivelGobierno", "sec_ejec"} or any(len(v) != 1 for v in query.values()):
        raise ValueError("Parametros de URL ausentes, repetidos o desconocidos.")
    try:
        year, unit = int(query["anoEje"][0]), int(query["sec_ejec"][0])
    except ValueError as exc:
        raise ValueError("Ano y unidad ejecutora deben ser enteros.") from exc
    level = query["nivelGobierno"][0]
    if not 1900 <= year <= 2100 or not 1 <= unit <= 2147483647 or level not in ("E", "M", "R"):
        raise ValueError("Parametros MEF fuera del dominio admitido.")
    canonical = urlunsplit((parts.scheme, "s3.mef.gob.pe", ENDPOINT,
                           urlencode({"anoEje": year, "nivelGobierno": level, "sec_ejec": unit}), ""))
    return {"url": canonical, "year": year, "level": level, "unit": unit}


def iter_records(data: bytes, source: dict, observations: list | None = None,
                 *, accept_quality_errors: bool = False):
    """No entrega un resultado exitoso hasta consumir y validar TODO el documento.

    El consumidor debe usar una transaccion para deshacer filas si el final falla.
    Se conserva el mes 0 y los codigos se tratan como texto, sin quitar ceros.
    """
    events = iterparse(BytesIO(data), events=("start", "end"), forbid_dtd=True,
                       forbid_entities=True, forbid_external=True)
    root = None
    depth = 0
    ordinal = 0
    for event, element in events:
        if event == "start":
            depth += 1
            if root is None:
                root = element
                if root.tag != f"{{{NS}}}DataGasto":
                    raise ValueError("Se esperaba DataGasto con el namespace del MEF.")
            elif depth == 2 and element.tag != f"{{{NS}}}Item":
                raise ValueError("Elemento inesperado dentro de DataGasto.")
            continue
        if depth == 2:
            ordinal += 1
            values = {}
            unit_nil = False
            for child in element:
                if not child.tag.startswith(f"{{{NS}}}") or len(child):
                    raise ValueError("Campo con namespace o estructura no admitidos.")
                name = child.tag.split("}", 1)[1]
                if name in values:
                    raise ValueError(f"Campo repetido: {name}")
                values[name] = (child.text or "").strip()
                if name == "Unidad_Medida":
                    unit_nil = child.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "").lower() in ("true", "1")
            if set(values)-set(FIELDS) or set(FIELDS)-set(values)-{"Unidad_Medida"}:
                raise ValueError(f"Contrato XML diferente: faltan {sorted(set(FIELDS)-set(values))}; "
                                 f"sobran {sorted(set(values)-set(FIELDS))}.")
            row = {}
            for name in INTEGER_FIELDS:
                try:
                    row[name] = int(values[name])
                except ValueError as exc:
                    raise ValueError(f"Entero invalido: {name}") from exc
            if not 0 <= row["MesEje"] <= 12:
                raise ValueError("MesEje fuera del dominio admitido.")
            if row["TipoActProy"] not in (2, 3):
                if observations is not None:
                    observations.append({"ordinal": ordinal, "campo": "TipoActProy", "codigo": "TIPO_ACT_PROY_INVALIDO",
                                         "severidad": "Error", "detalle": "Se esperaba 2 (Proyecto) o 3 (Actividad)."})
                if not accept_quality_errors:
                    raise ValueError("TipoActProy fuera del dominio admitido.")
            for name in CODE_FIELDS:
                value = values.get(name)
                if name == "Unidad_Medida" and (unit_nil or not value):
                    row[name] = None
                    code = "UNIDAD_NIL" if unit_nil else "UNIDAD_AUSENTE" if name not in values else "UNIDAD_VACIA"
                    if observations is not None:
                        observations.append({"ordinal": ordinal, "campo": name, "codigo": code,
                                             "severidad": "Advertencia", "detalle": "Unidad de medida no informada en el XML."})
                    continue
                if not value or len(value) > 32:
                    raise ValueError(f"Codigo vacio o demasiado largo: {name}")
                row[name] = value
            for name in MONEY_FIELDS:
                try:
                    value = Decimal(values[name])
                    if (not value.is_finite() or abs(value) >= Decimal('1000000000000000')
                            or value.as_tuple().exponent < -4):
                        raise ValueError(f"Importe fuera de DECIMAL(19,4): {name}")
                    row[name] = value
                except InvalidOperation as exc:
                    raise ValueError(f"Decimal invalido: {name}") from exc
            if (row["AnoEje"], row["IdNivelGobierno"], row["SecEjec"]) != (
                    source["year"], source["level"], source["unit"]):
                raise ValueError("El contenido no coincide con los parametros de la URL.")
            yield row
            element.clear()
            root.clear()
        depth -= 1


def content_hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()
