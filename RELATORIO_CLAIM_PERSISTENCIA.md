# Relatório Claim Persistência

- data_hora: 2026-07-08T16:54:00+00:00
- backups criados: `/root/wins_agro_v1/backups_claim_persist_20260708_165354/`
- escopo: persistência do claim por `place_id` no backend e sincronização do front do app

## Schema antes

- `contas`
  - `id TEXT PRIMARY KEY`
  - `fone TEXT UNIQUE`
  - `slug TEXT UNIQUE`
  - `salt TEXT`
  - `pass_hash TEXT`
  - `criado TEXT`
  - `rec_hash TEXT`
  - `rec_wrap TEXT`
  - `backup_ver INTEGER DEFAULT 0`
- `sessions`
  - `token TEXT PRIMARY KEY`
  - `conta_id TEXT`
  - `criado TEXT`
  - `expira TEXT`

## Schema depois

- nova tabela `estabelecimento_claims`
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `conta_id TEXT NOT NULL`
  - `place_id TEXT NOT NULL`
  - `claim_slug TEXT`
  - `nome_comercial TEXT`
  - `segmento TEXT`
  - `telefone TEXT`
  - `endereco TEXT`
  - `status TEXT DEFAULT 'claimed'`
  - `origem TEXT DEFAULT 'onepage_claim'`
  - `created_at TEXT`
  - `updated_at TEXT`
  - `UNIQUE(conta_id, place_id)`

## Endpoints adicionados

- `POST /api/claim-estabelecimento`
- `GET /api/me/claims`
- `GET /api/claim-estabelecimento/health`

## Campos seguros salvos

- `place_id`
- `claim_slug`
- `nome_comercial`
- `segmento`
- `telefone`
- `endereco`
- `status`
- `origem`
- `created_at`
- `updated_at`

## Campos proibidos nao salvos

- `cnpj`
- `score`
- `lead_tier`
- `tier`
- `prioridade`
- `dor`
- `reclamacoes`
- `pitch`
- `confidence`
- `fontes_json`

## Validacoes executadas

- `python3 -m py_compile /root/wins_agro_v1/ci-api/app.py`
- `python3 -m py_compile /root/wins_agro_v1/scripts/validar_claim_persistencia.py`
- `python3 /root/wins_agro_v1/scripts/validar_claim_seed_publico.py`
- `python3 /root/wins_agro_v1/scripts/validar_cliente_inteligente_publico.py`
- `python3 /root/wins_agro_v1/scripts/validar_claim_persistencia.py`
- `node --check /tmp/ci_claim_persist.js`

## Estado do backend

- a tabela existe no `ci.db`
- a allowlist do claim seed continua segura
- o payload do claim persistente foi limitado aos campos publicos permitidos

## Restart / rebuild

- precisa reiniciar/rebuildar somente `ci-api` para que os endpoints novos entrem em producao no container atual
- o teste `curl http://127.0.0.1:8000/api/claim-estabelecimento/health` nao respondeu neste ambiente porque nao ha servico escutando em `127.0.0.1:8000` aqui

## Proximos passos

- reiniciar/rebuildar apenas `ci-api`
- testar `POST /api/claim-estabelecimento` com uma conta autenticada
- testar `GET /api/me/claims`
- decidir quando a Prospecção interna passa a ler a tabela `estabelecimento_claims`
