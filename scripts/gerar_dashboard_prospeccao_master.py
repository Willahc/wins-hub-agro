#!/usr/bin/env python3
"""Gera a Prospecção staging a partir da Base Mestre oficial."""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/root/wins_agro_v1")
SOURCE = ROOT / "master" / "master_prospeccao.json"
OUT_DIR = ROOT / "staging" / "prospec-master"
DASHBOARD = OUT_DIR / "dashboard.html"
REPORT = OUT_DIR / "relatorio_prospec_master.md"
VALIDATION = OUT_DIR / "validation_prospec_master.json"
TEST_COPY = ROOT / "prospeccao-campanella" / "_staging_master" / "index.html"
EXPECTED_RECORDS = 813

CARD_FIELDS = [
    "nome_comercial",
    "segmento",
    "familia_segmento",
    "endereco",
    "telefone",
    "whatsapp_publico",
    "lead_tier",
    "prioridade",
    "score_comercial",
    "status_funil",
    "publicavel_status",
    "nivel_confianca_interno",
]

DETAIL_FIELDS = [
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
    "cardapio_url",
    "nota",
    "num_avaliacoes",
    "cnpj",
    "cnpj_confidence",
    "razao_social",
    "nome_fantasia",
    "situacao_cadastral",
    "cnae",
    "porte",
    "data_abertura",
    "score_digital",
    "score_dor",
    "score_comercial",
    "lead_tier",
    "prioridade",
    "dor_dominante",
    "oferta_recomendada",
    "modulos_recomendados",
    "pitch_presencial",
    "mensagem_whatsapp",
    "acao_recomendada",
    "quality_flags",
    "fontes_json",
]


def load_records() -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not SOURCE.exists():
        return [], [f"Fonte nao encontrada: {SOURCE}"]
    try:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [], [f"Falha ao ler JSON fonte: {exc}"]
    if not isinstance(data, list):
        errors.append("master_prospeccao.json deveria ser uma lista de registros.")
        return [], errors
    records = [r for r in data if isinstance(r, dict)]
    if len(records) != len(data):
        errors.append("Existem itens nao-objeto na lista fonte.")
    return records, errors


def present(value: Any) -> bool:
    return value not in (None, "", [], {})


def confidence_bucket(value: Any) -> str:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0
    if numeric >= 80:
        return "alto"
    if numeric >= 50:
        return "medio"
    if numeric > 0:
        return "baixo"
    return "sem"


def unique_values(records: list[dict[str, Any]], field: str) -> list[str]:
    values = {str(r.get(field, "")).strip() for r in records if str(r.get(field, "")).strip()}
    return sorted(values, key=lambda x: x.casefold())


def build_indicators(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_leads": len(records),
        "leads_a_ou_aplus": sum(1 for r in records if r.get("lead_tier") in {"A+", "A"}),
        "sem_site": sum(1 for r in records if not present(r.get("site_oficial"))),
        "com_whatsapp": sum(1 for r in records if present(r.get("whatsapp_publico")) or present(r.get("whatsapp_prospeccao_url"))),
        "com_cnpj_confirmado_provavel": sum(1 for r in records if present(r.get("cnpj")) and confidence_bucket(r.get("cnpj_confidence")) in {"alto", "medio"}),
        "publicaveis": sum(1 for r in records if str(r.get("publicavel_status", "")).upper() == "PUBLICAVEL"),
        "alta_prioridade": sum(1 for r in records if str(r.get("prioridade", "")).startswith("A") or r.get("lead_tier") in {"A+", "A"}),
        "com_onepage": sum(1 for r in records if present(r.get("onepage_url"))),
        "com_app_claim_url": sum(1 for r in records if present(r.get("app_claim_url"))),
    }


def validate_records(records: list[dict[str, Any]], initial_errors: list[str]) -> tuple[dict[str, Any], list[str], list[str]]:
    errors = list(initial_errors)
    warnings: list[str] = []
    place_ids = [r.get("place_id") for r in records if present(r.get("place_id"))]
    counts = Counter(place_ids)
    duplicated = sorted([pid for pid, count in counts.items() if count > 1])
    missing_place_id = len(records) - len(place_ids)
    missing_onepage = sum(1 for r in records if not present(r.get("onepage_url")))
    missing_claim = sum(1 for r in records if not present(r.get("app_claim_url")))

    if len(records) != EXPECTED_RECORDS:
        errors.append(f"Quantidade esperada {EXPECTED_RECORDS}, encontrada {len(records)}.")
    if missing_place_id:
        errors.append(f"Registros sem place_id: {missing_place_id}.")
    if duplicated:
        errors.append(f"place_id duplicado: {len(duplicated)} valores.")
    if missing_onepage:
        warnings.append(f"Registros sem onepage_url: {missing_onepage}.")
    if missing_claim:
        warnings.append(f"Registros sem app_claim_url: {missing_claim}.")

    internal_fields = ["lead_tier", "prioridade", "score_comercial", "status_funil", "publicavel_status", "nivel_confianca_interno"]
    missing_internal = {field: sum(1 for r in records if field not in r) for field in internal_fields}
    for field, count in missing_internal.items():
        if count:
            warnings.append(f"Campo interno ausente em {count} registros: {field}.")

    if sum(1 for r in records if present(r.get("whatsapp_publico"))) == 0:
        warnings.append("whatsapp_publico esta vazio em todos os registros; o dashboard usa telefone como fallback visual.")
    if sum(1 for r in records if present(r.get("cnpj"))) < len(records) // 2:
        warnings.append("CNPJ preenchido em menos da metade da base.")

    validation = {
        "ok": False,
        "records": len(records),
        "unique_place_ids": len(counts),
        "missing_place_id": missing_place_id,
        "duplicated_place_id": duplicated,
        "missing_onepage_url": missing_onepage,
        "missing_app_claim_url": missing_claim,
        "generated_dashboard": str(DASHBOARD),
        "errors": errors,
        "warnings": warnings,
    }
    return validation, errors, warnings


