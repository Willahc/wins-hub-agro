#!/usr/bin/env python3
"""Valida a persistencia do claim no Cliente Inteligente."""
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'ci-data' / 'ci.db'
API_PATH = ROOT / 'ci-api' / 'app.py'

EXPECTED_TABLE = 'estabelecimento_claims'
EXPECTED_COLUMNS = {
    'id', 'conta_id', 'place_id', 'claim_slug', 'nome_comercial', 'segmento', 'telefone',
    'endereco', 'status', 'origem', 'created_at', 'updated_at'
}
FORBIDDEN_COLUMNS = {
    'cnpj', 'score', 'lead_tier', 'tier', 'prioridade', 'dor', 'reclamacoes', 'pitch',
    'confidence', 'fontes_json', 'razao_social', 'nome_fantasia', 'legal_risk',
    'nivel_confianca_interno', 'mensagem_whatsapp', 'pitch_presencial', 'dor_dominante'
}
SAFE_CLAIM_REQUIRED = {
    'place_id', 'slug_app', 'nome_comercial', 'segmento', 'familia_segmento', 'telefone',
    'endereco', 'latitude', 'longitude', 'modulos_recomendados', 'oferta_recomendada',
    'app_claim_url', 'seed_config'
}


def fail(msg: str) -> None:
    print(f'ERRO: {msg}', file=sys.stderr)
    raise SystemExit(1)


def inspect_db() -> None:
    if not DB_PATH.exists():
        fail(f'BD nao encontrado: {DB_PATH}')
    con = sqlite3.connect(DB_PATH)
    try:
        tables = {row[0]: row[1] for row in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")}
        if EXPECTED_TABLE not in tables:
            fail(f'tabela {EXPECTED_TABLE} nao existe')
        info = list(con.execute(f'PRAGMA table_info({EXPECTED_TABLE})'))
        cols = {row[1] for row in info}
        missing = sorted(EXPECTED_COLUMNS - cols)
        if missing:
            fail(f'tabela {EXPECTED_TABLE} sem colunas esperadas: {", ".join(missing)}')
        leaked = sorted(cols & FORBIDDEN_COLUMNS)
        if leaked:
            fail(f'tabela {EXPECTED_TABLE} contem colunas proibidas: {", ".join(leaked)}')

        index_list = list(con.execute(f'PRAGMA index_list({EXPECTED_TABLE})'))
        unique_ok = False
        for _, idx_name, is_unique, *_ in index_list:
            if not is_unique:
                continue
            idx_cols = [r[2] for r in con.execute(f'PRAGMA index_info({idx_name})')]
            if idx_cols == ['conta_id', 'place_id']:
                unique_ok = True
                break
        if not unique_ok:
            fail('UNIQUE(conta_id, place_id) nao encontrado em estabelecimento_claims')

        count = con.execute(f'SELECT COUNT(*) FROM {EXPECTED_TABLE}').fetchone()[0]
        print(f'OK BD: tabela {EXPECTED_TABLE} existe, {count} registros, UNIQUE conta_id/place_id valido')
        print(f'OK BD schema: {", ".join(sorted(cols))}')
    finally:
        con.close()


def _extract_literal_tuple(tree: ast.AST, name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = node.value
                    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                        out = set()
                        for elt in value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                out.add(elt.value)
                        return out
                    fail(f'{name} nao e colecao literal de strings')
    fail(f'{name} nao encontrado em app.py')


def inspect_api() -> None:
    if not API_PATH.exists():
        fail(f'app.py nao encontrado: {API_PATH}')
    src = API_PATH.read_text(encoding='utf-8')
    tree = ast.parse(src)
    safe_fields = _extract_literal_tuple(tree, 'SAFE_CLAIM_FIELDS')
    required_missing = sorted(SAFE_CLAIM_REQUIRED - safe_fields)
    if required_missing:
        fail(f'SAFE_CLAIM_FIELDS sem campos obrigatorios: {", ".join(required_missing)}')
    leaked = sorted(safe_fields & FORBIDDEN_COLUMNS)
    if leaked:
        fail(f'SAFE_CLAIM_FIELDS contem campos proibidos: {", ".join(leaked)}')

    needles = [
        '/api/claim-estabelecimento',
        '/api/me/claims',
        '/api/claim-estabelecimento/health',
        'estabelecimento_claims',
    ]
    missing = [n for n in needles if n not in src]
    if missing:
        fail(f'app.py sem referencia aos endpoints/tabela: {", ".join(missing)}')
    print('OK API: endpoints de claim persistente presentes e allowlist segura')


def main() -> None:
    inspect_db()
    inspect_api()
    print('OK validação claim persistencia')


if __name__ == '__main__':
    main()
