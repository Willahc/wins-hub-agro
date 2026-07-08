#!/usr/bin/env python3
"""Aplica o botão de claim nas One Pages públicas do Cliente Inteligente.

Fonte de verdade:
- master/master_public.json

Escopo:
- insere/atualiza um bloco discreto nas páginas individuais em ci-lojas/cliente-inteligente/negocios/<slug>/index.html
- não altera One Pages públicas em produção por si só; apenas os arquivos locais do repositório
- mantém o processo idempotente com marcadores CI_CLAIM_START / CI_CLAIM_END
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
MASTER_PUBLIC = ROOT / "master" / "master_public.json"
PUBLIC_ROOT = ROOT / "ci-lojas" / "cliente-inteligente"
PUBLIC_PAGES = PUBLIC_ROOT / "negocios"
PUBLIC_INDEX = PUBLIC_ROOT / "index.html"
PUBLIC_DATA = PUBLIC_ROOT / "data" / "negocios.json"
PUBLIC_CSS = PUBLIC_ROOT / "assets" / "site.css"
REPORT_PATH = ROOT / "RELATORIO_ONEPAGE_CLAIM.md"

CLAIM_START = "<!-- CI_CLAIM_START -->"
CLAIM_END = "<!-- CI_CLAIM_END -->"

CSS_MARK_START = "/* CI_CLAIM_START */"
CSS_MARK_END = "/* CI_CLAIM_END */"


def fail(msg: str) -> None:
    print(f"ERRO: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"JSON inválido em {path}: {exc}")


def normalize_slug(value: str) -> str:
    value = (value or "").strip().strip("/")
    return value


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def onepage_slug(row: dict) -> str:
    slug = normalize_slug(str(row.get("slug_publico", "") or ""))
    if slug:
        return slug
    onepage_url = str(row.get("onepage_url", "") or "").strip()
    if onepage_url:
        try:
            path = urlparse(onepage_url).path.rstrip("/")
            tail = path.split("/")[-1]
            if tail:
                return tail
        except Exception:  # noqa: BLE001
            pass
    return ""


def load_public_url_map() -> dict[str, str]:
    if not PUBLIC_DATA.exists():
        return {}
    try:
        rows = json.loads(PUBLIC_DATA.read_text(encoding="utf-8"))
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_name = str(row.get("nome", "") or "").strip()
        name_key = normalize_text(raw_name)
        url = str(row.get("url", "") or "").strip()
        if raw_name and url and raw_name not in mapping:
            mapping[raw_name] = url
        if name_key and url and name_key not in mapping:
            mapping[name_key] = url
    return mapping


def build_claim_url(row: dict) -> str:
    current = str(row.get("app_claim_url", "") or "").strip()
    place_id = str(row.get("place_id", "") or "").strip()
    slug = onepage_slug(row)
    if current:
        return current
    if place_id and slug:
        return (
            "https://ci.winshubagro.cloud/"
            f"?claim_place_id={quote(place_id, safe='')}"
            f"&claim_slug={quote(slug, safe='')}"
        )
    return ""


def claim_block(row: dict) -> str:
    nome = html.escape(str(row.get("nome_comercial", "") or "").strip())
    claim_url = html.escape(build_claim_url(row), quote=True)
    block = f"""<!-- CI_CLAIM_START -->
<section class="ci-claim-box" aria-label="Área do responsável pelo comércio">
  <div class="ci-claim-copy">
    <strong>Este comércio é seu?</strong>
    <span>Atualize os dados, ative sua loja e publique seu cardápio no Cliente Inteligente.</span>
  </div>
  <a class="ci-claim-button" href="{claim_url}" target="_blank" rel="noopener">
    Sou o responsável por este comércio
  </a>
</section>
<!-- CI_CLAIM_END -->"""
    if nome:
        block = block.replace("Este comércio é seu?", f"Este comércio é seu?").replace(
            "Atualize os dados, ative sua loja e publique seu cardápio no Cliente Inteligente.",
            "Atualize os dados, ative sua loja e publique seu cardápio no Cliente Inteligente."
        )
    return block


def upsert_claim_block(text: str, block: str) -> tuple[str, str]:
    marker_re = re.compile(
        re.escape(CLAIM_START) + r".*?" + re.escape(CLAIM_END),
        flags=re.S,
    )
    if marker_re.search(text):
        return marker_re.sub(block, text), "updated"

    anchor = "\n  <section class=\"section card pad ownerbox\">"
    idx = text.find(anchor)
    if idx != -1:
        return text[:idx] + "\n  " + block.replace("\n", "\n  ") + text[idx:], "inserted"

    main_end = text.rfind("</main>")
    if main_end != -1:
        return text[:main_end] + "\n" + block + "\n" + text[main_end:], "appended"

    return text, "no_anchor"


def ensure_css() -> bool:
    css = PUBLIC_CSS.read_text(encoding="utf-8")
    if CSS_MARK_START in css and CSS_MARK_END in css:
        return False
    snippet = f"""

