#!/usr/bin/env python3
"""
Construtor oficial da Base Mestre do Cliente Inteligente.

Modos:
  --check                 verifica fontes, V5 e integridade sem gerar artefatos
  --build                 gera artefatos finais somente se V5 estiver completo
  --build --allow-partial gera artefatos com sufixo _partial para teste/staging
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path("/root/wins_agro_v1")
PUBLIC_JSON = ROOT / "ci-lojas/cliente-inteligente/data/negocios.json"
PROSPEC_CSV = ROOT / "prospeccao-campanella/prospeccao_campanella_enriquecida_v3.csv"
V5_DIR = ROOT / "enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max"
V5_CSV = V5_DIR / "prospectos_v5max_externos.csv"
V5_JSON = V5_DIR / "prospectos_v5max_externos.json"
MASTER_DIR = ROOT / "master"

EXPECTED_PUBLIC = 813
EXPECTED_PROSPEC = 813
EXPECTED_V5 = 813
MIN_V5_CSV_LINES = 814
STABLE_SECONDS = 180

BASE_URL = "https://ci.winshubagro.cloud"
ONEPAGE_BASE = f"{BASE_URL}/loja/cliente-inteligente/negocios"

MASTER_FIELDS = [
    "place_id",
    "slug_publico",
    "slug_app",
    "nome_comercial",
    "segmento",
    "familia_segmento",
    "endereco",
    "latitude",
    "longitude",
    "maps_url",
    "telefone",
    "whatsapp_publico",
    "whatsapp_prospeccao_url",
    "whatsapp_confidence",
    "whatsapp_status",
    "site_oficial",
    "site_confidence",
    "instagram",
    "facebook",
    "cardapio_url",
    "delivery_url",
    "horario",
    "nota",
    "num_avaliacoes",
    "descricao_publica",
    "onepage_url",
    "app_claim_url",
    "prospeccao_url",
    "usar_onepage",
    "usar_app_comerciante",
    "usar_prospeccao",
    "publicavel_status",
    "nivel_confianca_publico",
    "nivel_confianca_interno",
    "fontes_json",
    "quality_flags",
    "updated_at",
    "cnpj",
    "cnpj_candidates_json",
    "cnpj_candidate_count",
    "cnpj_status",
    "cnpj_confidence",
    "cnpj_match_reason",
    "cnpj_source_url",
    "razao_social",
    "nome_fantasia",
    "situacao_cadastral",
    "cnae",
    "cnae_descricao",
    "porte",
    "data_abertura",
    "score_digital",
    "score_dor",
    "score_comercial",
    "lead_tier",
    "prioridade",
    "dor_dominante",
    "reclamacoes",
    "oferta_recomendada",
    "modulos_recomendados",
    "pitch_presencial",
    "mensagem_whatsapp",
    "acao_recomendada",
    "status_funil",
    "anotacoes",
]

PUBLIC_FIELDS = [
    "place_id",
    "slug_publico",
    "nome_comercial",
    "segmento",
    "familia_segmento",
    "endereco",
    "latitude",
    "longitude",
    "maps_url",
    "telefone",
    "whatsapp_publico",
    "site_oficial",
    "instagram",
    "facebook",
    "cardapio_url",
    "delivery_url",
    "horario",
    "nota",
    "num_avaliacoes",
    "descricao_publica",
    "onepage_url",
    "app_claim_url",
    "publicavel_status",
]

APP_FIELDS = [
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
]

FORBIDDEN_PUBLIC_KEY_PATTERNS = [
    "cnpj",
    "razao_social",
    "nome_fantasia",
    "score",
    "lead_tier",
    "tier",
    "prioridade",
    "dor",
    "reclam",
    "pitch",
    "mensagem_whatsapp",
    "risco",
    "legal_risk",
    "confidence",
    "nivel_confianca_interno",
    "fontes_json",
]

FIELD_COUNT_KEYS = [
    "whatsapp_publico",
    "whatsapp_prospeccao_url",
    "cnpj",
    "cnpj_candidates_json",
    "site_oficial",
    "instagram",
    "cardapio_url",
    "delivery_url",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: Any) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"nan", "none", "null"} else value


def to_bool(value: Any) -> bool:
    value = clean(value).lower()
    return value in {"1", "true", "sim", "yes", "y", "s"}


def to_number(value: Any) -> Any:
    value = clean(value)
    if not value:
        return None
    try:
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def first_nonempty(*values: Any) -> str:
    for value in values:
        value = clean(value)
        if value:
            return value
    return ""


def valid_url(value: Any) -> str:
    value = clean(value)
    if not value:
        return ""
    if value.lower() in {
        "nao",
        "não",
        "sim",
        "pendente",
        "pendente_enriquecimento_externo",
        "agregador",
        "candidato",
        "nao_encontrado",
        "não_encontrado",
    }:
        return ""
    return value if re.match(r"^https?://", value, flags=re.I) else ""


def first_valid_url(*values: Any) -> str:
    for value in values:
        url = valid_url(value)
        if url:
            return url
    return ""


def phone_is_public(value: Any) -> bool:
    digits = re.sub(r"\D+", "", clean(value))
    return 10 <= len(digits) <= 13


def probable_whatsapp(value: Any) -> bool:
    value = clean(value).lower()
    return value in {"1", "true", "sim", "yes", "y", "s", "provavel", "provável", "candidato", "validado"}


def best_number(*values: Any) -> float:
    numbers = []
    for value in values:
        value = clean(value)
        if not value:
            continue
        try:
            numbers.append(float(value))
        except ValueError:
            continue
    return max(numbers) if numbers else 0.0


def normalize_score(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return round(value, 2)


def normalize_cnpj(value: Any) -> str:
    digits = re.sub(r"\D+", "", clean(value))
    return digits if len(digits) == 14 else ""


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    value = clean(value)
    if not value:
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def cnpj_candidates_json(row_v5: dict[str, Any]) -> tuple[str, int]:
    candidates = parse_jsonish(row_v5.get("v5max_cnpj_candidates_json"))
    if isinstance(candidates, dict):
        items = candidates.get("candidates") or candidates.get("items") or []
    elif isinstance(candidates, list):
        items = candidates
    else:
        items = []
    if not isinstance(items, list):
        items = []
    return json.dumps(items, ensure_ascii=False, separators=(",", ":")), len(items)


def choose_cnpj(row_v5: dict[str, Any], row_prospec: dict[str, Any]) -> tuple[str, Any, str]:
    confidence = best_number(
        row_v5.get("v5max_cnpj_confidence"),
        row_prospec.get("cnpj_confidence"),
    )
    candidate = first_nonempty(
        row_v5.get("v5max_cnpj_candidato"),
        row_v5.get("cnpj"),
        row_prospec.get("cnpj_provavel"),
        row_prospec.get("cnpj_candidato"),
        row_prospec.get("cnpj"),
    )
    cnpj = normalize_cnpj(candidate)
    if cnpj and confidence >= 70:
        return cnpj, normalize_score(confidence), "provavel" if confidence < 90 else "confirmado"
    if cnpj:
        return "", normalize_score(confidence), "candidato_baixa_confianca"
    return "", normalize_score(confidence), first_nonempty(
        row_v5.get("cnpj_status"),
        row_prospec.get("cnpj_status"),
        "sem_cnpj_promovido",
    )


def choose_site(row_public: dict[str, Any], row_prospec: dict[str, Any], row_v5: dict[str, Any]) -> tuple[str, Any]:
    site = first_valid_url(
        row_v5.get("v5max_site_oficial_candidato"),
        row_prospec.get("website_oficial_url"),
        row_v5.get("website_oficial_url"),
        row_v5.get("website"),
        row_prospec.get("website"),
        row_public.get("site_oficial"),
    )
    confidence = best_number(
        row_v5.get("v5max_site_confidence"),
        row_prospec.get("website_oficial_confidence"),
    )
    if site and confidence == 0:
        confidence = 50
    return site, normalize_score(confidence)


def choose_whatsapp(row_v5: dict[str, Any], row_prospec: dict[str, Any], telefone: str) -> tuple[str, str, Any, str]:
    prospec_url = first_valid_url(
        row_v5.get("whatsapp_prospeccao_url"),
        row_prospec.get("whatsapp_prospeccao_url"),
        row_v5.get("v5max_whatsapp_externo"),
        row_prospec.get("whatsapp_candidato_url"),
    )
    confidence = best_number(row_v5.get("whatsapp_confidence"), row_prospec.get("whatsapp_confidence"))
    if prospec_url and confidence == 0:
        confidence = 80
    probable = probable_whatsapp(row_v5.get("whatsapp_provavel")) or probable_whatsapp(row_prospec.get("whatsapp_candidato"))
    if prospec_url:
        status = "url_prospeccao"
    elif phone_is_public(telefone) and probable:
        status = "provavel_por_telefone"
    elif phone_is_public(telefone):
        status = "telefone_publico_sem_confirmacao_whatsapp"
    else:
        status = "sem_telefone_publico"
    return prospec_url, prospec_url, normalize_score(confidence), status


def load_json_list(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} nao contem uma lista JSON")
    return [row for row in data if isinstance(row, dict)]


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        return [dict(row) for row in reader]


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def extract_place_id(maps_url: str) -> str:
    maps_url = clean(maps_url)
    match = re.search(r"!1s([^!]+)", maps_url)
    if match:
        return match.group(1)
    match = re.search(r"(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)", maps_url)
    return match.group(1) if match else ""


def slug_from_public(row: dict[str, Any]) -> str:
    url = clean(row.get("url"))
    match = re.search(r"(?:^|/)negocios/([^/]+)/index\.html$", url)
    if match:
        return match.group(1)
    match = re.search(r"(?:^|/)negocios/([^/]+)/?$", url)
    if match:
        return match.group(1)
    return clean(row.get("slug"))


def index_by_place_id(
    rows: list[dict[str, Any]], source: str, place_id_getter
) -> tuple[dict[str, dict[str, Any]], list[int], dict[str, int]]:
    indexed: dict[str, dict[str, Any]] = {}
    missing: list[int] = []
    counts: Counter[str] = Counter()
    for idx, row in enumerate(rows, start=1):
        place_id = clean(place_id_getter(row))
        if not place_id:
            missing.append(idx)
            continue
        counts[place_id] += 1
        if place_id not in indexed:
            indexed[place_id] = row
    duplicates = {place_id: count for place_id, count in counts.items() if count > 1}
    return indexed, missing, duplicates


def detect_v5_process() -> dict[str, Any]:
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=False)
    lines = []
    for line in result.stdout.splitlines():
        if "enriquecer_v5_max.py" in line and "grep" not in line:
            lines.append(line)
    return {"running": bool(lines), "matches": lines}


def file_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return datetime.now(timezone.utc).timestamp() - path.stat().st_mtime


def v5_status(v5_json_rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    process = detect_v5_process()
    csv_lines = count_lines(V5_CSV)
    json_count = len(v5_json_rows or [])
    csv_age = file_age_seconds(V5_CSV)
    json_age = file_age_seconds(V5_JSON)
    files_stable = (
        csv_age is not None
        and json_age is not None
        and csv_age >= STABLE_SECONDS
        and json_age >= STABLE_SECONDS
    )
    complete = (
        not process["running"]
        and csv_lines >= MIN_V5_CSV_LINES
        and json_count == EXPECTED_V5
        and files_stable
    )
    reasons = []
    if process["running"]:
        reasons.append("processo enriquecer_v5_max.py ainda esta rodando")
    if csv_lines < MIN_V5_CSV_LINES:
        reasons.append(f"CSV V5 tem {csv_lines} linhas; esperado minimo {MIN_V5_CSV_LINES}")
    if json_count != EXPECTED_V5:
        reasons.append(f"JSON V5 tem {json_count} registros; esperado {EXPECTED_V5}")
    if not files_stable:
        reasons.append("arquivos V5 foram modificados ha menos de 3 minutos ou estao ausentes")
    return {
        "running": process["running"],
        "process_matches": process["matches"],
        "csv_lines": csv_lines,
        "json_count": json_count,
        "csv_age_seconds": csv_age,
        "json_age_seconds": json_age,
        "files_stable_3min": files_stable,
        "complete_for_final_build": complete,
        "block_reasons": reasons,
    }


def public_url(slug: str) -> str:
    return f"{ONEPAGE_BASE}/{slug}/"


def claim_url(place_id: str, slug: str) -> str:
    return f"{BASE_URL}/?claim_place_id={quote(place_id)}&claim_slug={quote(slug)}"


def prospection_url(place_id: str) -> str:
    return f"{BASE_URL}/prospec/?place_id={quote(place_id)}"


def family_from(row_public: dict[str, Any], row_prospec: dict[str, Any], row_v5: dict[str, Any]) -> str:
    return first_nonempty(
        row_v5.get("macrosegmento"),
        row_prospec.get("macrosegmento"),
        row_public.get("seg_key"),
        row_public.get("segmento"),
    )


def split_modules(value: Any) -> list[str]:
    value = clean(value)
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;/|]+", value) if part.strip()]


def build_seed_config(record: dict[str, Any]) -> dict[str, Any]:
    modules = record.get("modulos_recomendados") or []
    if isinstance(modules, str):
        modules = split_modules(modules)
    return {
        "segmento": record["segmento"],
        "familia_segmento": record["familia_segmento"],
        "modulos_iniciais": modules,
        "usar_cardapio": "cardapio" in {m.lower() for m in modules},
        "usar_delivery": "delivery" in {m.lower() for m in modules},
        "origem": "base_mestre_cliente_inteligente",
    }


def make_master_record(
    place_id: str,
    row_public: dict[str, Any],
    row_prospec: dict[str, Any],
    row_v5: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    slug_publico = first_nonempty(row_v5.get("slug"), slug_from_public(row_public))
    onepage = public_url(slug_publico)
    maps_url = first_nonempty(row_public.get("maps_url"), row_prospec.get("maps_url"), row_v5.get("maps_url"))
    modules = split_modules(first_nonempty(row_v5.get("modulos_recomendados"), row_prospec.get("modulos_recomendados")))
    public_confidence = 95
    internal_confidence = normalize_score(best_number(row_v5.get("v5max_cnpj_confidence"), row_prospec.get("cnpj_confidence")))
    site, site_confidence = choose_site(row_public, row_prospec, row_v5)
    instagram = first_valid_url(row_v5.get("v5max_instagram_url"), row_v5.get("instagram_coletado"), row_prospec.get("instagram_url"), row_prospec.get("instagram_coletado"), row_public.get("instagram"))
    cardapio_url = first_valid_url(row_v5.get("v5max_delivery_cardapio_url"), row_prospec.get("cardapio_url"))
    delivery_url = first_valid_url(row_v5.get("v5max_delivery_cardapio_url"), row_prospec.get("ifood_rappi_99food"), row_v5.get("delivery_url"), row_prospec.get("delivery_url"))
    cnpj, cnpj_confidence, cnpj_status = choose_cnpj(row_v5, row_prospec)
    candidates_json, candidate_count = cnpj_candidates_json(row_v5)
    telefone = first_nonempty(row_public.get("telefone"), row_v5.get("telefone"), row_prospec.get("telefone"))
    whatsapp_publico, whatsapp_prospeccao_url, whatsapp_confidence, whatsapp_status = choose_whatsapp(row_v5, row_prospec, telefone)
    if candidate_count and not cnpj:
        cnpj_status = "candidatos_sem_promocao"
    quality_flags = []
    for source_row in (row_prospec, row_v5):
        for key in ("data_quality_flags", "v5max_quality_flags"):
            value = clean(source_row.get(key))
            if value:
                quality_flags.extend([part.strip() for part in re.split(r"[,;|]+", value) if part.strip()])
    if not slug_publico:
        quality_flags.append("sem_slug_publico")
    if not maps_url:
        quality_flags.append("sem_maps_url")
    return {
        "place_id": place_id,
        "slug_publico": slug_publico,
        "slug_app": "",
        "nome_comercial": first_nonempty(row_public.get("nome"), row_v5.get("nome"), row_prospec.get("nome")),
        "segmento": first_nonempty(row_public.get("segmento"), row_v5.get("segmento_original"), row_prospec.get("segmento_original")),
        "familia_segmento": family_from(row_public, row_prospec, row_v5),
        "endereco": first_nonempty(row_public.get("endereco"), row_v5.get("endereco"), row_prospec.get("endereco")),
        "latitude": to_number(first_nonempty(row_v5.get("lat"), row_prospec.get("lat"))),
        "longitude": to_number(first_nonempty(row_v5.get("lng"), row_prospec.get("lng"))),
        "maps_url": maps_url,
        "telefone": telefone,
        "whatsapp_publico": whatsapp_publico,
        "whatsapp_prospeccao_url": whatsapp_prospeccao_url,
        "whatsapp_confidence": whatsapp_confidence,
        "whatsapp_status": whatsapp_status,
        "site_oficial": site,
        "site_confidence": site_confidence,
        "instagram": instagram,
        "facebook": first_valid_url(row_v5.get("v5max_facebook_url")),
        "cardapio_url": cardapio_url,
        "delivery_url": delivery_url,
        "horario": "",
        "nota": to_number(first_nonempty(row_public.get("nota"), row_v5.get("nota_google"), row_prospec.get("nota_google"))),
        "num_avaliacoes": to_number(first_nonempty(row_public.get("num_avaliacoes"), row_v5.get("num_avaliacoes"), row_prospec.get("num_avaliacoes"))),
        "descricao_publica": "",
        "onepage_url": onepage,
        "app_claim_url": claim_url(place_id, slug_publico),
        "prospeccao_url": prospection_url(place_id),
        "usar_onepage": True,
        "usar_app_comerciante": True,
        "usar_prospeccao": True,
        "publicavel_status": "PUBLICAVEL" if slug_publico and maps_url else "REVISAR",
        "nivel_confianca_publico": public_confidence,
        "nivel_confianca_interno": internal_confidence,
        "fontes_json": {
            "publico": str(PUBLIC_JSON),
            "prospeccao_v3": str(PROSPEC_CSV),
            "v5_json": str(V5_JSON),
            "v5_csv": str(V5_CSV),
        },
        "quality_flags": sorted(set(quality_flags)),
        "updated_at": timestamp,
        "cnpj": cnpj,
        "cnpj_candidates_json": candidates_json,
        "cnpj_candidate_count": candidate_count,
        "cnpj_status": first_nonempty(row_v5.get("v5max_cnpj_situacao"), cnpj_status),
        "cnpj_confidence": cnpj_confidence,
        "cnpj_match_reason": first_nonempty(row_v5.get("v5max_cnpj_match_reason"), row_prospec.get("cnpj_match_reason")),
        "cnpj_source_url": first_valid_url(row_v5.get("v5max_cnpj_source_url")),
        "razao_social": first_nonempty(row_v5.get("v5max_razao_social"), row_v5.get("razao_social"), row_prospec.get("razao_social")),
        "nome_fantasia": first_nonempty(row_v5.get("v5max_nome_fantasia"), row_prospec.get("nome_fantasia")),
        "situacao_cadastral": first_nonempty(row_v5.get("v5max_cnpj_situacao"), row_v5.get("situacao_cadastral"), row_prospec.get("situacao_cadastral")),
        "cnae": first_nonempty(row_v5.get("v5max_cnae_principal"), row_prospec.get("cnae_principal_codigo"), row_prospec.get("cnae_principal")),
        "cnae_descricao": first_nonempty(row_prospec.get("cnae_principal_descricao")),
        "porte": first_nonempty(row_v5.get("v5max_porte"), row_prospec.get("porte")),
        "data_abertura": first_nonempty(row_v5.get("v5max_abertura"), row_prospec.get("data_abertura")),
        "score_digital": to_number(first_nonempty(row_v5.get("v5max_maturidade_digital_score"), row_prospec.get("digital_presence_score_v2"), row_prospec.get("digital_gap_score_v2"))),
        "score_dor": to_number(first_nonempty(row_prospec.get("pain_score"))),
        "score_comercial": to_number(first_nonempty(row_prospec.get("conversion_score_v3_final"), row_v5.get("conversion_score_v4"), row_prospec.get("conversion_score_v2"))),
        "lead_tier": first_nonempty(row_v5.get("lead_tier_v4"), row_prospec.get("lead_tier_v3"), row_prospec.get("lead_tier_v2")),
        "prioridade": first_nonempty(row_v5.get("v5max_prioridade_final"), row_v5.get("prioridade_original"), row_prospec.get("prioridade_original")),
        "dor_dominante": first_nonempty(row_v5.get("dor_dominante"), row_prospec.get("dor_dominante")),
        "reclamacoes": {
            "total": to_number(first_nonempty(row_v5.get("num_reclamacoes_coletadas"), row_prospec.get("num_reclamacoes_coletadas"))),
            "categorias": first_nonempty(row_v5.get("dor_categorias_contagem"), row_prospec.get("dor_categorias_contagem")),
        },
        "oferta_recomendada": first_nonempty(row_v5.get("oferta_principal"), row_prospec.get("oferta_principal")),
        "modulos_recomendados": modules,
        "pitch_presencial": first_nonempty(row_v5.get("pitch_presencial"), row_prospec.get("pitch_presencial"), row_prospec.get("pitch_recomendado")),
        "mensagem_whatsapp": first_nonempty(row_v5.get("mensagem_whatsapp"), row_prospec.get("mensagem_whatsapp")),
        "acao_recomendada": first_nonempty(row_v5.get("acao_recomendada"), row_v5.get("v5max_proxima_acao"), row_prospec.get("acao_recomendada")),
        "status_funil": first_nonempty(row_v5.get("status_funil"), row_prospec.get("status_funil"), "novo"),
        "anotacoes": first_nonempty(row_v5.get("observacoes_vendedor"), row_prospec.get("observacoes_vendedor")),
    }


def public_view(record: dict[str, Any]) -> dict[str, Any]:
    data = {field: record.get(field) for field in PUBLIC_FIELDS}
    if not (
        phone_is_public(record.get("telefone"))
        and (
            probable_whatsapp(record.get("whatsapp_status"))
            or valid_url(record.get("whatsapp_prospeccao_url"))
        )
    ):
        data["whatsapp_publico"] = ""
    return data


def app_seed_view(record: dict[str, Any]) -> dict[str, Any]:
    data = {field: record.get(field) for field in APP_FIELDS if field != "seed_config"}
    data["seed_config"] = build_seed_config(record)
    return data


def validate_public(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors = []
    allowed = set(PUBLIC_FIELDS)
    for idx, record in enumerate(records, start=1):
        for key in record.keys():
            key_lower = key.lower()
            if key not in allowed:
                errors.append({"row": idx, "field": key, "error": "campo fora da whitelist"})
            for pattern in FORBIDDEN_PUBLIC_KEY_PATTERNS:
                if pattern in key_lower:
                    errors.append({"row": idx, "field": key, "error": f"campo proibido: {pattern}"})
    return {
        "ok": not errors,
        "records": len(records),
        "allowed_fields": PUBLIC_FIELDS,
        "forbidden_key_patterns": FORBIDDEN_PUBLIC_KEY_PATTERNS,
        "errors": errors[:200],
        "error_count": len(errors),
        "validated_at": now_iso(),
    }


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def count_present(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        field: sum(1 for record in records if clean(record.get(field)))
        for field in FIELD_COUNT_KEYS
    }


def existing_counts() -> dict[str, dict[str, int]]:
    files = {
        "cliente_inteligente_master": MASTER_DIR / "cliente_inteligente_master.json",
        "master_public": MASTER_DIR / "master_public.json",
        "master_app_seed": MASTER_DIR / "master_app_seed.json",
        "master_prospeccao": MASTER_DIR / "master_prospeccao.json",
    }
    counts: dict[str, dict[str, int]] = {}
    for label, path in files.items():
        if not path.exists():
            counts[label] = {field: 0 for field in FIELD_COUNT_KEYS}
            continue
        counts[label] = count_present(load_json_list(path))
    return counts


def make_report(
    context: dict[str, Any],
    generated: dict[str, str],
    partial: bool,
    field_counts: dict[str, Any] | None = None,
) -> str:
    status = context["v5_status"]
    lines = [
        "# Relatorio Base Mestre Cliente Inteligente",
        "",
        "- Versao: v1.1",
        f"- Gerado em: {now_iso()}",
        f"- Modo parcial: {'sim' if partial else 'nao'}",
        f"- V5 completo para build final: {'sim' if status['complete_for_final_build'] else 'nao'}",
        f"- V5 rodando: {'sim' if status['running'] else 'nao'}",
        f"- Linhas CSV V5: {status['csv_lines']}",
        f"- Registros JSON V5: {status['json_count']}",
        f"- Arquivos V5 estaveis por 3 minutos: {'sim' if status['files_stable_3min'] else 'nao'}",
        "",
        "## Contagens",
        "",
        f"- Publico JSON: {context['counts']['public_json']}",
        f"- Prospecção CSV: {context['counts']['prospec_csv']}",
        f"- V5 JSON: {context['counts']['v5_json']}",
        f"- Match publico vs prospeccao por place_id: {context['matches']['public_vs_prospec']}",
        f"- Match prospeccao vs V5 por place_id: {context['matches']['prospec_vs_v5']}",
        "",
        "## Campos corrigidos v1.1",
        "",
        "- WhatsApp: `whatsapp_publico`, `whatsapp_prospeccao_url`, `whatsapp_confidence`, `whatsapp_status`.",
        "- CNPJ: promocao conservadora para `cnpj`, preservando `cnpj_confidence`, `cnpj_status`, `cnpj_candidates_json` e `cnpj_candidate_count` como campos internos.",
        "- Presenca digital: `site_oficial`, `site_confidence`, `instagram`, `cardapio_url` e `delivery_url` agora filtram URLs reais.",
        "- Publico: `master_public.json` segue whitelist publica e nao inclui CNPJ, scores, tiers, dores, pitch ou candidatos internos.",
        "",
        "## Contagem antes/depois",
        "",
    ]
    if field_counts:
        for view, before in field_counts["before"].items():
            after = field_counts["after"].get(view, {})
            lines.append(f"### {view}")
            for field in FIELD_COUNT_KEYS:
                lines.append(f"- {field}: {before.get(field, 0)} -> {after.get(field, 0)}")
            lines.append("")
    else:
        lines.append("- Contagem antes/depois nao disponivel neste modo.")
        lines.append("")
    lines.extend([
        "## Problemas de integridade",
        "",
    ])
    problems = context["problems"]
    for key, value in problems.items():
        lines.append(f"- {key}: {value}")
    if not any(problems.values()):
        lines.append("- Nenhum problema bloqueante encontrado.")
    lines.extend([
        "",
        "## Segurança pública",
        "",
        f"- Validação pública OK: {'sim' if context['public_validation']['ok'] else 'nao'}",
        f"- Erros de validação pública: {context['public_validation']['error_count']}",
        "",
        "## Campos públicos",
        "",
        ", ".join(PUBLIC_FIELDS),
        "",
        "## Campos internos",
        "",
        ", ".join(field for field in MASTER_FIELDS if field not in PUBLIC_FIELDS),
        "",
        "## Arquivos gerados",
        "",
    ])
    if generated:
        for label, path in generated.items():
            lines.append(f"- {label}: `{path}`")
    else:
        lines.append("- Nenhum arquivo final gerado.")
    lines.extend([
        "",
        "## Próximos passos",
        "",
        "1. Se o V5 estiver incompleto, aguardar finalizacao e rodar `--check` novamente.",
        "2. Quando o V5 estiver completo e parado, rodar `--build`.",
        "3. Antes de publicar One Pages, validar `master_public.json`.",
    ])
    return "\n".join(lines) + "\n"


def analyze_sources() -> dict[str, Any]:
    public_rows = load_json_list(PUBLIC_JSON)
    prospec_rows = load_csv(PROSPEC_CSV)
    v5_rows = load_json_list(V5_JSON) if V5_JSON.exists() else []

    public_idx, public_missing, public_dups = index_by_place_id(
        public_rows, "publico", lambda row: extract_place_id(row.get("maps_url", ""))
    )
    prospec_idx, prospec_missing, prospec_dups = index_by_place_id(
        prospec_rows, "prospeccao", lambda row: row.get("place_id")
    )
    v5_idx, v5_missing, v5_dups = index_by_place_id(v5_rows, "v5", lambda row: row.get("place_id"))

    public_slugs = [slug_from_public(row) for row in public_rows]
    slug_counts = Counter(slug for slug in public_slugs if slug)
    slug_dups = {slug: count for slug, count in slug_counts.items() if count > 1}

    public_set = set(public_idx)
    prospec_set = set(prospec_idx)
    v5_set = set(v5_idx)

    missing_public_in_prospec = sorted(public_set - prospec_set)
    missing_prospec_in_public = sorted(prospec_set - public_set)
    missing_prospec_in_v5 = sorted(prospec_set - v5_set)
    missing_v5_in_prospec = sorted(v5_set - prospec_set)

    status = v5_status(v5_rows)
    context = {
        "rows": {
            "public": public_rows,
            "prospec": prospec_rows,
            "v5": v5_rows,
        },
        "indexes": {
            "public": public_idx,
            "prospec": prospec_idx,
            "v5": v5_idx,
        },
        "counts": {
            "public_json": len(public_rows),
            "prospec_csv": len(prospec_rows),
            "v5_json": len(v5_rows),
            "public_place_ids": len(public_idx),
            "prospec_place_ids": len(prospec_idx),
            "v5_place_ids": len(v5_idx),
        },
        "matches": {
            "public_vs_prospec": len(public_set & prospec_set),
            "prospec_vs_v5": len(prospec_set & v5_set),
        },
        "problems": {
            "public_missing_place_id_rows": public_missing[:50],
            "prospec_missing_place_id_rows": prospec_missing[:50],
            "v5_missing_place_id_rows": v5_missing[:50],
            "public_duplicate_place_ids": public_dups,
            "prospec_duplicate_place_ids": prospec_dups,
            "v5_duplicate_place_ids": v5_dups,
            "duplicate_slug_publico": slug_dups,
            "missing_public_in_prospec": missing_public_in_prospec[:50],
            "missing_prospec_in_public": missing_prospec_in_public[:50],
            "missing_prospec_in_v5": missing_prospec_in_v5[:50],
            "missing_v5_in_prospec": missing_v5_in_prospec[:50],
        },
        "v5_status": status,
    }
    return context


def build_records(context: dict[str, Any]) -> list[dict[str, Any]]:
    timestamp = now_iso()
    public_idx = context["indexes"]["public"]
    prospec_idx = context["indexes"]["prospec"]
    v5_idx = context["indexes"]["v5"]
    records = []
    for place_id in sorted(public_idx):
        records.append(
            make_master_record(
                place_id,
                public_idx.get(place_id, {}),
                prospec_idx.get(place_id, {}),
                v5_idx.get(place_id, {}),
                timestamp,
            )
        )
    return records


def blocking_integrity_errors(context: dict[str, Any], require_v5_complete: bool) -> list[str]:
    errors = []
    counts = context["counts"]
    matches = context["matches"]
    problems = context["problems"]
    if counts["public_json"] != EXPECTED_PUBLIC:
        errors.append(f"public_json={counts['public_json']} esperado={EXPECTED_PUBLIC}")
    if counts["prospec_csv"] != EXPECTED_PROSPEC:
        errors.append(f"prospec_csv={counts['prospec_csv']} esperado={EXPECTED_PROSPEC}")
    if matches["public_vs_prospec"] != EXPECTED_PUBLIC:
        errors.append(f"publico vs prospeccao={matches['public_vs_prospec']} esperado={EXPECTED_PUBLIC}")
    for key in (
        "public_missing_place_id_rows",
        "prospec_missing_place_id_rows",
        "public_duplicate_place_ids",
        "prospec_duplicate_place_ids",
        "duplicate_slug_publico",
        "missing_public_in_prospec",
        "missing_prospec_in_public",
    ):
        if problems[key]:
            errors.append(f"{key}: {problems[key]}")
    if require_v5_complete:
        if not context["v5_status"]["complete_for_final_build"]:
            errors.extend(context["v5_status"]["block_reasons"])
        if counts["v5_json"] != EXPECTED_V5:
            errors.append(f"v5_json={counts['v5_json']} esperado={EXPECTED_V5}")
        if matches["prospec_vs_v5"] != EXPECTED_V5:
            errors.append(f"prospeccao vs V5={matches['prospec_vs_v5']} esperado={EXPECTED_V5}")
        for key in ("v5_missing_place_id_rows", "v5_duplicate_place_ids", "missing_prospec_in_v5", "missing_v5_in_prospec"):
            if problems[key]:
                errors.append(f"{key}: {problems[key]}")
    return errors


def print_check_summary(context: dict[str, Any], errors: list[str]) -> None:
    status = context["v5_status"]
    print("Base Mestre Cliente Inteligente - check")
    print(f"public_json: {context['counts']['public_json']}")
    print(f"prospec_csv: {context['counts']['prospec_csv']}")
    print(f"v5_json: {context['counts']['v5_json']}")
    print(f"v5_csv_linhas: {status['csv_lines']}")
    print(f"match_publico_prospeccao_place_id: {context['matches']['public_vs_prospec']}/813")
    print(f"match_prospeccao_v5_place_id: {context['matches']['prospec_vs_v5']}/813")
    print(f"v5_rodando: {'sim' if status['running'] else 'nao'}")
    print(f"v5_estavel_3min: {'sim' if status['files_stable_3min'] else 'nao'}")
    print(f"v5_completo_para_build_final: {'sim' if status['complete_for_final_build'] else 'nao'}")
    if status["block_reasons"]:
        print("V5 ainda incompleto; aguardando finalização")
        for reason in status["block_reasons"]:
            print(f"- {reason}")
    if errors:
        print("Problemas bloqueantes:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Integridade base OK para as fontes exigidas no modo solicitado.")


def run_check() -> int:
    context = analyze_sources()
    records = build_records(context)
    context["public_validation"] = validate_public([public_view(record) for record in records])
    errors = blocking_integrity_errors(context, require_v5_complete=False)
    print_check_summary(context, errors)
    return 1 if errors else 0


def run_build(allow_partial: bool) -> int:
    context = analyze_sources()
    require_v5 = not allow_partial
    errors = blocking_integrity_errors(context, require_v5_complete=require_v5)
    before_counts = existing_counts()
    records = build_records(context)
    public_records = [public_view(record) for record in records]
    app_records = [app_seed_view(record) for record in records]
    prospec_records = records
    after_counts = {
        "cliente_inteligente_master": count_present(records),
        "master_public": count_present(public_records),
        "master_app_seed": count_present(app_records),
        "master_prospeccao": count_present(prospec_records),
    }
    field_counts = {"before": before_counts, "after": after_counts}
    validation = validate_public(public_records)
    context["public_validation"] = validation
    if not validation["ok"]:
        errors.append("master_public.json contem campos proibidos ou fora da whitelist")
    if errors and not allow_partial:
        print_check_summary(context, errors)
        print("Build final bloqueado.")
        return 2

    suffix = "_partial" if allow_partial else ""
    outputs = {
        "master": MASTER_DIR / f"cliente_inteligente_master{suffix}.json",
        "public": MASTER_DIR / f"master_public{suffix}.json",
        "app_seed": MASTER_DIR / f"master_app_seed{suffix}.json",
        "prospeccao": MASTER_DIR / f"master_prospeccao{suffix}.json",
        "validation": MASTER_DIR / f"validation_public{suffix}.json",
        "validation_v1_1": MASTER_DIR / f"validation_public_v1_1{suffix}.json",
        "report": MASTER_DIR / f"relatorio_master_build{suffix}.md",
        "report_v1_1": MASTER_DIR / f"relatorio_master_build_v1_1{suffix}.md",
    }
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    write_json(outputs["master"], records)
    write_json(outputs["public"], public_records)
    write_json(outputs["app_seed"], app_records)
    write_json(outputs["prospeccao"], prospec_records)
    write_json(outputs["validation"], validation)
    write_json(outputs["validation_v1_1"], validation)
    generated = {key: str(path) for key, path in outputs.items()}
    report = make_report(context, generated, allow_partial, field_counts)
    outputs["report"].write_text(report, encoding="utf-8")
    outputs["report_v1_1"].write_text(report, encoding="utf-8")
    print_check_summary(context, errors)
    if allow_partial:
        print("Build parcial gerado com sufixo _partial. Nao usar em producao.")
    else:
        print("Build final gerado com sucesso.")
    for key, path in outputs.items():
        print(f"{key}: {path}")
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Construtor da Base Mestre Cliente Inteligente")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="verifica fontes sem gerar artefatos")
    group.add_argument("--build", action="store_true", help="gera artefatos da Base Mestre")
    parser.add_argument("--allow-partial", action="store_true", help="gera artefatos _partial mesmo com V5 incompleto")
    args = parser.parse_args()

    if args.allow_partial and not args.build:
        parser.error("--allow-partial so pode ser usado com --build")

    try:
        if args.check:
            return run_check()
        return run_build(args.allow_partial)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
