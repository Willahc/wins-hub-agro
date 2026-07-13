"""Regressão do ROI Pasto Limpo sem inicializar a aplicação ou acessar o banco.

Os testes exercitam o corpo real da rota com dependências falsas, renderizam os
templates Jinja diretamente e executam a lógica JavaScript existente via Node.
"""

import ast
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from types import SimpleNamespace
import subprocess
import unittest

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "app" / "frontend"
ROUTER = ROOT / "app" / "routers" / "simulador.py"


class _HTMLInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if attributes.get("id"):
            self.ids.append(attributes["id"])

    def has_tag_with_class(self, tag, class_name):
        return any(
            current_tag == tag and class_name in attributes.get("class", "").split()
            for current_tag, attributes in self.tags
        )


class _FakeTemplates:
    def TemplateResponse(self, template_name, context):
        return SimpleNamespace(template_name=template_name, context=context, headers={})


def _route_function(user):
    """Compila apenas o corpo real de pasto_limpo_page, sem importar main/db."""
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"), filename=str(ROUTER))
    route = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pasto_limpo_page"
    )
    route.decorator_list = []
    isolated_module = ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[]))
    templates = _FakeTemplates()
    namespace = {
        "APP_VERSION": "test-version",
        "HTMLResponse": object,
        "Request": object,
        "get_current_user": lambda request: user,
        "templates": templates,
    }
    exec(compile(isolated_module, str(ROUTER), "exec"), namespace)
    return namespace["pasto_limpo_page"]