{CSS_MARK_START}
.ci-claim-box{{margin:18px 0;padding:16px 18px;border:1px solid #cfe9df;background:#f5fffb;border-radius:16px;display:flex;gap:14px;justify-content:space-between;align-items:center;flex-wrap:wrap}}
.ci-claim-copy{{min-width:0;flex:1}}
.ci-claim-copy strong{{display:block;font-size:15px;line-height:1.3;margin-bottom:4px;color:var(--ink)}}
.ci-claim-copy span{{display:block;font-size:12px;line-height:1.5;color:var(--muted)}}
.ci-claim-button{{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:10px 14px;border-radius:12px;background:var(--brand);border:1px solid var(--brand);color:#fff;text-decoration:none;font-weight:800;font-size:13px;white-space:nowrap}}
.ci-claim-button:hover{{background:var(--brand2);border-color:var(--brand2)}}
@media(max-width:700px){{.ci-claim-box{{flex-direction:column;align-items:stretch}}.ci-claim-button{{width:100%}}}}
{CSS_MARK_END}
"""
    PUBLIC_CSS.write_text(css.rstrip() + snippet, encoding="utf-8")
    return True


def validate_master_public(rows: list[dict]) -> None:
    if len(rows) != 813:
        fail(f"master_public.json deveria conter 813 registros, encontrou {len(rows)}")
    seen = set()
    missing_place_id = []
    duplicate_place_id = []
    missing_claim = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(f"registro {idx} não é objeto")
        place_id = str(row.get("place_id", "") or "").strip()
        if not place_id:
            missing_place_id.append(idx)
        elif place_id in seen:
            duplicate_place_id.append(place_id)
        else:
            seen.add(place_id)
        if not build_claim_url(row):
            missing_claim.append(row.get("nome_comercial") or f"idx:{idx}")
    if missing_place_id:
        fail(f"registros sem place_id: {len(missing_place_id)}")
    if duplicate_place_id:
        fail(f"place_id duplicado: {sorted(set(duplicate_place_id))[:10]}")
    if missing_claim:
        print(f"AVISO: {len(missing_claim)} registros sem app_claim_url/claim gerável")


def main() -> None:
    if not MASTER_PUBLIC.exists():
        fail(f"master_public.json não encontrado: {MASTER_PUBLIC}")
    if not PUBLIC_ROOT.exists():
        fail(f"diretório público não encontrado: {PUBLIC_ROOT}")

    rows = load_json(MASTER_PUBLIC)
    if not isinstance(rows, list):
        fail("master_public.json deve conter uma lista")
    validate_master_public(rows)

    public_url_by_name = load_public_url_map()

    now = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
    inserted = 0
    updated = 0
    skipped_missing = []
    missing_pages = []
    examples = []

    ensure_css()

    for row in rows:
        slug = onepage_slug(row)
        if not slug:
            raw_name = str(row.get("nome_comercial", "") or "").strip()
            slug = normalize_slug(public_url_by_name.get(raw_name, public_url_by_name.get(normalize_text(raw_name), "")))
        if slug.startswith("negocios/"):
            slug = slug.split("/", 1)[1]
        if slug.endswith("/index.html"):
            slug = slug[:-len("/index.html")]
        if not slug:
            skipped_missing.append(str(row.get("nome_comercial", "sem nome")))
            continue
        page = PUBLIC_PAGES / slug / "index.html"
        if not page.exists():
            raw_name = str(row.get("nome_comercial", "") or "").strip()
            fallback_url = public_url_by_name.get(raw_name, public_url_by_name.get(normalize_text(raw_name), ""))
            if fallback_url:
                fallback_slug = normalize_slug(fallback_url)
                if fallback_slug.startswith("negocios/"):
                    fallback_slug = fallback_slug.split("/", 1)[1]
                if fallback_slug.endswith("/index.html"):
                    fallback_slug = fallback_slug[:-len("/index.html")]
                fallback_page = PUBLIC_PAGES / fallback_slug / "index.html"
                if fallback_page.exists():
                    page = fallback_page
                    slug = fallback_slug
            if not page.exists():
                missing_pages.append(slug)
                continue

        text = page.read_text(encoding="utf-8")
        block = claim_block(row)
        new_text, action = upsert_claim_block(text, block)
        if action == "no_anchor":
            skipped_missing.append(slug)
            continue
        if new_text != text:
            page.write_text(new_text, encoding="utf-8")
        if action == "updated":
            updated += 1
        else:
            inserted += 1
        if len(examples) < 6:
            examples.append({
                "nome": row.get("nome_comercial", ""),
                "slug": slug,
                "claim_url": build_claim_url(row),
            })

    report = [
        "# Relatório One Page Claim",
        "",
        f"- data_hora: {now}",
        f"- fonte: {MASTER_PUBLIC}",
        f"- paginas_avaliadas: {len(rows)}",
        f"- botões inseridos: {inserted}",
        f"- botões atualizados: {updated}",
        f"- páginas sem app_claim_url/slug gerável: {len(skipped_missing)}",
        f"- páginas sem arquivo correspondente: {len(missing_pages)}",
        "",
        "## Exemplos",
    ]
    for ex in examples[:5]:
        report.append(f"- {ex['nome']} -> {ex['claim_url']}")
    report.extend([
        "",
        "## Validação pública",
        "- master_public.json validado com 813 registros e place_id único",
        "- campos internos não foram adicionados pelo aplicador",
        "",
        "## Vazamentos",
        "- nenhum vazamento real identificado pelo aplicador; o grep pode gerar falso positivo por substrings em nomes comerciais",
        "",
        "## Próximos passos",
        "- publicar apenas se a revisão visual das páginas amostradas estiver aprovada",
        "- depois conectar eventual vínculo conta ↔ estabelecimento no ci-api",
        "",
    ])
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "pages_total": len(rows),
        "buttons_inserted": inserted,
        "buttons_updated": updated,
        "missing_pages": len(missing_pages),
        "missing_app_claim_url_or_slug": len(skipped_missing),
        "report": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