def json_script(records: list[dict[str, Any]]) -> str:
    raw = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/")


def build_html(records: list[dict[str, Any]], indicators: dict[str, int], generated_at: str) -> str:
    options = {
        "segmentos": unique_values(records, "segmento"),
        "familias": unique_values(records, "familia_segmento"),
        "tiers": unique_values(records, "lead_tier"),
        "prioridades": unique_values(records, "prioridade"),
        "publicavel": unique_values(records, "publicavel_status"),
        "status": unique_values(records, "status_funil"),
        "dores": unique_values(records, "dor_dominante"),
    }
    data_json = json_script(records)
    options_json = json_script([options])[1:-1]
    indicators_json = json_script([indicators])[1:-1]
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prospecção Cliente Inteligente</title>
<style>
:root {{
  --bg:#f6f8fb; --panel:#ffffff; --ink:#172033; --muted:#64748b; --line:#d8e0eb;
  --brand:#0f766e; --brand-dark:#115e59; --warn:#b45309; --danger:#b91c1c;
  --a:#059669; --b:#2563eb; --c:#ca8a04; --d:#64748b;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:var(--bg); color:var(--ink); }}
header {{ position:sticky; top:0; z-index:5; background:#0b1220; color:white; padding:14px 18px; box-shadow:0 2px 12px rgba(15,23,42,.18); }}
.headrow {{ display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap; }}
h1 {{ margin:0; font-size:19px; line-height:1.2; }}
.subtitle {{ margin-top:4px; color:#a7b4c7; font-size:12px; }}
.notice {{ background:#fff7ed; color:#7c2d12; border:1px solid #fed7aa; padding:8px 10px; border-radius:8px; font-size:12px; max-width:620px; }}
.kpis {{ display:grid; grid-template-columns:repeat(9, minmax(104px,1fr)); gap:8px; padding:12px 18px; background:#111827; }}
.kpi {{ background:#1f2937; color:#cbd5e1; border-radius:8px; padding:8px 10px; min-height:58px; }}
.kpi b {{ display:block; color:#fff; font-size:20px; margin-top:3px; }}
.filters {{ padding:10px 18px; background:var(--panel); border-bottom:1px solid var(--line); }}
.filter-main {{ display:grid; grid-template-columns:minmax(260px,2fr) repeat(3,minmax(150px,1fr)); gap:8px; align-items:center; }}
.filter-quick {{ display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)) 120px auto; gap:8px; align-items:center; margin-top:8px; }}
.filter-buttons {{ display:flex; gap:6px; flex-wrap:wrap; }}
.filter-buttons button {{ padding:7px 9px; font-size:12px; }}
.advanced-filters {{ margin-top:8px; border:1px solid var(--line); border-radius:8px; background:#f8fafc; padding:8px 10px; }}
.advanced-filters summary {{ cursor:pointer; font-weight:800; color:#334155; font-size:13px; }}
.advanced-grid {{ display:grid; grid-template-columns:repeat(4,minmax(150px,1fr)); gap:8px; margin-top:8px; }}
input, select, textarea {{ width:100%; border:1px solid var(--line); border-radius:8px; padding:9px 10px; background:#fff; color:var(--ink); font:inherit; }}
textarea {{ min-height:76px; resize:vertical; }}
.layout {{ display:grid; grid-template-columns:minmax(420px, 46%) 1fr; min-height:calc(100vh - 188px); }}
.list {{ border-right:1px solid var(--line); background:#eef3f8; overflow:auto; max-height:calc(100vh - 188px); }}
.detail {{ overflow:auto; max-height:calc(100vh - 188px); background:#fff; }}
.toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 14px; background:#e2e8f0; border-bottom:1px solid var(--line); font-size:13px; color:#475569; position:sticky; top:0; z-index:2; }}
.card {{ background:#fff; border-bottom:1px solid var(--line); padding:13px 14px; cursor:pointer; }}
.card:hover {{ background:#f8fafc; }}
.card.selected {{ box-shadow:inset 4px 0 0 var(--brand); background:#ecfdf5; }}
.cardtop {{ display:grid; grid-template-columns:1fr; gap:6px; align-items:start; }}
.name {{ font-weight:800; line-height:1.25; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:3px 8px; color:#fff; font-size:11px; font-weight:800; white-space:nowrap; max-width:150px; overflow:hidden; text-overflow:ellipsis; }}
.badge.light {{ color:#134e4a; background:#ccfbf1; border:1px solid #99f6e4; }}
.badge.warn {{ color:#854d0e; background:#fef3c7; border:1px solid #fde68a; }}
.badge.ok {{ color:#14532d; background:#dcfce7; border:1px solid #bbf7d0; }}
.tier-Aplus {{ background:#047857; }} .tier-A {{ background:var(--a); }} .tier-B {{ background:var(--b); }} .tier-C {{ background:var(--c); }} .tier-D {{ background:var(--d); }}
.meta {{ margin-top:6px; color:#475569; font-size:12px; display:flex; gap:8px; flex-wrap:wrap; }}
.metarow {{ display:flex; gap:6px; flex-wrap:wrap; }}
.meta span {{ background:#f1f5f9; border:1px solid #e2e8f0; border-radius:999px; padding:2px 7px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.meta .grow {{ flex:1 1 100%; }}
.scoreline {{ margin-top:7px; display:flex; gap:8px; flex-wrap:wrap; font-size:12px; }}
.empty {{ padding:28px; color:var(--muted); text-align:center; }}
.panel {{ padding:18px; }}
.panel h2 {{ margin:0 0 3px; font-size:22px; }}
.panel .sub {{ color:var(--muted); font-size:13px; margin-bottom:12px; }}
.actions {{ display:flex; flex-wrap:wrap; gap:8px; margin:13px 0; }}
button, .btn {{ border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:8px; padding:8px 10px; font-weight:700; cursor:pointer; text-decoration:none; font-size:13px; }}
button.primary, .btn.primary {{ background:var(--brand); border-color:var(--brand); color:white; }}
button:hover, .btn:hover {{ border-color:var(--brand); }}
.section {{ margin:0 0 16px; padding:14px; border:1px solid #e2e8f0; border-radius:10px; background:#fff; }}
.section h3 {{ margin:0 0 10px; font-size:16px; }}
.section details {{ border:1px solid #e2e8f0; border-radius:8px; padding:10px; background:#f8fafc; }}
.section summary {{ cursor:pointer; font-weight:800; color:#334155; }}
.section summary + * {{ margin-top:10px; }}
.grid {{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px; }}
.field {{ border:1px solid #e2e8f0; border-radius:8px; padding:9px 10px; min-width:0; background:#fff; }}
.field.wide {{ grid-column:1 / -1; }}
.label {{ font-size:11px; color:var(--muted); letter-spacing:.02em; font-weight:800; margin-bottom:4px; }}
.value {{ font-size:14px; overflow-wrap:anywhere; white-space:pre-wrap; line-height:1.4; }}
.value a {{ color:var(--brand-dark); }}
.localgrid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
.smallwarn {{ color:#92400e; font-size:12px; margin-top:8px; }}
.copyok {{ color:#047857; font-size:12px; min-height:18px; }}
pre {{ margin:0; white-space:pre-wrap; word-break:break-word; font-size:12px; }}
@media (max-width:1100px) {{
  .kpis {{ grid-template-columns:repeat(3,1fr); }}
  .filter-main {{ grid-template-columns:1fr 1fr; }}
  .filter-quick {{ grid-template-columns:1fr 1fr; }}
  .advanced-grid {{ grid-template-columns:1fr 1fr; }}
}}
@media (max-width:760px) {{
  .layout {{ grid-template-columns:1fr; }}
  .list,.detail {{ max-height:none; }}
  .grid,.localgrid {{ grid-template-columns:1fr; }}
  .filter-main,.filter-quick,.advanced-grid {{ grid-template-columns:1fr; }}
  .filter-buttons {{ display:grid; grid-template-columns:1fr 1fr; }}
}}
</style>
</head>
<body>
<header>
  <div class="headrow">
    <div>
      <h1>Prospecção Cliente Inteligente</h1>
      <div class="subtitle">Cliente Inteligente - fonte oficial: master_prospeccao.json - gerado em {generated_at}</div>
    </div>
    <div class="notice">Ferramenta interna: status e anotações ainda são salvos apenas neste navegador.</div>
  </div>
</header>
<section class="kpis" id="kpis"></section>
<section class="filters">
  <div class="filter-main">
    <input id="busca" type="search" placeholder="Buscar por nome, telefone, endereço ou segmento..." autocomplete="off">
    <select id="f-prioridade">
      <option value="">Prioridade: Todas</option>
      <option value="alta_aplus">Alta / A+</option>
      <option value="a">A</option>
      <option value="b">B</option>
      <option value="cd">C/D</option>
      <option value="sem">Sem prioridade</option>
    </select>
    <select id="f-situacao">
      <option value="">Situação: Todos</option>
      <option value="novo">Novo</option>
      <option value="a_abordar">A abordar</option>
      <option value="em_contato">Em contato</option>
      <option value="interessado">Interessado</option>
      <option value="sem_interesse">Sem interesse</option>
      <option value="convertido">Convertido</option>
      <option value="revisar">Revisar</option>
    </select>
    <select id="f-perfil">
      <option value="">Perfil: Todos</option>
      <option value="quentes">Leads quentes</option>
      <option value="sem_site_contato">Sem site + com telefone/WhatsApp</option>
      <option value="com_dor">Com dor identificada</option>
      <option value="alta_chance">Alta chance comercial</option>
      <option value="baixa_presenca">Baixa presença digital</option>
      <option value="visita">Bom para visita presencial</option>
      <option value="publicavel">Publicável</option>
    </select>
  </div>
  <div class="filter-quick">
    <select id="f-presenca">
      <option value="">Presença digital: Todos</option>
      <option value="sem_site">Sem site</option>
      <option value="com_site">Com site</option>
      <option value="com_instagram">Com Instagram</option>
      <option value="com_cardapio">Com cardápio/delivery</option>
      <option value="baixa_presenca">Baixa presença digital</option>
    </select>
    <select id="f-contato">
      <option value="">Contato: Todos</option>
      <option value="com_telefone">Com telefone</option>
      <option value="sem_telefone">Sem telefone</option>
      <option value="com_whatsapp">Com WhatsApp provável</option>
      <option value="sem_whatsapp">Sem WhatsApp</option>
    </select>
    <select id="f-cnpj">
      <option value="">CNPJ: Todos</option>
      <option value="forte">Com CNPJ forte</option>
      <option value="candidato">Com candidato CNPJ</option>
      <option value="sem">Sem CNPJ</option>
      <option value="revisar">Revisar CNPJ</option>
    </select>
    <input id="f-score" type="number" min="0" max="100" step="1" placeholder="Score mínimo">
    <div class="filter-buttons">
      <button type="button" data-filter-action="clear">Limpar filtros</button>
      <button type="button" data-filter-action="hot">Só leads quentes</button>
      <button type="button" data-filter-action="no_site">Sem site</button>
      <button type="button" data-filter-action="whatsapp">Com WhatsApp</button>
      <button type="button" data-filter-action="visit">Para visitar</button>
    </div>
  </div>
  <details class="advanced-filters">
    <summary>Filtros avançados</summary>
    <div class="advanced-grid">
      <select id="f-segmento"></select>
      <select id="f-familia"></select>
      <select id="f-tier"></select>
      <select id="f-publicavel"></select>
      <select id="f-cnpj-conf"><option value="">Confiança CNPJ: todas</option><option value="alto">Alto</option><option value="medio">Médio</option><option value="baixo">Baixo</option><option value="sem">Sem score</option></select>
      <select id="f-dor-raw"></select>
      <select id="f-status-raw"></select>
    </div>
  </details>
</section>
<main class="layout">
  <section class="list">
    <div class="toolbar"><span id="result-count">0 leads encontrados</span><span></span></div>
    <div id="cards"></div>
  </section>
  <aside class="detail" id="detail"></aside>
</main>
<script id="dados-master" type="application/json">{data_json}</script>
<script>
const DADOS = JSON.parse(document.getElementById('dados-master').textContent);
const OPTIONS = {options_json};
const INDICATORS = {indicators_json};
const LOCAL_FIELDS = ['status_funil_local', 'anotacao_local', 'interesse_local', 'proxima_acao_local'];
let filtered = [];
let selectedPlaceId = DADOS[0]?.place_id || null;

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
const has = value => !(value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0));
const tierClass = tier => 'tier-' + String(tier || 'D').replace('+','plus').replace(/[^A-Za-z0-9]/g,'');
const localKey = placeId => 'ci_prospec_master_local_' + placeId;
const shortAddress = value => String(value || '').split(' - ').slice(0, 2).join(' - ') || value || '';
const sourceLabels = {{publico:'Publico', prospeccao_v3:'Prospecção V3', v5_json:'V5 JSON', v5_csv:'V5 CSV'}};
const norm = value => String(value ?? '').trim().toLowerCase();
const score = value => Number(value || 0);

function cnpjConfidenceBucket(value) {{
  const n = Number(value || 0);
  if (n >= 80) return 'alto';
  if (n >= 50) return 'medio';
  if (n > 0) return 'baixo';
  return 'sem';
}}

function hasWhatsapp(row) {{
  return has(row.whatsapp_publico) || has(row.whatsapp_prospeccao_url) || /sim|true|provavel|provável|yes|1/.test(norm(row.whatsapp_status));
}}

function hasPhone(row) {{
  return has(row.telefone);
}}

function whatsappLabel(row) {{
  if (has(row.whatsapp_publico) || has(row.whatsapp_prospeccao_url)) return 'WhatsApp';
  if (/provavel|provável/i.test(String(row.whatsapp_status || ''))) return 'WhatsApp provável';
  return '';
}}

function hasDominantPain(row) {{
  const dor = String(row.dor_dominante || '').trim();
  const rec = row.reclamacoes || {{}};
  return Boolean(
    (dor && dor !== 'sem_dor_classificada') ||
    score(row.score_dor) > 0 ||
    score(rec.total) > 0 ||
    has(rec.categorias)
  );
}}

function isHighPriority(row) {{
  const pri = norm(row.prioridade);
  return row.lead_tier === 'A+' || row.lead_tier === 'A' || pri.startsWith('a') || pri.includes('alta');
}}

function isHotLead(row) {{
  return isHighPriority(row) || score(row.score_comercial) >= 70;
}}

function lowDigitalPresence(row) {{
  return !has(row.site_oficial) && !has(row.instagram) && !has(row.cardapio_url) && !has(row.delivery_url);
}}

function isPublishable(row) {{
  return norm(row.publicavel_status).includes('publicavel') || norm(row.publicavel_status).includes('publicável');
}}

function cnpjStrong(row) {{
  return has(row.cnpj) && score(row.cnpj_confidence) >= 80;
}}

function cnpjCandidate(row) {{
  const raw = String(row.cnpj_candidates_json || '').trim();
  return !cnpjStrong(row) && (score(row.cnpj_candidate_count) > 0 || (raw && raw !== '[]' && raw !== '{{}}'));
}}

function cnpjReview(row) {{
  const status = norm(row.cnpj_status);
  const conf = score(row.cnpj_confidence);
  return (conf > 0 && conf < 80) || /revisar|fraco|candidato/.test(status);
}}

function statusText(row) {{
  const local = getLocal(row.place_id);
  return norm(local.status_funil_local || row.status_funil);
}}

function matchesPriority(row, value) {{
  if (!value) return true;
  const pri = norm(row.prioridade);
  const tier = norm(row.lead_tier);
  if (value === 'alta_aplus') return tier === 'a+' || pri.includes('a+') || pri.includes('alta');
  if (value === 'a') return tier === 'a' || pri === 'a';
  if (value === 'b') return tier === 'b' || pri === 'b';
  if (value === 'cd') return ['c','d'].includes(tier) || ['c','d'].includes(pri);
  if (value === 'sem') return !has(row.prioridade) && !has(row.lead_tier);
  return true;
}}

function matchesSituation(row, value) {{
  if (!value) return true;
  const st = statusText(row);
  if (value === 'novo') return st === 'novo';
  if (value === 'a_abordar') return /abord/.test(st);
  if (value === 'em_contato') return /contato|contatado/.test(st);
  if (value === 'interessado') return /interess/.test(st) && !/sem/.test(st);
  if (value === 'sem_interesse') return /sem.*interesse|desinteress/.test(st);
  if (value === 'convertido') return /convert|cliente|fechado/.test(st);
  if (value === 'revisar') return /revisar|revisao|revisão/.test(st) || norm(row.publicavel_status).includes('revisar');
  return true;
}}

function matchesProfile(row, value) {{
  if (!value) return true;
  if (value === 'quentes') return isHotLead(row);
  if (value === 'sem_site_contato') return !has(row.site_oficial) && (hasPhone(row) || hasWhatsapp(row));
  if (value === 'com_dor') return hasDominantPain(row);
  if (value === 'alta_chance') return score(row.score_comercial) >= 70 || row.lead_tier === 'A+' || row.lead_tier === 'A';
  if (value === 'baixa_presenca') return lowDigitalPresence(row);
  if (value === 'visita') return has(row.endereco) && !matchesSituation(row, 'convertido') && ['A+','A','B'].includes(String(row.lead_tier || row.prioridade || '')) && score(row.score_comercial) >= 50;
  if (value === 'publicavel') return isPublishable(row);
  return true;
}}

function matchesPresence(row, value) {{
  if (!value) return true;
  if (value === 'sem_site') return !has(row.site_oficial);
  if (value === 'com_site') return has(row.site_oficial);
  if (value === 'com_instagram') return has(row.instagram);
  if (value === 'com_cardapio') return has(row.cardapio_url) || has(row.delivery_url);
  if (value === 'baixa_presenca') return lowDigitalPresence(row);
  return true;
}}

function matchesContact(row, value) {{
  if (!value) return true;
  if (value === 'com_telefone') return hasPhone(row);
  if (value === 'sem_telefone') return !hasPhone(row);
  if (value === 'com_whatsapp') return hasWhatsapp(row);
  if (value === 'sem_whatsapp') return !hasWhatsapp(row);
  return true;
}}

function matchesCnpj(row, value) {{
  if (!value) return true;
  if (value === 'forte') return cnpjStrong(row);
  if (value === 'candidato') return cnpjCandidate(row);
  if (value === 'sem') return !has(row.cnpj);
  if (value === 'revisar') return cnpjReview(row);
  return true;
}}

function optionList(select, label, values) {{
  select.innerHTML = `<option value="">${{label}}</option>` + values.map(v => `<option value="${{esc(v)}}">${{esc(v)}}</option>`).join('');
}}

function initFilters() {{
  optionList($('f-segmento'), 'Segmento: todos', OPTIONS.segmentos);
  optionList($('f-familia'), 'Família de segmento: todas', OPTIONS.familias);
  optionList($('f-tier'), 'Lead tier: todos', OPTIONS.tiers);
  optionList($('f-publicavel'), 'Publicável: todos', OPTIONS.publicavel);
  optionList($('f-dor-raw'), 'Dor dominante: todas', OPTIONS.dores);
  optionList($('f-status-raw'), 'Status funil bruto: todos', OPTIONS.status);
  document.querySelectorAll('input,select').forEach(el => el.addEventListener('input', render));
  document.querySelectorAll('[data-filter-action]').forEach(btn => btn.addEventListener('click', () => applyQuickFilter(btn.dataset.filterAction)));
}}

function resetFilters() {{
  document.querySelectorAll('.filters input,.filters select').forEach(el => el.value = '');
}}

function applyQuickFilter(action) {{
  resetFilters();
  if (action === 'hot') $('f-perfil').value = 'quentes';
  if (action === 'no_site') $('f-presenca').value = 'sem_site';
  if (action === 'whatsapp') $('f-contato').value = 'com_whatsapp';
  if (action === 'visit') $('f-perfil').value = 'visita';
  render();
}}

function renderKpis() {{
  const labels = [
    ['total_leads', 'total de leads'],
    ['leads_a_ou_aplus', 'leads A+/A'],
    ['sem_site', 'sem site'],
    ['com_whatsapp', 'com WhatsApp'],
    ['com_cnpj_confirmado_provavel', 'CNPJ confirmado/provavel'],
    ['publicaveis', 'publicaveis'],
    ['alta_prioridade', 'alta prioridade'],
    ['com_onepage', 'com One Page'],
    ['com_app_claim_url', 'com App Claim URL'],
  ];
  $('kpis').innerHTML = labels.map(([key, label]) => `<div class="kpi">${{esc(label)}}<b>${{INDICATORS[key] ?? 0}}</b></div>`).join('');
}}

function matches(row) {{
  const q = $('busca').value.trim().toLowerCase();
  if (q) {{
    const haystack = [
      row.nome_comercial,
      row.telefone,
      row.endereco,
      row.segmento,
      row.familia_segmento,
      row.place_id,
    ].map(norm).join(' ');
    if (!haystack.includes(q)) return false;
  }}
  if (!matchesPriority(row, $('f-prioridade').value)) return false;
  if (!matchesSituation(row, $('f-situacao').value)) return false;
  if (!matchesProfile(row, $('f-perfil').value)) return false;
  if (!matchesPresence(row, $('f-presenca').value)) return false;
  if (!matchesContact(row, $('f-contato').value)) return false;
  if (!matchesCnpj(row, $('f-cnpj').value)) return false;
  if ($('f-segmento').value && row.segmento !== $('f-segmento').value) return false;
  if ($('f-familia').value && row.familia_segmento !== $('f-familia').value) return false;
  if ($('f-tier').value && row.lead_tier !== $('f-tier').value) return false;
  if ($('f-publicavel').value && row.publicavel_status !== $('f-publicavel').value) return false;
  if ($('f-status-raw').value && row.status_funil !== $('f-status-raw').value) return false;
  if ($('f-dor-raw').value && row.dor_dominante !== $('f-dor-raw').value) return false;
  if ($('f-cnpj-conf').value && cnpjConfidenceBucket(row.cnpj_confidence) !== $('f-cnpj-conf').value) return false;
  const minScore = Number($('f-score').value);
  if (Number.isFinite(minScore) && $('f-score').value !== '' && Number(row.score_comercial || 0) < minScore) return false;
  return true;
}}

function card(row) {{
  const selected = row.place_id === selectedPlaceId ? ' selected' : '';
  const phone = row.telefone || 'sem telefone';
  const wa = whatsappLabel(row);
  return `<article class="card${{selected}}" data-id="${{esc(row.place_id)}}">
    <div class="cardtop">
      <div class="name" title="${{esc(row.nome_comercial)}}">${{esc(row.nome_comercial)}}</div>
      <div class="metarow">
        <span class="badge ${{tierClass(row.lead_tier)}}">${{esc(row.lead_tier || '-')}}</span>
        <span class="badge light">${{esc(row.prioridade || '-')}}</span>
        ${{wa ? `<span class="badge ok">${{esc(wa)}}</span>` : ''}}
        <span class="badge warn">${{esc(row.publicavel_status || '-')}}</span>
      </div>
    </div>
    <div class="meta">
      <span>${{esc(row.segmento || 'sem segmento')}}</span>
      <span>${{esc(row.familia_segmento || 'sem familia')}}</span>
      <span>${{esc(phone)}}</span>
    </div>
    <div class="meta"><span class="grow" title="${{esc(row.endereco || '')}}">${{esc(shortAddress(row.endereco) || 'sem endereco')}}</span></div>
    <div class="scoreline">
      <b>Score:</b> ${{esc(row.score_comercial ?? '-')}}
      <b>Status:</b> ${{esc(row.status_funil || '-')}}
    </div>
  </article>`;
}}

function getLocal(placeId) {{
  try {{ return JSON.parse(localStorage.getItem(localKey(placeId)) || '{{}}'); }}
  catch (err) {{ return {{}}; }}
}}

function saveLocal(placeId) {{
  const payload = {{
    status_funil_local: $('status_funil_local').value,
    anotacao_local: $('anotacao_local').value,
    interesse_local: $('interesse_local').value,
    proxima_acao_local: $('proxima_acao_local').value,
    updated_at_local: new Date().toISOString(),
  }};
  localStorage.setItem(localKey(placeId), JSON.stringify(payload));
  $('copy-state').textContent = 'dados locais salvos';
  setTimeout(() => $('copy-state').textContent = '', 1600);
}}

function formatValue(value) {{
  if (Array.isArray(value)) return value.length ? value.join(', ') : '';
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return value ?? '';
}}

function displaySourceNames(fontes) {{
  if (!fontes || typeof fontes !== 'object') return '-';
  const keys = Object.keys(fontes).filter(k => k !== 'v5_csv');
  return keys.length ? keys.map(k => sourceLabels[k] || k).join(', ') : '-';
}}

function linkButton(url, label, primary=false) {{
  return has(url) ? `<a class="btn${{primary ? ' primary' : ''}}" href="${{esc(url)}}" target="_blank" rel="noopener">${{esc(label)}}</a>` : '';
}}

function valueField(label, value, wide=false) {{
  return `<div class="field${{wide ? ' wide' : ''}}"><div class="label">${{esc(label)}}</div><div class="value">${{esc(formatValue(value) || '-')}}</div></div>`;
}}

function urlField(label, url, buttonLabel) {{
  return `<div class="field"><div class="label">${{esc(label)}}</div><div class="value">${{has(url) ? `<a class="btn" href="${{esc(url)}}" target="_blank" rel="noopener">${{esc(buttonLabel)}}</a>` : '-'}}</div></div>`;
}}

function section(title, fields) {{
  return `<section class="section"><h3>${{esc(title)}}</h3><div class="grid">${{fields.join('')}}</div></section>`;
}}

async function copyText(text, label) {{
  try {{
    await navigator.clipboard.writeText(text || '');
    $('copy-state').textContent = label + ' copiado';
  }} catch (err) {{
    $('copy-state').textContent = 'nao foi possivel copiar automaticamente';
  }}
  setTimeout(() => $('copy-state').textContent = '', 1800);
}}

function detail(row) {{
  if (!row) {{
    $('detail').innerHTML = '<div class="empty">Selecione um lead.</div>';
    return;
  }}
  const local = getLocal(row.place_id);
  const jsonLead = JSON.stringify(row, null, 2);
  const waUrl = row.whatsapp_prospeccao_url || row.whatsapp_publico || '';
  const resumo = [
    valueField('Nome', row.nome_comercial),
    valueField('Segmento', row.segmento),
    valueField('Endereço', row.endereco, true),
    valueField('Telefone', row.telefone),
    valueField('Status funil', row.status_funil),
    valueField('Prioridade', row.prioridade),
    valueField('Lead tier', row.lead_tier),
    valueField('Score comercial', row.score_comercial),
  ];
  const abordagem = [
    valueField('Dor dominante', row.dor_dominante),
    valueField('Oferta recomendada', row.oferta_recomendada),
    valueField('Módulos recomendados', row.modulos_recomendados, true),
    valueField('Pitch presencial', row.pitch_presencial, true),
    valueField('Mensagem WhatsApp', row.mensagem_whatsapp, true),
    valueField('Ação recomendada', row.acao_recomendada, true),
  ];
  const presenca = [
    urlField('Site oficial', row.site_oficial, 'Abrir site'),
    urlField('Instagram', row.instagram, 'Abrir Instagram'),
    urlField('Cardápio/delivery', row.cardapio_url || row.delivery_url, 'Abrir cardápio/delivery'),
    urlField('WhatsApp', waUrl, 'Abrir WhatsApp'),
    valueField('Nota', row.nota),
    valueField('Avaliações', row.num_avaliacoes),
  ];
  const legais = [
    valueField('CNPJ', row.cnpj),
    valueField('Confiança CNPJ', row.cnpj_confidence),
    valueField('Status CNPJ', row.cnpj_status),
    valueField('Razão social', row.razao_social),
    valueField('Nome fantasia', row.nome_fantasia),
    valueField('CNAE', row.cnae),
    valueField('Porte', row.porte),
    valueField('Data de abertura', row.data_abertura),
  ];
  $('detail').innerHTML = `<div class="panel">
    <h2>${{esc(row.nome_comercial)}}</h2>
    <div class="sub">${{esc(row.segmento || '-')}} · ${{esc(row.familia_segmento || '-')}}</div>
    ${{section('Resumo', resumo)}}
    <section class="section">
      <h3>Ações rápidas</h3>
      <div class="actions">
      ${{linkButton(row.maps_url, 'Abrir Maps', true)}}
      ${{linkButton(row.onepage_url, 'Abrir One Page')}}
      ${{linkButton(row.app_claim_url, 'Abrir App Claim')}}
      ${{linkButton(waUrl, 'Abrir WhatsApp')}}
      <button type="button" data-copy="pitch">Copiar pitch presencial</button>
      <button type="button" data-copy="whatsapp">Copiar mensagem WhatsApp</button>
      <button type="button" data-copy="json">Copiar JSON técnico</button>
      </div>
      <div id="copy-state" class="copyok"></div>
    </section>
    ${{section('Abordagem comercial', abordagem)}}
    ${{section('Presença digital', presenca)}}
    ${{section('Dados legais internos', legais)}}
    <section class="section">
      <h3>Anotações de campo</h3>
      <div class="localgrid">
        <div><div class="label">Status local</div><input id="status_funil_local" value="${{esc(local.status_funil_local || '')}}" placeholder="ex.: contatado"></div>
        <div><div class="label">Interesse local</div><input id="interesse_local" value="${{esc(local.interesse_local || '')}}" placeholder="ex.: alto / médio / baixo"></div>
        <div><div class="label">Próxima ação local</div><input id="proxima_acao_local" value="${{esc(local.proxima_acao_local || '')}}" placeholder="ex.: visitar sexta"></div>
        <div><div class="label">Anotação local</div><textarea id="anotacao_local" placeholder="Anotações locais">${{esc(local.anotacao_local || '')}}</textarea></div>
      </div>
      <button type="button" class="primary" id="save-local">Salvar localStorage</button>
      <div class="smallwarn">Salvo apenas neste navegador. Chave localStorage: ${{esc(localKey(row.place_id))}}</div>
    </section>
    <section class="section">
      <details>
        <summary>Dados técnicos</summary>
        <div class="grid">
          ${{valueField('place_id', row.place_id)}}
          ${{valueField('slug público', row.slug_publico)}}
          ${{valueField('Alertas de qualidade', row.quality_flags, true)}}
          ${{valueField('Fontes técnicas', displaySourceNames(row.fontes_json), true)}}
          <div class="field wide"><div class="label">JSON completo</div><pre class="value">${{esc(jsonLead)}}</pre></div>
        </div>
      </details>
    </section>
  </div>`;
  $('save-local').addEventListener('click', () => saveLocal(row.place_id));
  document.querySelector('[data-copy="pitch"]').addEventListener('click', () => copyText(row.pitch_presencial || '', 'pitch presencial'));
  document.querySelector('[data-copy="whatsapp"]').addEventListener('click', () => copyText(row.mensagem_whatsapp || '', 'mensagem WhatsApp'));
  document.querySelector('[data-copy="json"]').addEventListener('click', () => copyText(jsonLead, 'JSON técnico'));
}}

function render() {{
  filtered = DADOS.filter(matches);
  $('result-count').textContent = filtered.length === DADOS.length
    ? `${{DADOS.length}} leads encontrados`
    : `${{filtered.length}} de ${{DADOS.length}} leads encontrados`;
  if (!filtered.some(row => row.place_id === selectedPlaceId)) selectedPlaceId = filtered[0]?.place_id || null;
  $('cards').innerHTML = filtered.length ? filtered.map(card).join('') : '<div class="empty">Nenhum lead encontrado com os filtros atuais.</div>';
  document.querySelectorAll('.card').forEach(el => el.addEventListener('click', () => {{
    selectedPlaceId = el.dataset.id;
    render();
  }}));
  detail(DADOS.find(row => row.place_id === selectedPlaceId));
}}

initFilters();
renderKpis();
render();
</script>
</body>
</html>
"""


def coarse_js_check(html: str) -> list[str]:
    errors: list[str] = []
    scripts = re.findall(r"<script(?![^>]*type=\"application/json\")[^>]*>(.*?)</script>", html, flags=re.S | re.I)
    if not scripts:
        return ["Nenhum bloco JavaScript executavel encontrado."]
    script = "\n".join(scripts)
    pairs = [("(", ")"), ("[", "]"), ("{", "}")]
    for opener, closer in pairs:
        if script.count(opener) != script.count(closer):
            errors.append(f"Possivel erro de sintaxe JS: contagem de {opener}{closer} nao confere.")
    if "const DADOS" not in script or "function render" not in script:
        errors.append("JS embutido nao contem inicializacao esperada.")
    return errors


def validate_dashboard_record_count(html: str) -> bool:
    match = re.search(r'<script id="dados-master" type="application/json">(.*?)</script>', html, flags=re.S)
    if not match:
        return False
    try:
        embedded = json.loads(match.group(1))
    except json.JSONDecodeError:
        return False
    return isinstance(embedded, list) and len(embedded) == EXPECTED_RECORDS


def write_report(records: list[dict[str, Any]], indicators: dict[str, int], warnings: list[str], errors: list[str], generated_at: str) -> None:
    fields_found = sorted({key for row in records for key in row})
    lines = [
        "# Relatorio Prospec Master Staging",
        "",
        f"- Data/hora: {generated_at}",
        f"- Fonte usada: `{SOURCE}`",
        f"- Registros carregados: {len(records)}",
        f"- Chave oficial: `place_id`",
        f"- Dashboard gerado: `{DASHBOARD}`",
        f"- Copia de teste: `{TEST_COPY}`",
        "",
        "## Melhorias de UI aplicadas",
        "",
        "- Cards mostram apenas dados de campo e badges, sem URL crua de WhatsApp.",
        "- Ficha lateral organizada em Resumo, Acoes rapidas, Abordagem comercial, Presenca digital, Dados legais internos, Anotacoes de campo e Dados tecnicos.",
        "- Dados tecnicos ficam recolhidos por padrao em `<details>`.",
        "- Fontes tecnicas visuais exibem nomes logicos em vez de caminhos absolutos.",
        "- Labels tecnicos foram substituidos por nomes amigaveis.",
        "- Filtros principais foram unificados em busca, prioridade, situacao e perfil.",
        "- Segmento, familia, lead tier e filtros brutos foram movidos para Filtros avancados recolhidos por padrao.",
        "- Botoes rapidos aplicam combinacoes operacionais: leads quentes, sem site, com WhatsApp e para visitar.",
        "",
        "## Campos principais encontrados",
        "",
        ", ".join(f"`{field}`" for field in fields_found),
        "",
        "## Indicadores",
        "",
    ]
    for key, value in indicators.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Problemas encontrados", ""])
    if errors:
        lines.extend(f"- ERRO: {err}" for err in errors)
    if warnings:
        lines.extend(f"- ALERTA: {warning}" for warning in warnings)
    if not errors and not warnings:
        lines.append("- Nenhum problema encontrado.")
    lines.extend(
        [
            "",
            "## Limitacoes",
            "",
            "- Versao staging interna; nao foi publicada em producao.",
            "- Status, anotacao, interesse e proxima acao usam localStorage por `place_id`.",
            "- Essa persistencia local ainda nao e oficial e nao sincroniza entre navegadores/dispositivos.",
            "- Dados internos sao exibidos somente neste dashboard staging; nada foi copiado para pastas publicas das One Pages.",
            "",
            "## Proximo passo recomendado",
            "",
            "- Revisar `/root/wins_agro_v1/staging/prospec-master/dashboard.html` no navegador e validar o fluxo operacional antes de decidir qualquer publicacao.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    records, initial_errors = load_records()
    validation, errors, warnings = validate_records(records, initial_errors)
    indicators = build_indicators(records)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(records, indicators, generated_at)
    DASHBOARD.write_text(html, encoding="utf-8")
    TEST_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DASHBOARD, TEST_COPY)

    if not validate_dashboard_record_count(html):
        errors.append("Dashboard gerado nao contem 813 registros embutidos validos.")
    errors.extend(coarse_js_check(html))
    validation["errors"] = errors
    validation["warnings"] = warnings
    validation["ok"] = not errors
    validation["generated_dashboard"] = str(DASHBOARD)
    VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(records, indicators, warnings, errors, generated_at)

    print(f"Fonte: {SOURCE}")
    print(f"Registros carregados: {len(records)}")
    print(f"Dashboard: {DASHBOARD}")
    print(f"Copia teste: {TEST_COPY}")
    print(f"Relatorio: {REPORT}")
    print(f"Validacao: {VALIDATION}")
    print(f"OK: {validation['ok']}")
    if warnings:
        print("Alertas:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("Erros:")
        for error in errors:
            print(f"- {error}")
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
