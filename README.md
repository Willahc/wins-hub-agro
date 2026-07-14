# WiNS Hub Agro

Plataforma de **inteligência genética e comercial bovina**: catálogo genético (DEPs/sumários),
prospecção de demanda, preço de sêmen e valor econômico em reais — tudo num painel só.

## Stack

- **Backend:** FastAPI (Python 3.11) + Postgres 16
- **Frontend:** SPA single-file (Alpine.js + Leaflet + Chart.js), self-hosted (sem CDN) — **PWA instalável**
- **Infra:** nginx (TLS Let's Encrypt) + certbot, orquestrado por Docker Compose

## Funcionalidades

- **Matching genético** — rankeia reprodutores por adequação + custo, com **valor agregado em R$**
  (corte: R$/bezerro · leite: R$/lactação por filha)
- **Arbitragem** (melhor R$/IQGg) e **Rankings** de centrais/fazendas
- **Demanda & Expansão** — rebanho em crescimento (PPM/IBGE), pasto ocioso (lotação), grandes grupos B2B
- **Território** — relatório de prospecção por UF + export PDF executivo
- **Mapa** (Leaflet) — rebanho, crescimento, pasto ocioso, leite, valor
- **Mercado** — indicadores ao vivo (boi gordo, leite, milho, soja via ESALQ/B3; dólar/Selic via BCB)
- **Marketplace / Leads** — criadores rurais (base CNPJ) com export CSV

## Estrutura

```
app/            # FastAPI: main.py (rotas), auth.py, external_apis.py, pdf_generator.py
  frontend/     # index.html (SPA), login.html, vendor/ (libs self-hosted), manifest/sw (PWA)
scripts/        # ingestão de dados (Geneplus, sumários, preços CRV/ABS)
nginx/          # config nginx (montada em conf.d/default.conf)
certbot/        # ACME/TLS (conteúdo sensível fora do git)
docker-compose.yml
```

## Configuração

Copie `.env.example` para `.env` e preencha os valores (segredos **não** vão para o git):

```bash
cp .env.example .env
# gere os segredos:
python -c "import secrets; print(secrets.token_urlsafe(48))"            # SECRET_KEY
python -c "import bcrypt; print(bcrypt.hashpw(b'SUA_SENHA', bcrypt.gensalt()).decode())"  # MARI_PASSWORD_HASH
```

## Rodar

```bash
docker-compose up -d --build
# app em https://<seu-domínio> (nginx) — porta 8000 da API só interna
```

> O Postgres é exposto apenas em `127.0.0.1`. Toda rota `/api/*` exige sessão autenticada.

## Módulos de alimentação

- Autonomia Alimentar — simulações de oferta e demanda.
- Pasto Vivo — biomassa e eventos de pastejo.
- Silagem e Estoques — estruturas, lotes e ledger.
- Colheita e Silos — planejamento, capacidade e conversão do resultado em lotes (`docs/colheita_silos/`).
- Clima e Operações — previsão do tempo, janelas operacionais, integrações com Pasto Vivo e Colheita (`docs/clima_operacoes/`).

## Segurança

- Segredos só via `.env` (gitignored) — nenhuma credencial hardcoded no código
- HSTS, CSP, X-Frame-Options, TLS 1.2/1.3, cookie `Secure/HttpOnly/SameSite`
