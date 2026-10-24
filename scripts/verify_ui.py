"""QA del frontend Vue compilado con Edge: lecturas reales y cargas simuladas.

No descarga XML ni crea lotes reales. Las credenciales se leen por teclado o stdin.
"""
import argparse
from getpass import getpass
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

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
BASE = "http://127.0.0.1:8765"
URL = ("http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/"
       "ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usuario", default="administrador")
    parser.add_argument("--stdin", action="store_true", help="Leer clave desde stdin sin mostrarla")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n") if args.stdin else getpass("Contrasena de administrador para QA: ")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("Compila primero: pnpm --dir frontend build")
    RUNTIME.mkdir(exist_ok=True)
    browser_temp = RUNTIME / 'browser-tmp'
    browser_temp.mkdir(exist_ok=True)
    tempfile.tempdir = str(browser_temp)
    os.environ['TEMP'] = str(browser_temp)
    os.environ['TMP'] = str(browser_temp)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8765))
    with (RUNTIME / "preview.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("No se pudo iniciar preview; revisar .runtime/preview.log")
                try:
                    with urllib.request.urlopen(BASE, timeout=1):
                        break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError("El servidor no respondio.")
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(BASE + "/ui/datos")
                    expect(page.locator("#login-form")).to_be_visible()
                    page.screenshot(path=str(RUNTIME / "vue-login-desktop.png"), full_page=True)
                    page.locator("#login-user").fill(args.usuario)
                    page.locator("#login-password").fill(password)
                    page.locator("#login-submit").click()
                    expect(page.locator("#session-name")).to_contain_text("Administrador")
                    expect(page.locator("#connection-text")).to_have_text("Base de datos conectada")
                    print("Login y API reales: OK", flush=True)
                    page.get_by_role("link", name="Carga de datos").click()
                    expect(page.locator("#submit")).to_be_disabled()
                    page.screenshot(path=str(RUNTIME / "vue-carga-desktop.png"), full_page=True)

                    scenario = {"created": False, "stage": "Pendiente", "requests": 0, "received": None}

                    def fixtures(route):
                        parsed = urlsplit(route.request.url)
                        path = parsed.path
                        if path == "/lotes" and route.request.method == "POST":
                            body = route.request.post_data_json
                            if any("localhost" in url for url in body["urls"]):
                                route.fulfill(status=422, json={"detail": {"mensaje": "Corrige los enlaces indicados.", "errores": [{"linea": 1, "detalle": "Endpoint no admitido."}]}})
                            else:
                                scenario["created"] = True
                                scenario["received"] = body["urls"]
                                route.fulfill(status=201, json={"lote_id": 9001, "trabajos": 1, "nuevas": 1, "ya_cargadas": 0, "duplicados_omitidos": 0})
                        elif path == "/lotes" and route.request.method == "GET":
                            route.fulfill(json=[{"Id": 9001, "Nombre": "QA Vue: un XML", "CreadoUtc": "2026-10-23T15:00:00", "Total": 1, "Completados": int(scenario["stage"] == "Completado"), "Fallidos": int(scenario["stage"] == "Fallido")}] if scenario["created"] else [])
                        elif path == "/lotes/9001":
                            route.fulfill(json={"lote": {"Id": 9001, "CreadoUtc": "2026-10-23T15:00:00"}, "resumen": [{"Estado": scenario["stage"], "Cantidad": 1}], "registros": 7 if scenario["stage"] == "Completado" else 0, "eta_segundos": None})
                        elif path == "/lotes/9001/trabajos":
                            scenario["requests"] += 1
                            filters = parse_qs(parsed.query)
                            if filters.get("estado") and filters["estado"] != [scenario["stage"]]:
                                route.fulfill(json=[])
                                return
                            failed = scenario["stage"] in ("Reintento", "Fallido")
                            state = "Pendiente" if scenario["stage"] == "Reintento" else scenario["stage"]
                            route.fulfill(json=[{"Id": 90001, "LoteId": 9001, "Estado": state, "Intentos": 2 if state == "Completado" else 1 if failed else 0,
                                "MaxIntentos": 4, "Url": URL, "AnoEje": 2020, "NivelGobierno": "E", "SecEjec": 3, "CantidadRegistros": 7 if state == "Completado" else None,
                                "HttpStatus": 500 if failed else 200 if state == "Completado" else None, "UltimoError": '<img src=x onerror="alert(1)"> HTTP 500 simulado' if failed else None,
                                "ProximoIntentoUtc": "2026-10-23T15:01:00"}])
                        elif path == "/trabajos/90001/reintentar" and route.request.method == "POST":
                            scenario["stage"] = "Pendiente"
                            route.fulfill(json={"mensaje": "Reintento encolado."})
                        elif path == "/trabajos/90001/forzar-revision" and route.request.method == "POST":
                            scenario["stage"] = "Fallido"
                            route.fulfill(json={"mensaje": "Revision encolada."})
                        elif path == "/trabajos/90001/gastos":
                            route.fulfill(json=[{"Id": 1, "AnoEje": 2020, "MesEje": 0, "SecEjec": 3, "IdProyecto": "2999999", "IdMeta": "00001", "PIM": "110191.3700", "Devengado": "110191.3700"}])
                        else:
                            route.continue_()

                    page.route("**/*", fixtures)
                    page.locator("#urls").fill("http://localhost/private")
                    page.locator("#submit").click()
                    expect(page.locator("#form-message")).to_contain_text("Enlace 1")
                    page.locator("#example").click()
                    expect(page.locator("#url-count")).to_have_text("1 enlace")
                    page.locator("#submit").click()
                    expect(page.locator("#jobs-body tr")).to_have_count(1)
                    expect(page.locator("#stat-total")).to_have_text("1")
                    scenario["stage"] = "Reintento"
                    expect(page.locator("#jobs-body")).to_contain_text("HTTP 500", timeout=7000)
                    page.locator(".error-details summary").click()
                    expect(page.locator(".error-details")).to_contain_text("<img src=x")
                    assert page.locator("img").count() == 0
                    scenario["stage"] = "Completado"
                    expect(page.locator("#stat-completed")).to_have_text("1", timeout=7000)
                    expect(page.locator("#jobs-body")).to_contain_text("HTTP 200")
                    page.get_by_role("button", name="Ver datos").click()
                    expect(page.locator("dialog[open]")).to_contain_text("110,191.37")
                    page.keyboard.press("Escape")
                    page.get_by_role("button", name="Forzar revisión").click()
                    expect(page.get_by_role("button", name="Reintentar")).to_be_visible()
                    page.get_by_role("button", name="Reintentar").click()
                    expect(page.locator("#jobs-body .status-badge")).to_have_text("Pendiente")
                    scenario["stage"] = "Completado"
                    expect(page.locator("#stat-records")).to_have_text("7", timeout=7000)
                    page.locator("#job-state").select_option("CompletadoSinDatos")
                    expect(page.locator("#empty-state")).to_contain_text("No hay enlaces")
                    page.locator("#job-state").select_option("")
                    expect(page.locator("#jobs-body tr")).to_have_count(1)
                    page.screenshot(path=str(RUNTIME / "vue-seguimiento-simulado.png"), full_page=True)
                    assert scenario["received"] == [URL]
                    print("Un XML simulado: HTTP 500, recuperacion automatica y acciones: OK", flush=True)

                    page.evaluate("window.__qaVueNavigation = 42")
                    page.get_by_role("link", name="Registros XML", exact=False).first.click()
                    expect(page.locator(".explorer-card th")).to_have_count(39)
                    assert page.evaluate("window.__qaVueNavigation") == 42, "La navegacion recargo el documento"
                    calls = scenario["requests"]
                    page.wait_for_timeout(3300)
                    assert scenario["requests"] == calls, "El seguimiento siguio consultando fuera de su pantalla"
                    page.unroute("**/*", fixtures)

                    page.locator(".explorer-card .row-action").first.click()
                    expect(page.locator("dialog[open] .record-fields")).to_have_count(2)
                    expect(page.locator("dialog[open] .record-fields").nth(1).locator("dt")).to_have_count(39)
                    page.get_by_role("link", name="Ver en modelo").click()
                    expect(page.get_by_role("heading", name="Gasto normalizado", exact=True)).to_be_visible()
                    page.locator('[aria-label^="Meta #"]').first.click()
                    expect(page.get_by_role("heading", name="Metas por contexto", exact=True)).to_be_visible()
                    page.get_by_role("link", name="Registros XML", exact=False).first.click()
                    page.locator("#data-mode").select_option("false")
                    expect(page.locator(".explorer-card th")).to_have_count(43)

                    page.get_by_role("link", name="Auditoría", exact=False).first.click()
                    expect(page.locator("#audit-description")).to_contain_text("resultados")
                    page.locator("#audit-actor").fill("QA_ACTOR_INEXISTENTE_98173")
                    page.locator("#audit-filters").get_by_role("button", name="Consultar").click()
                    expect(page.locator(".explorer-empty")).to_contain_text("No hay resultados")
                    page.get_by_role("button", name="Limpiar", exact=True).click()
                    expect(page.locator(".explorer-card tbody tr")).not_to_have_count(0)
                    page.get_by_role("button", name="Ver cambios").first.click()
                    expect(page.locator(".audit-comparison th")).to_have_count(3)
                    page.keyboard.press("Escape")
                    page.get_by_role("button", name="Cargas por documento", exact=True).click()
                    expect(page.get_by_role("heading", name="Cargas por documento")).to_be_visible()
                    page.get_by_role("button", name="Eventos de acceso", exact=True).click()
                    expect(page.locator(".explorer-card tbody tr")).not_to_have_count(0)
                    print("Consultas XML, modelo, filtros, auditoria y navegacion SPA: OK", flush=True)

                    for name, selector in [("auditoria", "#audit-description"), ("datos", "#data-description"), ("modelo", "#model-description"), ("ejecucion", "#execution-description"), ("observaciones", "#observations-description"), ("usuarios", "#users-description")]:
                        page.goto(BASE + "/ui/" + name)
                        expect(page.locator(selector)).to_contain_text("resultados")
                        page.screenshot(path=str(RUNTIME / f"vue-{name}-desktop.png"), full_page=True)
                        page.set_viewport_size({"width": 390, "height": 844})
                        page.screenshot(path=str(RUNTIME / f"vue-{name}-mobile.png"), full_page=True)
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Desbordamiento en {name}"
                        page.set_viewport_size({"width": 1440, "height": 1000})
                    page.locator("#logout").click()
                    expect(page.locator("#login-form")).to_be_visible()
                    assert not errors, errors
                    result = {"resultado": "OK", "frontend": "Vue 3 / Vite / TypeScript / Pinia / Vue Router", "xml_simulados": 1, "casos": ["login/logout real", "polling HTTP 500 a 200", "reintento y revision simulados", "navegacion SPA", "cancelacion de polling", "39 campos y trazabilidad", "FK", "auditoria", "reportes", "usuarios", "movil 390px"]}
                    (RUNTIME / "qa_vue.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                except BaseException:
                    page.screenshot(path=str(RUNTIME / "vue-qa-fallo.png"), full_page=True)
                    print("Errores de pagina:", errors, flush=True)
                    raise
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
