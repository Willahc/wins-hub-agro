#!/usr/bin/env python3
"""Valida o claim-seed publico do Cliente Inteligente.

Regras cobertas:
- master_app_seed.json tem 813 registros
- place_id existe e e unico
- seed nao vaza campos internos
- ci-api/app.py expõe somente allowlist segura no payload do endpoint
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "ci-data" / "master_app_seed.json"
API_PATH = ROOT / "ci-api" / "app.py"

FORBIDDEN_KEYS = {
    "cnpj",
    "cnpj_status",
    "cnpj_confidence",
    "cnpj_candidates_json",
    "cnpj_candidate_count",
    "razao_social",
    "nome_fantasia",
    "score",
    "score_digital",
    "score_dor",
    "score_comercial",
    "lead_tier",
    "tier",
    "prioridade",
    "dor",
    "dor_dominante",
    "reclamacoes",
    "pitch",
    "pitch_presencial",
    "mensagem_whatsapp",
    "risco",
    "legal_risk",
    "nivel_confianca_interno",
    "nivel_confianca_publico",
    "whatsapp_confidence",
    "whatsapp_status",
    "whatsapp_publico",
    "whatsapp_prospeccao_url",
}
REQUIRED_SAFE_FIELDS = {
    "place_id",
    "slug_app",
    "nome_comercial",
    "segmento",
    "familia_segmento",
    "telefone",
    "endereco",
    "latitude",
    "longitude",
    "modulos_recomendados",
    "oferta_recomendada",
    "app_claim_url",
    "seed_config",
}


def fail(msg: str) -> None:
    print(f"ERRO: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"JSON invalido em {path}: {exc}")


def validate_seed() -> list[dict]:
    if not SEED_PATH.exists():
        fail(f"seed nao encontrado: {SEED_PATH}")
    data = load_json(SEED_PATH)
    if not isinstance(data, list):
        fail("master_app_seed.json deve conter uma lista")
    if len(data) != 813:
        fail(f"esperado 813 registros, encontrado {len(data)}")
    rows = []
    missing_place_id = []
    seen = set()
    duplicated = []
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            fail(f"registro {idx} nao e objeto")
        rows.append(row)
        place_id = str(row.get("place_id", "") or "").strip()
        if not place_id:
            missing_place_id.append(idx)
        elif place_id in seen:
            duplicated.append(place_id)
        else:
            seen.add(place_id)
        leaked = sorted(FORBIDDEN_KEYS.intersection(row.keys()))
        if leaked:
            fail(f"registro {idx} contem campos proibidos: {', '.join(leaked)}")
    if missing_place_id:
        fail(f"registros sem place_id: {len(missing_place_id)}")
    if duplicated:
        fail(f"place_id duplicado: {sorted(set(duplicated))[:10]}")
    print(f"OK seed: {len(rows)} registros, place_id unico")
    return rows


def _extract_constant_set(tree: ast.AST, name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = node.value
                    if isinstance(value, (ast.Set, ast.Tuple, ast.List)):
                        out = set()
                        for elt in value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                out.add(elt.value)
                        return out
                    fail(f"{name} nao e uma colecao literal de strings")
    fail(f"{name} nao encontrado em {API_PATH}")


def validate_api_allowlist() -> None:
    if not API_PATH.exists():
        fail(f"app.py nao encontrado: {API_PATH}")
    tree = ast.parse(API_PATH.read_text(encoding="utf-8"))
    safe_fields = _extract_constant_set(tree, "SAFE_CLAIM_FIELDS")
    prohibited = _extract_constant_set(tree, "CLAIM_PROHIBITED_KEYS")

    missing_required = sorted(REQUIRED_SAFE_FIELDS - safe_fields)
    if missing_required:
        fail(f"SAFE_CLAIM_FIELDS sem campos obrigatorios: {', '.join(missing_required)}")

    leaked = sorted(safe_fields & FORBIDDEN_KEYS)
    if leaked:
        fail(f"SAFE_CLAIM_FIELDS contem campos proibidos: {', '.join(leaked)}")

    leaked_prohibited = sorted(prohibited - FORBIDDEN_KEYS)
    if leaked_prohibited:
        fail(f"CLAIM_PROHIBITED_KEYS tem itens fora da politica atual: {', '.join(leaked_prohibited)}")

    if not safe_fields.issubset({
        "place_id", "slug_app", "nome_comercial", "segmento", "familia_segmento",
        "telefone", "endereco", "latitude", "longitude", "modulos_recomendados",
        "oferta_recomendada", "app_claim_url", "seed_config",
    }):
        fail("SAFE_CLAIM_FIELDS contem itens inesperados")

    print("OK allowlist ci-api: payload seguro limitado aos campos permitidos")


def main() -> None:
    validate_seed()
    validate_api_allowlist()
    print("OK validação claim seed publico")


if __name__ == "__main__":
    main()
