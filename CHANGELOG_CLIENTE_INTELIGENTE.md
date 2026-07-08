# Changelog Cliente Inteligente

Todas as mudancas relevantes do ecossistema Cliente Inteligente devem ser registradas aqui.

## 2026-07-08

### Painel Administrativo de Claims

- Criada página admin em `/admin-claims.html` para listar e moderar claims.
- Adicionados endpoints admin protegidos por token:
  - `GET /api/admin/claims` — lista claims com filtros (status, busca)
  - `PATCH /api/admin/claims/{id}` — atualiza status de um claim
  - `GET /api/admin/claims/health` — health check do admin
- Token admin gerado automaticamente e salvo em `/root/wins_agro_v1/ci-data/admin_token.txt`
- Colunas adicionadas na tabela `estabelecimento_claims`: `admin_note`, `verified_at`, `rejected_at`
- Validação de schema idempotente (não quebra dados existentes)
- Criado validador `scripts/validar_admin_claims.py`
- Relatório completo: `RELATORIO_ADMIN_CLAIMS.md`
- Status permitidos: pending_verification, claimed, verified, rejected
- Dados expostos apenas campos seguros; CNPJ, score, tier, prioridade, dor, reclamacoes, pitch, confidence, fontes_json permanecem protegidos
- **Precisa restart do container ci-api para carregar novas rotas**

### Claim persistente por place_id

- Adicionado `estabelecimento_claims` no `ci.db` para vinculo conta <-> estabelecimento.
- Criados os endpoints:
  - `POST /api/claim-estabelecimento`
  - `GET /api/me/claims`
  - `GET /api/claim-estabelecimento/health`
- O App agora tenta persistir o claim quando a conta autentica, mantendo o claim local ate o login.
- Mantida a seguranca: o payload do claim continua sem CNPJ, score, tier, prioridade, dor, reclamacoes, pitch ou confidence interno.
- Atualizada a documentacao do fluxo de 3 camadas para refletir o claim operacional.
- Observacao: ainda nao existe verificacao manual/documental do responsavel; o status inicial do claim e `claimed`.

## 2026-07-07

### Auditoria de fluxo e documentacao de integracao

- Criada auditoria de fluxo entre One Pages, App comerciante, Prospecção interna e `ci-api`.
- Veredito documentado: **parcialmente integrado**.
- Confirmada correspondencia **813/813** entre One Pages e Prospecção por `place_id` extraido de `maps_url`.
- Registrado que as tres camadas compartilham a mesma base historica, mas ainda nao possuem integracao operacional.
- Separacao publico/interno validada na camada publica.
- Proximo passo recomendado: construir a Base Mestre e gerar `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
- Criados documentos:
  - `docs/FLUXO_DADOS_3_CAMADAS.md`
  - `docs/CONTRATO_BASE_MESTRE.md`
  - `docs/PLANO_INTEGRACAO_CAMADAS.md`

### Documentacao

- Criados documentos dedicados ao Cliente Inteligente:
  - `README_CLIENTE_INTELIGENTE.md`
  - `docs/OPERACAO_CLIENTE_INTELIGENTE.md`
  - `docs/ARQUITETURA_CLIENTE_INTELIGENTE.md`
  - `docs/SEGURANCA_DADOS_PUBLICOS.md`
- Documentadas pastas de producao, staging/teste, regras de dados publicos/internos, validador publico e operacao segura do V5.

### Correcao anterior registrada

Backup usado antes das correcoes:

```text
/root/wins_agro_v1/backups_codex_20260707_1155
```

Mudancas feitas na ultima rodada de correcao:

- One Pages publicas:
  - removidos campos internos `tier`, `prioridade` e `score` do JSON publico;
  - removidos os mesmos campos do dataset embutido no indice;
  - removidas caixas "Score interno" das paginas individuais;
  - ajustado `assets/index.js` para nao renderizar classificacao interna mesmo se um dataset antigo voltar com esses campos.
- Prospecção:
  - `dashboard.html` foi regenerado por `gerar_dashboard.py`;
  - removido fallback emergencial `CI_FALLBACK_RENDER_PROSPEC` do HTML gerado;
  - corrigida interpolacao JavaScript no bloco de enriquecimento;
  - mantida a ficha de captacao no dashboard oficial.
- Segurança de dados:
  - criado `scripts/validar_cliente_inteligente_publico.py` para bloquear vazamento de dados internos em artefatos publicos.

### Validacoes executadas na rodada anterior

```bash
python3 scripts/validar_cliente_inteligente_publico.py
python3 -m py_compile /root/wins_agro_v1/prospeccao-campanella/gerar_dashboard.py /root/wins_agro_v1/scripts/validar_cliente_inteligente_publico.py /root/wins_agro_v1/ci-api/app.py
node --check /tmp/ci_prospec_dashboard.js
node --check /tmp/ci_public_index_embedded.js
node --check /root/wins_agro_v1/ci-lojas/cliente-inteligente/assets/index.js
node --check /root/wins_agro_v1/ci-lojas/cliente-inteligente/assets/page.js
```

### Nao alterado

- Nginx.
- Docker/Compose.
- Bancos de dados.
- Processo V5 MAX.
- Credenciais ou arquivos de chave.

## Pendente

1. Construir Base Mestre.
2. Gerar `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
3. Persistir status/anotacoes da prospeccao fora de `localStorage`.
4. Regerar One Pages por whitelist publica.
5. Aplicar design system de forma segura.