class TestPastoLimpo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Environment(
            loader=FileSystemLoader(FRONTEND),
            autoescape=select_autoescape(("html", "xml")),
        )
        cls.auth_html = cls.env.get_template("pasto_limpo.html").render(
            request=None,
            user={"name": "Mari", "sub": "mari@example.test"},
            active="pasto_limpo",
            app_version="test-version",
        )
        cls.public_html = cls.env.get_template("pasto_limpo_public.html").render(request=None)

    def test_authenticated_route_uses_shell_template_and_no_store(self):
        user = {"name": "Mari", "sub": "mari@example.test"}
        response = _route_function(user)(object())

        self.assertEqual(response.template_name, "pasto_limpo.html")
        self.assertIs(response.context["user"], user)
        self.assertEqual(response.context["active"], "pasto_limpo")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_public_route_preserves_existing_url_and_public_template(self):
        request = object()
        response = _route_function(None)(request)
        source = ROUTER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        route = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "pasto_limpo_page"
        )
        decorators = "\n".join(ast.get_source_segment(source, item) or "" for item in route.decorator_list)

        self.assertIn('router.get("/pasto-limpo"', decorators)
        self.assertEqual(response.template_name, "pasto_limpo_public.html")
        self.assertIs(response.context["request"], request)
        self.assertEqual(set(response.context), {"request"})
        self.assertNotIn("Cache-Control", response.headers)

    def test_authenticated_template_has_shell_active_menu_and_same_tab_link(self):
        template_source = (FRONTEND / "pasto_limpo.html").read_text(encoding="utf-8")
        inspector = _HTMLInspector()
        inspector.feed(self.auth_html)
        links = [attrs for tag, attrs in inspector.tags if tag == "a" and attrs.get("href") == "/pasto-limpo"]

        self.assertIn('{% extends "base.html" %}', template_source)
        self.assertTrue(inspector.has_tag_with_class("nav", "sidebar"))
        self.assertTrue(inspector.has_tag_with_class("header", "topbar"))
        self.assertEqual(len(links), 1)
        self.assertIn("active", links[0].get("class", "").split())
        self.assertNotIn("target", links[0])
        self.assertIn("Mari", self.auth_html)

    def test_public_template_has_simulator_without_private_shell(self):
        inspector = _HTMLInspector()
        inspector.feed(self.public_html)

        self.assertFalse(inspector.has_tag_with_class("nav", "sidebar"))
        self.assertFalse(inspector.has_tag_with_class("header", "topbar"))
        self.assertTrue(inspector.has_tag_with_class("section", "pasto-limpo-page"))
        self.assertIn("Dados do pasto", self.public_html)
        self.assertIn("Retorno estimado", self.public_html)

    def test_shared_fields_results_scripts_and_unique_ids(self):
        fields = (
            "Área de pasto a tratar (ha)",
            "Infestação de daninha",
            "Lotação potencial do pasto limpo (UA/ha)",
            "Custo do herbicida + aplicação (R$/ha)",
            "Preço da arroba (@) hoje",
            "Eficácia do controle",
            "Produção por UA por ano (@/UA/ano)",
        )
        for page_name, html in (("autenticada", self.auth_html), ("pública", self.public_html)):
            with self.subTest(page=page_name):
                for field in fields:
                    self.assertIn(field, html)
                self.assertIn("Retorno estimado", html)
                self.assertEqual(html.count("function pastoLimpo()"), 1)
                self.assertEqual(html.count("/static/vendor/alpine.min.js"), 1)
                inspector = _HTMLInspector()
                inspector.feed(html)
                duplicated_ids = [item for item, count in Counter(inspector.ids).items() if count > 1]
                self.assertEqual(duplicated_ids, [])

    def test_central_formula_fragments_remain_in_shared_javascript(self):
        script = (FRONTEND / "_pasto_limpo_script.html").read_text(encoding="utf-8")
        expected_fragments = (
            "get lotacaoAtual() { return this.lotacaoPot * (1 - this.infest/100); }",
            "get lotacaoRecup() { return this.lotacaoAtual + (this.lotacaoPot - this.lotacaoAtual) * this.eficacia/100; }",
            "get uaAdicionais() { return Math.max(0, (this.lotacaoRecup - this.lotacaoAtual) * (this.area||0)); }",
            "get arrobasAno() { return this.uaAdicionais * this.arrPorUA; }",
            "get receitaAno() { return this.arrobasAno * (this.arroba||0); }",
            "get custoTotal() { return (this.area||0) * (this.custoHa||0); }",
            "get roi() { return this.custoTotal > 0 ? this.receitaAno / this.custoTotal : 0; }",
        )
        for fragment in expected_fragments:
            self.assertIn(fragment, script)

    @unittest.skipUnless(shutil.which("node"), "Node não disponível para executar o JavaScript compartilhado")
    def test_default_calculation_regression_uses_existing_javascript(self):
        script = (FRONTEND / "_pasto_limpo_script.html").read_text(encoding="utf-8")
        javascript = script[script.index(">") + 1:script.rindex("<")]
        runner = javascript + """
const simulation = pastoLimpo();
console.log(JSON.stringify({
  lotacaoAtual: simulation.lotacaoAtual,
  lotacaoRecup: simulation.lotacaoRecup,
  uaAdicionais: simulation.uaAdicionais,
  arrobasAno: simulation.arrobasAno,
  receitaAno: simulation.receitaAno,
  custoTotal: simulation.custoTotal,
  roi: simulation.roi,
  payback: simulation.payback
}));
"""
        completed = subprocess.run(
            ["node", "-e", runner],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(completed.stdout)

        self.assertAlmostEqual(values["lotacaoAtual"], 1.26)
        self.assertAlmostEqual(values["lotacaoRecup"], 1.692)
        self.assertAlmostEqual(values["uaAdicionais"], 432)
        self.assertAlmostEqual(values["arrobasAno"], 3024)
        self.assertAlmostEqual(values["receitaAno"], 967680)
        self.assertAlmostEqual(values["custoTotal"], 250000)
        self.assertAlmostEqual(values["roi"], 3.87072)
        self.assertEqual(values["payback"], 4)

    def test_css_is_scoped_and_responsive(self):
        css = (FRONTEND / "_pasto_limpo_styles.html").read_text(encoding="utf-8")
        dangerous_global_selector = re.compile(
            r"^\s*(?:body|header|nav|main|button|input|table|\.container|:root|\*)\s*(?:,|\{)",
            re.MULTILINE,
        )

        self.assertIn(".pasto-limpo-page", css)
        self.assertIsNone(dangerous_global_selector.search(css))
        self.assertRegex(css, r"@media\s*\(max-width:\s*520px\)")
        self.assertRegex(
            css,
            r"\.pasto-limpo-page\s+\.pasto-limpo-grid\s*\{\s*grid-template-columns:1fr;\s*\}",
        )


if __name__ == "__main__":
    unittest.main()
