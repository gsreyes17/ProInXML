"""Comprueba interfaz, navegacion y operaciones con API simulada; no modifica SQL."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
import urllib.request

from playwright.sync_api import expect, sync_playwright
from app.model_schema import registry
from app.xml_reader import FIELDS
from app.metrics import PHASES

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
BASE = "http://127.0.0.1:8766"


def main():
    suffix = ""
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("Compila primero: pnpm --dir frontend build")
    browser_temp = RUNTIME / "browser-tmp"
    browser_temp.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(browser_temp)
    os.environ["TEMP"] = os.environ["TMP"] = str(browser_temp)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8766))
    with (RUNTIME / "preview-maintenance.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8766",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("No se pudo iniciar el servidor de QA.")
                try:
                    with urllib.request.urlopen(BASE, timeout=1):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("El servidor de QA no responde.")
            state = {
                "documents": True,
                "role": "Administrador",
                "running": 0,
                "deletions": [],
                "requests": [],
                "reject": False,
                "metric_reads": 0,
                "urls_received": 0,
            }

            def page_data(records):
                return {
                    "registros": records,
                    "total": len(records),
                    "siguiente_cursor": None,
                }

            evidence = RUNTIME / "qa_metricas_sql.json"
            measured = (
                json.loads(evidence.read_text(encoding="utf-8"))
                if evidence.exists()
                else None
            )
            metric_sample = (
                measured["resumen"]
                if measured
                else {
                    "resumen": {
                        "Intentos": 20,
                        "Completados": 20,
                        "Errores": 0,
                        "Interrumpidos": 0,
                        "EnCurso": 0,
                        "FilasInsertadas": 140,
                        "FilasReutilizadas": 0,
                        "XmlPorMinuto": 60,
                        "FilasPorSegundo": 7,
                    },
                    "fases": [
                        {
                            "Campo": key,
                            "Nombre": label,
                            "Color": color,
                            "Muestras": 20,
                            "PromedioMs": (n + 1) * 10,
                            "P95Ms": (n + 1) * 15,
                            "MaximoMs": (n + 1) * 20,
                        }
                        for n, (key, label, color) in enumerate(PHASES)
                    ],
                    "total_intento": {"PromedioMs": 500, "P95Ms": 600},
                    "comparacion": [
                        {
                            "Concurrencia": 20,
                            "Intentos": 20,
                            "Completados": 20,
                            "Fallos": 0,
                            "FilasInsertadas": 140,
                            "XmlPorMinuto": 60,
                            "FilasPorSegundo": 7,
                            "PromedioMs": 500,
                        }
                    ],
                    "lentos": [],
                    "intentos_sin_medicion": 2,
                    "concurrencia_configurada": 20,
                    "nota": "Datos de prueba simulados",
                }
            )
            metric_attempts = (
                measured["intentos"]
                if measured
                else page_data(
                    [
                        {
                            "Id": 1,
                            "IntentoId": 1,
                            "LoteId": 9002,
                            "Estado": "Completado",
                            "Concurrencia": 20,
                            "HttpStatus": 200,
                            "RegistrosInsertados": 7,
                            "TotalMs": "500.000",
                        }
                    ]
                )
            )
            document = {
                "Id": 42,
                "AnoEje": 2020,
                "SecEjec": 3,
                "EstadoDocumento": "Rechazado",
                "HttpStatus": 200,
                "RegistrosDetalle": 7,
                "Observaciones": 1,
                "Vigente": False,
                "ErrorValidacion": "TipoActProy inesperado",
                "Url": "https://s3.mef.gob.pe/ejemplo",
                "CreadoUtc": "2026-10-23T15:00:00",
            }
            observation = {
                "Id": 1,
                "DocumentoId": 42,
                "OrdinalItem": 1,
                "Campo": "TipoActProy",
                "CodigoObservacion": "TIPO_ACT_PROY_INVALIDO",
                "Severidad": "Error",
                "Detalle": "Se esperaba 2 o 3",
                "FechaUtc": "2026-10-23T15:00:00",
            }

            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1050})
                errors, unexpected = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def fixture(route):
                    request = route.request
                    parsed = urlsplit(request.url)
                    path = parsed.path
                    # Solo los archivos de la interfaz llegan al servidor. Toda API se simula.
                    if (
                        path == "/"
                        or path.startswith(("/ui/", "/assets/"))
                        or path == "/favicon.svg"
                    ):
                        route.continue_()
                        return
                    state["requests"].append(
                        {"path": path, "query": parsed.query, "method": request.method}
                    )
                    if path == "/auth/me":
                        route.fulfill(
                            json={
                                "usuario": {
                                    "Id": 1,
                                    "NombreUsuario": "qa_simulado",
                                    "NombreCompleto": "QA",
                                    "Rol": state["role"],
                                    "Activo": True,
                                },
                                "csrf": "qa-csrf",
                            }
                        )
                    elif path == "/salud":
                        route.fulfill(json={"estado": "ok"})
                    elif path == "/documentos":
                        route.fulfill(
                            json=page_data([document] if state["documents"] else [])
                        )
                    elif path == "/documentos/42":
                        route.fulfill(
                            json={
                                "documento": document,
                                "registro": {
                                    "Id": 1,
                                    "TipoActProy": 4,
                                    "Unidad_Medida": None,
                                }
                                if parse_qs(parsed.query).get("ordinal")
                                else None,
                                "original": {
                                    "texto": "<DataGasto><script>window.qaInjected = true</script><TipoActProy>4</TipoActProy></DataGasto>",
                                    "truncado": False,
                                },
                            }
                        )
                    elif path == "/mantenimiento/vista-previa":
                        body = request.post_data_json
                        all_data = body["alcance"] == "todo"
                        route.fulfill(
                            json={
                                "alcance": body["alcance"],
                                "documento": None if all_data else document,
                                "conteos": {
                                    "documentos": 1,
                                    "registros_xml": 7,
                                    "registros_modelo": 0,
                                    "observaciones": 1,
                                    "trabajos": 1,
                                    "intentos": 1,
                                    "lotes": int(all_data),
                                    "consultas": int(all_data),
                                },
                                "trabajos_en_curso": state["running"],
                                "revision": "a" * 64,
                                "confirmacion": "VACIAR CARGAS"
                                if all_data
                                else "ELIMINAR DOCUMENTO 42",
                                "nota": "Vista previa simulada de eliminacion.",
                                "conserva": ["Usuarios", "Auditoria"],
                            }
                        )
                    elif path == "/mantenimiento/eliminar":
                        assert request.headers.get("x-csrf-token") == "qa-csrf"
                        state["deletions"].append(request.post_data_json)
                        if state["reject"]:
                            route.fulfill(
                                status=409,
                                json={
                                    "detail": "Los datos cambiaron desde la vista previa."
                                },
                            )
                        else:
                            state["documents"] = False
                            route.fulfill(
                                json={
                                    "mensaje": "Cargas eliminadas en simulacion.",
                                    "conteos": {
                                        "documentos": 1,
                                        "registros_xml": 7,
                                        "registros_modelo": 0,
                                    },
                                }
                            )
                    elif path == "/observaciones":
                        route.fulfill(json=page_data([observation]))
                    elif path == "/reportes/ejecucion":
                        route.fulfill(
                            json=page_data(
                                [
                                    {
                                        "Id": 1,
                                        "DocumentoId": 42,
                                        "Estado": "Error",
                                        "HttpStatus": 500,
                                        "Error": "HTTP 500",
                                    }
                                ]
                            )
                        )
                    elif path == "/lotes" and request.method == "POST":
                        state["urls_received"] = len(request.post_data_json["urls"])
                        route.fulfill(
                            status=422,
                            json={
                                "detail": "Solicitud de prueba recibida sin crear lotes."
                            },
                        )
                    elif path == "/lotes":
                        route.fulfill(json=[])
                    elif path == "/metricas/lotes":
                        route.fulfill(
                            json=[{"LoteId": 9002, "Nombre": "Ensayo de metricas"}]
                        )
                    elif path == "/metricas/resumen":
                        state["metric_reads"] += 1
                        payload = json.loads(json.dumps(metric_sample))
                        payload["intentos_sin_medicion"] = 2
                        if parse_qs(parsed.query).get("concurrencia") == ["4"]:
                            payload["resumen"]["Intentos"] = 0
                            payload["fases"] = [
                                dict(
                                    item,
                                    Muestras=0,
                                    PromedioMs=None,
                                    P95Ms=None,
                                    MaximoMs=None,
                                )
                                for item in payload["fases"]
                            ]
                            payload["comparacion"] = payload["lentos"] = []
                        else:
                            payload["resumen"]["Intentos"] = 20 + int(
                                state["metric_reads"] > 1
                            )
                        route.fulfill(json=payload)
                    elif path == "/metricas/intentos":
                        route.fulfill(
                            json=page_data([])
                            if parse_qs(parsed.query).get("concurrencia") == ["4"]
                            else metric_attempts
                        )
                    elif path == "/datos/xml":
                        record = {
                            field: "0.0000"
                            if field
                            in (
                                "PIA",
                                "PIM",
                                "Certificado",
                                "CompAnual",
                                "AtencionCompMensual",
                                "Devengado",
                                "Girado",
                            )
                            else "001"
                            for field in FIELDS
                        }
                        record.update(
                            AnoEje=2020,
                            MesEje=0,
                            SecEjec=3,
                            TipoActProy=2,
                            Unidad_Medida=None,
                        )
                        route.fulfill(
                            json={
                                **page_data([record]),
                                "columnas": list(FIELDS),
                                "identificadores": [1],
                            }
                        )
                    elif path == "/modelo/tablas":
                        route.fulfill(
                            json={"tablas": registry(), "campos_xml": list(FIELDS)}
                        )
                    elif path.startswith("/modelo/tablas/"):
                        definition = next(
                            item
                            for item in registry()
                            if item["tabla"] == path.rsplit("/", 1)[-1]
                        )
                        route.fulfill(
                            json={
                                **page_data(
                                    [
                                        {
                                            "Id": 1,
                                            "Codigo": "E",
                                            "CreadoUtc": "2026-10-23T15:00:00",
                                        }
                                    ]
                                ),
                                **definition,
                            }
                        )
                    elif path == "/usuarios":
                        route.fulfill(
                            json=page_data(
                                [
                                    {
                                        "Id": 1,
                                        "NombreUsuario": "qa_simulado",
                                        "NombreCompleto": "QA de interfaz",
                                        "Rol": "Administrador",
                                        "Activo": True,
                                    }
                                ]
                            )
                        )
                    elif path == "/auditoria/tablas":
                        route.fulfill(
                            json=["integracion.Documento", "integracion.Trabajo"]
                        )
                    elif path in (
                        "/auditoria",
                        "/auditoria/cargas",
                        "/auditoria/accesos",
                    ):
                        route.fulfill(json=page_data([]))
                    else:
                        unexpected.append(path)
                        route.fulfill(
                            status=503,
                            json={
                                "detail": "API sin simulacion; no se permite consultar SQL en este QA."
                            },
                        )

                page.route("**/*", fixture)
                try:
                    page.goto(BASE + "/ui/mantenimiento")
                    expect(
                        page.get_by_role("heading", name="Limpieza del laboratorio")
                    ).to_be_visible()
                    expect(page.locator("#maintenance-description")).to_contain_text(
                        "1 resultados"
                    )
                    metrics = page.evaluate("""() => {
                        const box = selector => {const r=document.querySelector(selector).getBoundingClientRect(); return {top:r.top,bottom:r.bottom,height:r.height}};
                        const css = selector => {const s=getComputedStyle(document.querySelector(selector));return {fuente:s.fontFamily,tamano:s.fontSize,color:s.color,fondo:s.backgroundColor,peso:s.fontWeight}};
                        return {titulo:box('.page-header'),filtros:box('.filter-card'),tabla:box('.explorer-card'),texto:css('td'),encabezado:css('th'),ayuda:css('.subtle'),etiqueta:css('.filter-grid label'),boton:css('#maintenance-filters button[type=submit]')};
                    }""")
                    page.screenshot(
                        path=str(RUNTIME / f"mantenimiento-desktop{suffix}.png"),
                        full_page=True,
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.screenshot(
                        path=str(RUNTIME / f"mantenimiento-datos-movil{suffix}.png"),
                        full_page=True,
                    )
                    page.set_viewport_size({"width": 1440, "height": 1050})
                    page.locator("#maintenance-calidad").select_option("rechazados")
                    page.locator("#maintenance-filters").get_by_role(
                        "button", name="Consultar"
                    ).click()
                    expect(
                        page.locator("#maintenance-filters button[type=submit]")
                    ).to_be_enabled()
                    assert any(
                        "calidad=rechazados" in item["query"]
                        for item in state["requests"]
                    )
                    page.get_by_role(
                        "button", name="Inspeccionar ↗", exact=True
                    ).click()
                    expect(page.locator(".original-preview")).to_contain_text(
                        "<script>window.qaInjected"
                    )
                    assert page.evaluate("window.qaInjected") is None
                    page.get_by_role("button", name="Cerrar detalle").click()
                    page.get_by_role(
                        "button", name="Eliminar documento", exact=True
                    ).click()
                    expect(page.locator("#confirm-delete")).to_be_disabled()
                    expect(page.locator("#delete-requirements")).to_contain_text(
                        "5 caracteres"
                    )
                    page.locator("#delete-reason").fill("test")
                    expect(page.locator("#confirm-delete")).to_be_disabled()
                    page.locator("#delete-confirmation").fill("ELIMINAR DOCUMENTO 42")
                    expect(page.locator("#confirm-delete")).to_be_disabled()
                    page.locator("#delete-reason").fill(
                        "Repetir la prueba del laboratorio"
                    )
                    expect(page.locator("#confirm-delete")).to_be_enabled()
                    expect(page.locator("#delete-requirements")).to_contain_text(
                        "Confirmación completa"
                    )
                    page.screenshot(
                        path=str(RUNTIME / f"mantenimiento-confirmacion{suffix}.png"),
                        full_page=True,
                    )
                    page.get_by_role("button", name="Cancelar", exact=True).click()
                    assert not state["deletions"]

                    state["running"] = 1
                    page.locator("#reset-lab").click()
                    page.locator("#delete-reason").fill("Prueba de trabajo en curso")
                    page.locator("#delete-confirmation").fill("VACIAR CARGAS")
                    expect(page.locator("#confirm-delete")).to_be_disabled()
                    expect(page.get_by_role("dialog")).to_contain_text(
                        "trabajos en curso"
                    )
                    page.get_by_role("button", name="Cancelar", exact=True).click()
                    state["running"] = 0
                    state["reject"] = True
                    page.get_by_role(
                        "button", name="Eliminar documento", exact=True
                    ).click()
                    page.locator("#delete-reason").fill("Vista previa obsoleta")
                    page.locator("#delete-confirmation").fill("ELIMINAR DOCUMENTO 42")
                    page.locator("#confirm-delete").click()
                    expect(page.locator("#maintenance-error")).to_contain_text(
                        "Los datos cambiaron"
                    )
                    expect(page.get_by_role("dialog")).not_to_be_visible()
                    state["reject"] = False
                    page.get_by_role(
                        "button", name="Eliminar documento", exact=True
                    ).click()
                    page.locator("#delete-reason").fill("Eliminar documento de prueba")
                    page.locator("#delete-confirmation").fill("ELIMINAR DOCUMENTO 42")
                    page.locator("#confirm-delete").click()
                    expect(page.locator("#maintenance-message")).to_contain_text(
                        "auditoría"
                    )
                    expect(page.locator("#maintenance-message")).to_contain_text(
                        "7 filas XML"
                    )
                    expect(page.locator("#maintenance-description")).to_contain_text(
                        "0 resultados"
                    )
                    state["documents"] = True
                    page.locator("#reset-lab").click()
                    page.locator("#delete-reason").fill(
                        "Reiniciar laboratorio simulado"
                    )
                    page.locator("#delete-confirmation").fill("VACIAR CARGAS")
                    page.locator("#confirm-delete").click()
                    expect(page.locator("#maintenance-message")).to_be_visible()
                    assert state["deletions"][-1]["alcance"] == "todo"
                    assert state["deletions"][-1]["documento_id"] is None

                    page.get_by_role(
                        "link", name="Observaciones", exact=False
                    ).first.click()
                    page.get_by_role("button", name="Ver dato observado").click()
                    expect(page.locator(".field-highlight")).to_contain_text(
                        "TipoActProy"
                    )
                    expect(page.locator(".field-highlight")).to_contain_text("4")
                    page.get_by_role("dialog").get_by_role(
                        "link", name="Ver observaciones"
                    ).click()
                    expect(page.locator("#observations-documento_id")).to_have_value(
                        "42"
                    )
                    expect(page.get_by_role("dialog")).not_to_be_visible()
                    page.get_by_role(
                        "link", name="Ejecución del servicio", exact=False
                    ).first.click()
                    page.locator("#execution-solo_fallos").select_option("true")
                    page.locator("#execution-filters").get_by_role(
                        "button", name="Consultar"
                    ).click()
                    expect(
                        page.locator("#execution-filters button[type=submit]")
                    ).to_be_enabled()
                    assert any(
                        "solo_fallos=true" in item["query"]
                        for item in state["requests"]
                    )

                    page.get_by_role(
                        "link", name="Mantenimiento", exact=False
                    ).first.click()
                    page.set_viewport_size({"width": 390, "height": 844})
                    expect(page.locator("#reset-lab")).to_be_visible()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.screenshot(
                        path=str(RUNTIME / f"mantenimiento-movil{suffix}.png"),
                        full_page=True,
                    )
                    page.set_viewport_size({"width": 1440, "height": 1050})
                    page.get_by_role(
                        "link", name="Métricas de carga", exact=False
                    ).first.click()
                    expect(page.locator("#metrics-count")).to_have_text("20")
                    expect(page.locator("#metrics-legacy")).to_contain_text(
                        "sin desglose"
                    )
                    expect(page.locator(".phase-row")).to_have_count(7)
                    expect(page.locator("#metrics-count")).to_have_text(
                        "21", timeout=8000
                    )
                    page.screenshot(
                        path=str(RUNTIME / "metricas-desktop.png"), full_page=True
                    )
                    page.get_by_role(
                        "button", name="Ver medición", exact=False
                    ).first.click()
                    expect(page.get_by_role("dialog")).to_contain_text("Concurrencia")
                    page.get_by_role("button", name="Cerrar detalle").click()
                    page.locator("#metrics-concurrency").select_option("4")
                    expect(page.locator("#metrics-empty")).to_be_visible()
                    page.locator("#metrics-concurrency").select_option("20")
                    expect(page.locator("#metrics-count")).to_have_text("21")
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.screenshot(
                        path=str(RUNTIME / "metricas-movil.png"), full_page=True
                    )
                    expect(page.locator(".menu-toggle")).to_be_visible()
                    page.locator(".menu-toggle").click()
                    expect(page.locator(".nav-group")).to_have_count(3)
                    expect(
                        page.get_by_role("navigation", name="Pantallas")
                    ).to_be_visible()
                    page.get_by_role(
                        "link", name="Seguimiento", exact=False
                    ).first.click()
                    expect(page.locator(".menu-toggle")).to_have_attribute(
                        "aria-expanded", "false"
                    )
                    for screen, label, selector in [
                        ("carga", "Carga de datos", "#urls"),
                        ("datos", "Registros XML", ".explorer-card"),
                        ("modelo", "Modelo 3FN", ".model-layout"),
                        ("auditoria", "Auditoría", ".explorer-card"),
                        ("usuarios", "Usuarios", ".explorer-card"),
                    ]:
                        page.set_viewport_size({"width": 1440, "height": 1050})
                        page.get_by_role("link", name=label, exact=False).first.click()
                        expect(page.locator(selector).first).to_be_visible()
                        if screen == "carga":
                            sample_url = "http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3"
                            page.locator("#urls").fill("\n".join([sample_url] * 1001))
                            page.locator("#submit").click()
                            expect(page.locator("#form-message")).to_contain_text(
                                "1 a 1000"
                            )
                            assert state["urls_received"] == 0
                            page.locator("#urls").fill("\n".join([sample_url] * 1000))
                            page.locator("#submit").click()
                            expect(page.locator("#form-message")).to_contain_text(
                                "sin crear lotes"
                            )
                            assert state["urls_received"] == 1000
                            page.locator("#urls").fill("")
                        page.screenshot(
                            path=str(RUNTIME / f"ui-{screen}-desktop{suffix}.png"),
                            full_page=True,
                        )
                        page.set_viewport_size({"width": 390, "height": 844})
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"
                        ), screen
                        page.screenshot(
                            path=str(RUNTIME / f"ui-{screen}-movil{suffix}.png"),
                            full_page=True,
                        )
                    page.set_viewport_size({"width": 1440, "height": 1050})
                    page.get_by_role(
                        "link", name="Mantenimiento", exact=False
                    ).first.click()
                    state["role"] = "Operador"
                    page.reload()
                    expect(page).to_have_url(BASE + "/ui/seguimiento")
                    expect(
                        page.get_by_role("link", name="Mantenimiento", exact=False)
                    ).to_have_count(0)
                    page.evaluate("window.dispatchEvent(new Event('session-expired'))")
                    expect(page.locator("#login-form")).to_be_visible()
                    page.screenshot(
                        path=str(RUNTIME / "ui-login-desktop.png"), full_page=True
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.screenshot(
                        path=str(RUNTIME / "ui-login-movil.png"), full_page=True
                    )
                    assert not errors, errors
                    assert not unexpected, unexpected
                    result = {
                        "resultado": "OK",
                        "api": "simulada; sin SQL",
                        "comprobaciones": [
                            "filtros de calidad y fallos",
                            "original escapado",
                            "confirmacion y motivo",
                            "cancelar no elimina",
                            "trabajos en curso",
                            "vista previa obsoleta",
                            "eliminacion individual y global simuladas",
                            "valor observado resaltado",
                            "movil sin desborde",
                            "navegacion por rol",
                            "carga, XML, modelo, auditoria y usuarios en escritorio/movil",
                            "metricas, fases, filtros y actualizacion automatica",
                            "entrada manual 1000 y rechazo 1001",
                            "navegacion agrupada, menu movil y pantalla de acceso",
                        ],
                        "errores_js": errors,
                        "medidas_ui": metrics,
                    }
                    (RUNTIME / "qa_interfaz.json").write_text(
                        json.dumps(result, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                finally:
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
