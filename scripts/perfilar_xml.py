"""Perfila carpetas/listas XML o documentos conservados en SQL Server, sin descargarlos."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import gzip
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from defusedxml.ElementTree import fromstring
from app.xml_reader import FIELDS, INTEGER_FIELDS, MONEY_FIELDS, NS


def profile(documents):
    counts = {field: Counter({"presentes": 0, "vacios": 0, "ausentes": 0, "nil": 0, "formato_raro": 0}) for field in FIELDS}
    errors, files, items, generic_units = [], 0, 0, Counter()
    for name, payload in documents:
        files += 1
        try:
            if payload.startswith(b"\x1f\x8b"):
                payload = gzip.decompress(payload)
            root = fromstring(payload, forbid_dtd=True, forbid_entities=True, forbid_external=True)
            if root.tag != f"{{{NS}}}DataGasto":
                raise ValueError("Raiz o namespace fuera del contrato MEF.")
            for item in root.findall(f"{{{NS}}}Item"):
                items += 1
                values = {c.tag.rsplit("}", 1)[-1]: c for c in item}
                for field in FIELDS:
                    stat = counts[field]
                    node = values.get(field)
                    if node is None:
                        stat["ausentes"] += 1
                        continue
                    stat["presentes"] += 1
                    text = (node.text or "").strip()
                    if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "").lower() in ("true", "1"):
                        stat["nil"] += 1
                    if not text:
                        stat["vacios"] += 1
                        continue
                    try:
                        if field in INTEGER_FIELDS:
                            val = int(text)
                            if field == "MesEje" and not 0 <= val <= 12 or field == "TipoActProy" and val not in (2, 3):
                                raise ValueError()
                        elif field in MONEY_FIELDS:
                            value = Decimal(text)
                            if not value.is_finite() or abs(value) >= Decimal("1000000000000000") or value.as_tuple().exponent < -4:
                                raise ValueError()
                        elif len(text)>32:
                            raise ValueError()
                    except (ValueError, InvalidOperation):
                        stat["formato_raro"] += 1
                unit = values.get("Unidad_Medida")
                if unit is None or not (unit.text or "").strip():
                    meta = values.get("IdMeta"); final = values.get("IdFinalidad")
                    generic_units[f"IdMeta={meta.text if meta is not None else None};IdFinalidad={final.text if final is not None else None}"] += 1
        except Exception as exc:
            errors.append({"documento": str(name), "error": str(exc)})
    return {"documentos": files, "items": items, "campos": counts,
            "unidad_ausente_por_meta_finalidad": dict(generic_units), "documentos_no_interpretables": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rutas", nargs="*")
    parser.add_argument("--lista", type=Path, help="Archivo UTF-8 con una ruta XML local por linea")
    parser.add_argument("--base-datos", action="store_true")
    parser.add_argument("--salida", type=Path, default=Path(".runtime/perfil_xml.json"))
    args = parser.parse_args()
    paths = [Path(path) for path in args.rutas]
    if args.lista:
        paths += [args.lista.parent/line.strip() for line in args.lista.read_text(encoding="utf-8").splitlines() if line.strip()]
    files = [child for path in paths for child in (sorted(path.glob("*.xml")) if path.is_dir() else [path])]
    def documents():
        for path in files:
            yield str(path), path.read_bytes()
        if args.base_datos:
            from app.db import transaction
            with transaction(actor="perfilado-local") as con:
                for row in con.execute("SELECT Id,Respuesta FROM integracion.Documento ORDER BY Id"):
                    yield f"Documento {row[0]}", bytes(row[1])
    result = profile(documents())
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Perfilados {result['documentos']} documentos, {result['items']} Items. Informe: {args.salida}")


if __name__ == "__main__":
    main()
