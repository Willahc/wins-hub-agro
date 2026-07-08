#!/usr/bin/env python3
"""Auditoria somente leitura do fluxo de dados do Cliente Inteligente.

Compara One Pages publicas, prospeccao, dashboard e ci-api sem alterar arquivos
de producao, bancos ou processos. A saida e texto/JSON para subsidiar relatorio.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path("/root/wins_agro_v1")
PUBLIC_DIR = ROOT / "ci-lojas" / "cliente-inteligente"
PROSPEC_DIR = ROOT / "prospeccao-campanella"
CI_DIR = ROOT / "ci"
CI_API_DIR = ROOT / "ci-api"
CI_DB = ROOT / "ci-data" / "ci.db"
PROSPEC_DB = PROSPEC_DIR / "campanella_prospeccao_enriquecida_v3.db"
PROSPEC_CSV = PROSPEC_DIR / "prospeccao_campanella_enriquecida_v3.csv"
DASHBOARD = PROSPEC_DIR / "dashboard.html"


def norm(s: object) -> str:
    return " ".join(str(s or "").strip().casefold().split())


def extract_place_id(url: object) -> str:
    text = str(url or "")
    match = re.search(r"!1s([^!]+)", text)
    return match.group(1) if match else ""


def slug_from_url(url: object) -> str:
    text = str(url or "")
    parts = [p for p in text.split("/") if p]
    if len(parts) >= 2 and parts[-1] == "index.html":
        return parts[-2]
    if parts:
        return parts[-1]
    return ""


def load_public_json() -> list[dict]:
    path = PUBLIC_DIR / "data" / "negocios.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for row in data:
        rows.append({
            **row,
            "_place_id_from_maps": extract_place_id(row.get("maps_url")),
            "_slug": slug_from_url(row.get("url")),
            "_nome_norm": norm(row.get("nome")),
        })
    return rows


def load_dashboard_json() -> list[dict]:
    text = DASHBOARD.read_text(encoding="utf-8")
    match = re.search(r'<script id="dados" type="application/json">(.*?)</script>', text, re.S)
    if not match:
        return []
    return json.loads(match.group(1))


def read_sqlite_schema(path: Path) -> dict:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by name")]
        for table in tables:
            cols = [redact_column_name(r[1]) for r in con.execute(f"pragma table_info({table})")]
            count = con.execute(f"select count(*) from {table}").fetchone()[0]
            out[table] = {"columns": cols, "count": count}
    finally:
        con.close()
    return out


def redact_column_name(name: str) -> str:
    lowered = name.lower()
    sensitive = ("hash", "salt", "token", "senha", "password", "secret", "key")
    if any(part in lowered for part in sensitive):
        return "[redigido]"
    return name


def load_prospec_db_rows() -> list[dict]:
    con = sqlite3.connect(f"file:{PROSPEC_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("select * from estabelecimentos_enriquecidos_v3")]
    finally:
        con.close()
    for row in rows:
        row["_nome_norm"] = norm(row.get("nome"))
        row["_slug_guess"] = ""
    return rows


def load_prospec_csv_sample() -> tuple[list[str], int]:
    with PROSPEC_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        header = reader.fieldnames or []
        rows = sum(1 for _ in reader)
    return header, rows


def duplicate_counts(rows: list[dict], key: str) -> dict:
    values = [r.get(key) for r in rows if r.get(key)]
    counts = Counter(values)
    dups = {k: v for k, v in counts.items() if v > 1}
    return {"total_values": len(values), "unique": len(counts), "duplicates": dups}


def scan_text(path: Path, patterns: list[str]) -> dict[str, int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {p: len(re.findall(p, text, re.I)) for p in patterns}


def main() -> None:
    public = load_public_json()
    dashboard = load_dashboard_json()
    prospec = load_prospec_db_rows()
    ci_schema = read_sqlite_schema(CI_DB)
    prospec_schema = read_sqlite_schema(PROSPEC_DB)
    csv_header, csv_rows = load_prospec_csv_sample()

    public_place_ids = {r["_place_id_from_maps"] for r in public if r["_place_id_from_maps"]}
    prospec_place_ids = {r.get("place_id") for r in prospec if r.get("place_id")}

    public_slugs = {r["_slug"] for r in public if r["_slug"]}
    page_slugs = {p.parent.name for p in (PUBLIC_DIR / "negocios").glob("*/index.html")}

    public_names = {r["_nome_norm"] for r in public if r["_nome_norm"]}
    prospec_names = {r["_nome_norm"] for r in prospec if r["_nome_norm"]}

    app_index = CI_DIR / "index.html"
    ci_api = CI_API_DIR / "app.py"
    public_page_js = PUBLIC_DIR / "assets" / "page.js"
    public_index_js = PUBLIC_DIR / "assets" / "index.js"

    report = {
        "counts": {
            "public_json_records": len(public),
            "public_page_dirs": len(page_slugs),
            "dashboard_records": len(dashboard),
            "prospec_db_records": len(prospec),
            "prospec_csv_rows": csv_rows,
        },
        "identity_matches": {
            "public_place_ids_from_maps": len(public_place_ids),
            "prospec_place_ids": len(prospec_place_ids),
            "place_ids_in_both": len(public_place_ids & prospec_place_ids),
            "public_missing_in_prospec_by_place_id": len(public_place_ids - prospec_place_ids),
            "prospec_missing_in_public_by_place_id": len(prospec_place_ids - public_place_ids),
            "names_in_both": len(public_names & prospec_names),
            "public_missing_in_prospec_by_name": len(public_names - prospec_names),
            "prospec_missing_in_public_by_name": len(prospec_names - public_names),
            "public_json_slugs": len(public_slugs),
            "public_page_dir_slugs": len(page_slugs),
            "slugs_json_without_page": sorted(public_slugs - page_slugs)[:20],
            "page_dirs_without_json_slug": sorted(page_slugs - public_slugs)[:20],
        },
        "duplicates": {
            "public_slug": duplicate_counts(public, "_slug"),
            "public_place_id": duplicate_counts(public, "_place_id_from_maps"),
            "public_name": duplicate_counts(public, "_nome_norm"),
            "prospec_place_id": duplicate_counts(prospec, "place_id"),
            "prospec_name": duplicate_counts(prospec, "_nome_norm"),
        },
        "schemas": {
            "ci_db": ci_schema,
            "prospec_db": prospec_schema,
            "prospec_csv_columns": csv_header,
        },
        "text_scans": {
            "ci_index": scan_text(app_index, [
                r"seed", r"segmento", r"localStorage", r"IndexedDB", r"Dexie",
                r"/api/loja", r"/api/register", r"slug", r"place_id",
            ]),
            "ci_api": scan_text(ci_api, [
                r"CREATE TABLE", r"contas", r"sessions", r"estabelec",
                r"prospecc", r"master", r"status", r"observa", r"/api/loja",
            ]),
            "public_page_js": scan_text(public_page_js, [
                r"ownerForm", r"mailto:", r"slug", r"place_id", r"/api/", r"ci.winshubagro.cloud",
            ]),
            "public_index_js": scan_text(public_index_js, [
                r"fetch", r"negocios.json", r"slug", r"place_id", r"/api/",
            ]),
            "dashboard": scan_text(DASHBOARD, [
                r"/loja/cliente-inteligente", r"publica", r"One Page", r"slug",
                r"place_id", r"localStorage", r"ci_prospec_note_", r"cnpj",
                r"pitch", r"score", r"Tier",
            ]),
        },
        "sample_mismatches": {
            "public_place_ids_not_in_prospec": sorted(public_place_ids - prospec_place_ids)[:10],
            "prospec_place_ids_not_in_public": sorted(prospec_place_ids - public_place_ids)[:10],
            "public_names_not_in_prospec": sorted(public_names - prospec_names)[:10],
            "prospec_names_not_in_public": sorted(prospec_names - public_names)[:10],
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
