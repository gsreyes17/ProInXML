from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.main import app
from app.api.security import current_user

URL = (
    "http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/"
    "ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3"
)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.user = {"Id": 1, "NombreUsuario": "test", "Rol": "Administrador"}

        async def user_override():
            return self.user

        app.dependency_overrides[current_user] = user_override
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_actual_workbook_imports_5655_sources_without_footer(self):
        workbook = Path(__file__).resolve().parents[1] / "data_models" / "URLs.xlsx"
        with patch("app.api.main.create_batch", return_value={"lote_id": 1}) as create:
            response = self.client.post(
                "/lotes/excel", files={"file": ("URLs.xlsx", workbook.read_bytes())}
            )
        self.assertEqual(response.status_code, 201, response.text)
        sources = create.call_args.args[1]
        self.assertEqual(len(sources), 5655)
        self.assertEqual(sum(s["year"] == 2020 for s in sources), 2830)
        self.assertEqual(sum(s["year"] == 2021 for s in sources), 2825)

    def test_excel_does_not_require_year_or_expected_count(self):
        book = Workbook()
        book.active.title = "XML"
        book.active.append(["URL", "Anio", "Cantidad Registros"])
        book.active.append([URL, 2021, "x"])
        data = BytesIO()
        book.save(data)
        with patch("app.api.main.create_batch", return_value={"lote_id": 1}) as create:
            response = self.client.post(
                "/lotes/excel", files={"file": ("bad.xlsx", data.getvalue())}
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(create.call_args.args[1][0]["year"], 2020)

    def test_rejects_unapproved_url(self):
        with patch("app.api.main.create_batch") as create:
            response = self.client.post(
                "/lotes/url", json={"url": "http://localhost/private"}
            )
        self.assertEqual(response.status_code, 422)
        create.assert_not_called()

    def test_malformed_excel_returns_validation_error_without_creating_batch(self):
        book = Workbook()
        book.active.append(["URL"])
        book.active.append([URL])
        original = BytesIO()
        book.save(original)
        broken = BytesIO()
        with (
            ZipFile(BytesIO(original.getvalue())) as source,
            ZipFile(broken, "w") as target,
        ):
            for info in source.infolist():
                target.writestr(
                    info,
                    b"<worksheet"
                    if info.filename == "xl/worksheets/sheet1.xml"
                    else source.read(info.filename),
                )
        with patch("app.api.main.create_batch") as create:
            response = self.client.post(
                "/lotes/excel", files={"file": ("malformado.xlsx", broken.getvalue())}
            )
        self.assertEqual(response.status_code, 422, response.text)
        create.assert_not_called()

    def test_interface_serves_vue_entry_without_caching_html(self):
        with TemporaryDirectory(dir=self.temp_root) as folder:
            Path(folder, "index.html").write_text(
                '<div id="app"></div>', encoding="utf-8"
            )
            with patch("app.api.ui.DIST", Path(folder)):
                response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="app"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_additional_visual_pages_are_served(self):
        with TemporaryDirectory(dir=self.temp_root) as folder:
            Path(folder, "index.html").write_text(
                '<div id="app"></div>', encoding="utf-8"
            )
            with patch("app.api.ui.DIST", Path(folder)):
                for path in (
                    "/ui/login",
                    "/ui/seguimiento",
                    "/ui/auditoria",
                    "/ui/datos",
                    "/ui/modelo",
                    "/ui/usuarios",
                    "/ui/observaciones",
                    "/ui/ejecucion",
                    "/ui/mantenimiento",
                    "/ui/metricas",
                ):
                    self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/ui/inexistente").status_code, 404)

    def test_missing_frontend_build_has_clear_error(self):
        with (
            TemporaryDirectory(dir=self.temp_root) as folder,
            patch("app.api.ui.DIST", Path(folder)),
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("pnpm", response.json()["detail"])

    def test_model_registry_and_identifier_validation(self):
        definition = self.client.get("/api/modelo/estructura").json()
        self.assertEqual(len(definition["campos_xml"]), 39)
        self.assertEqual(len(definition["tablas"]), 31)
        self.assertEqual(self.client.get("/api/modelo/sys.tables").status_code, 404)
        self.assertEqual(
            self.client.get("/api/auditoria?desde=2026-10-22T00:00:00").status_code, 422
        )

    def test_multiple_urls_are_created_in_one_batch(self):
        urls = [URL, URL.replace("sec_ejec=3", "sec_ejec=5")]
        with patch(
            "app.api.main.create_batch", return_value={"lote_id": 21, "trabajos": 2}
        ) as create:
            response = self.client.post("/lotes/urls", json={"urls": urls})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(create.call_args.args[1]), 2)
        self.assertEqual(response.json()["trabajos"], 2)

    def test_invalid_url_rejects_entire_list_before_saving(self):
        with patch("app.api.main.create_batch") as create:
            response = self.client.post(
                "/lotes/urls", json={"urls": [URL, "http://localhost/private"]}
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errores"][0]["linea"], 2)
        create.assert_not_called()

    def test_empty_or_excessive_url_lists_are_rejected(self):
        with patch("app.api.main.create_batch") as create:
            for urls in ([], [URL] * 1001):
                response = self.client.post("/lotes/urls", json={"urls": urls})
                self.assertEqual(response.status_code, 422)
        create.assert_not_called()

    def test_manual_input_accepts_1000_urls(self):
        with patch("app.api.main.create_batch", return_value={"lote_id": 1}) as create:
            response = self.client.post("/lotes", json={"urls": [URL] * 1000})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(create.call_args.args[1]), 1000)

    def test_expenses_returns_exact_decimal_as_string(self):
        from contextlib import contextmanager

        @contextmanager
        def connection():
            from unittest.mock import MagicMock

            yield MagicMock()

        with (
            patch("app.api.main.transaction", connection),
            patch(
                "app.api.main.rows", return_value=[{"PIA": Decimal("12345678901234.1200")}]
            ),
        ):
            response = self.client.get("/gastos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["PIA"], "12345678901234.1200")

    def test_consulta_cannot_create_retry_force_or_read_audit(self):
        self.user["Rol"] = "Consulta"
        for path, body in [
            ("/lotes/urls", {"urls": [URL]}),
            ("/trabajos/1/reintentar", None),
            ("/trabajos/1/forzar-revision", None),
            ("/usuarios", {}),
        ]:
            self.assertEqual(self.client.post(path, json=body).status_code, 403, path)
        self.assertEqual(self.client.get("/auditoria").status_code, 403)

    def test_operator_cannot_force_review_or_manage_users(self):
        self.user["Rol"] = "Operador"
        self.assertEqual(
            self.client.post("/trabajos/1/forzar-revision").status_code, 403
        )
        self.assertEqual(self.client.get("/usuarios").status_code, 403)

    def test_only_administrator_can_preview_or_delete_data(self):
        for role in ("Consulta", "Operador"):
            self.user["Rol"] = role
            with patch("app.api.maintenance.transaction") as transact:
                for path in (
                    "/mantenimiento/vista-previa",
                    "/mantenimiento/eliminar",
                    "/mantenimiento/normalizar",
                ):
                    self.assertEqual(
                        self.client.post(path, json={"alcance": "todo"}).status_code,
                        403,
                    )
                transact.assert_not_called()

    def test_maintenance_cookie_requires_csrf_before_opening_sql_connection(self):
        import hashlib
        import secrets
        import time
        from app.api.security import COOKIE, sessions

        app.dependency_overrides.clear()
        token = secrets.token_urlsafe(32)
        key = hashlib.sha256(token.encode()).hexdigest()
        sessions[key] = {
            "user_id": 1,
            "expires": time.monotonic() + 60,
            "csrf": "expected-csrf",
        }
        try:
            self.client.cookies.set(COOKIE, token)
            with patch("app.api.security.transaction") as transact:
                for path in (
                    "/mantenimiento/vista-previa",
                    "/mantenimiento/eliminar",
                    "/mantenimiento/normalizar",
                ):
                    self.assertEqual(
                        self.client.post(path, json={"alcance": "todo"}).status_code,
                        403,
                    )
                transact.assert_not_called()
        finally:
            sessions.pop(key, None)

    def test_deletion_requires_exact_scope_confirmation_and_reason_before_sql(self):
        cases = [
            {"alcance": "documento"},
            {"alcance": "todo", "documento_id": 1},
            {
                "alcance": "todo",
                "revision": "0" * 64,
                "confirmacion": "eliminar",
                "motivo": "Prueba laboratorio",
            },
            {
                "alcance": "todo",
                "revision": "0" * 64,
                "confirmacion": "VACIAR CARGAS",
                "motivo": "     ",
            },
        ]
        with patch("app.api.maintenance.transaction") as transact:
            for body in cases:
                response = self.client.post("/mantenimiento/eliminar", json=body)
                self.assertEqual(response.status_code, 422, response.text)
            transact.assert_not_called()

    def test_anonymous_cannot_read_data(self):
        app.dependency_overrides.clear()
        for path in (
            "/datos/xml",
            "/metricas/resumen",
            "/metricas/intentos",
            "/metricas/lotes",
        ):
            self.assertEqual(self.client.get(path).status_code, 401)


if __name__ == "__main__":
    unittest.main()
