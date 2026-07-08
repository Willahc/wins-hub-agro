#!/usr/bin/env python3
"""Valida se os artefatos publicos do Cliente Inteligente nao vazam dados internos.

Uso:
  python3 scripts/validar_cliente_inteligente_publico.py

O validador e propositalmente simples e sem dependencias: ele protege a fronteira
mais importante entre One Pages publicas e prospeccao interna.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "ci-lojas" / "cliente-inteligente"

FORBIDDEN_JSON_KEYS = {
    "cnpj",
    "cnpj_status",
    "cnpj_conf",
    "cnpj_confidence",
    "dor",
    "dor_dominante",
    "gancho",
    "lead_tier",
    "pitch",
    "pitch_v3",
    "prioridade",
    "reclamacoes",
    "recs",
    "score",
    "score_comercial",
    "tier",
}

FORBIDDEN_HTML_PATTERNS = {
    "cnpj": re.compile(r"\bcnpj\b", re.I),
    "score interno": re.compile(r"\bscore\b", re.I),
    "tier interno": re.compile(r'<span class="tag gray">\s*(?:A\+|A|B|C|D)\s*</span>'),
    "fallback prospeccao": re.compile(r"CI_FALLBACK_RENDER_PROSPEC"),
}


def fail(msg: str) -> None:
    print(f"ERRO: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"JSON invalido em {path}: {exc}")


def validate_public_json() -> None:
    path = PUBLIC_DIR / "data" / "negocios.json"
    data = load_json(path)
    if not isinstance(data, list):
        fail(f"{path} deveria conter uma lista")
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            fail(f"{path} item {idx} nao e objeto")
        leaked = sorted(FORBIDDEN_JSON_KEYS.intersection(row))
        if leaked:
            fail(f"{path} item {idx} contem campos internos: {', '.join(leaked)}")
    print(f"OK JSON publico: {len(data)} registros")


def validate_embedded_index() -> None:
    path = PUBLIC_DIR / "index.html"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.NEGOCIOS_DATA=(\[.*?\]);</script>", text, flags=re.S)
    if not match:
        fail("window.NEGOCIOS_DATA nao encontrado no index publico")
    data = json.loads(match.group(1))
    for idx, row in enumerate(data):
        leaked = sorted(FORBIDDEN_JSON_KEYS.intersection(row))
        if leaked:
            fail(f"NEGOCIOS_DATA item {idx} contem campos internos: {', '.join(leaked)}")
    print(f"OK dataset embutido: {len(data)} registros")


def validate_public_pages() -> None:
    pages = list((PUBLIC_DIR / "negocios").glob("*/index.html"))
    for path in pages:
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_HTML_PATTERNS.items():
            if pattern.search(text):
                fail(f"{path} contem padrao proibido: {label}")
    print(f"OK paginas publicas: {len(pages)} paginas")


def main() -> None:
    if not PUBLIC_DIR.exists():
        fail(f"diretorio publico nao encontrado: {PUBLIC_DIR}")
    validate_public_json()
    validate_embedded_index()
    validate_public_pages()


if __name__ == "__main__":
    main()
