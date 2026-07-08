# Relatorio Codex - Cliente Inteligente

Data da analise: 2026-07-07 11:50 UTC  
Escopo: analise somente leitura do ecossistema Cliente Inteligente na VPS. Nenhum arquivo de producao, Nginx, banco, One Page ou processo de enriquecimento foi alterado.

## 1. Visao geral da arquitetura atual

O projeto `Cliente Inteligente` hoje esta dividido em tres superficies principais:

1. **App / painel do comerciante**
   - URL: `https://ci.winshubagro.cloud`
   - Pasta: `/root/wins_agro_v1/ci`
   - Tipo: app estatico single-file, offline-first/PWA.
   - Arquivos principais: `index.html`, `sw.js`, `manifest.json`, `libs/`.
   - Persistencia primaria: IndexedDB via Dexie.
   - Persistencia auxiliar: `localStorage`.
   - Backend auxiliar: `ci-api`, usado para conta, backup cifrado e publicacao de loja.

2. **One Pages publicas / paginas dos estabelecimentos**
   - URL atual: `https://ci.winshubagro.cloud/loja/cliente-inteligente/`
   - Pasta atual: `/root/wins_agro_v1/ci-lojas/cliente-inteligente`
   - Copia/teste: `/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2`
   - Conteudo: 813 paginas estaticas em `negocios/<slug>/index.html`, mais indice, CSS/JS e `data/negocios.json`.
   - Situacao: geradas a partir da base Campanella, mas ainda nao consomem diretamente uma Base Mestre enriquecida e filtrada por regras publicas.

3. **Ferramenta interna de prospeccao/campo**
   - URL: `https://ci.winshubagro.cloud/prospec/`
   - Pasta: `/root/wins_agro_v1/prospeccao-campanella`
   - Tipo: dashboard estatico gerado a partir de SQLite, protegido por Basic Auth no Nginx.
   - Banco principal atual: `campanella_prospeccao_enriquecida_v3.db`.
   - Dados: inclui score, tier, CNPJ candidato, confianca, dores/reclamacoes, pitch, status e anotacoes locais.

Existe tambem a API legada do WiNS Agro:

- Pasta: `/root/wins_agro_v1/app`
- Container: `wins_agro_v1-api-1`
- Stack: FastAPI + Postgres.
- Roteada em `https://winshubagro.cloud`, nao e o backend principal do Cliente Inteligente, mas compartilha o mesmo compose/Nginx.

## 2. Mapa de pastas relevante

```text
/root/wins_agro_v1
├── docker-compose.yml
├── nginx/
│   ├── nginx.conf
│   └── .htpasswd_prospec
├── ci/
│   ├── index.html
│   ├── sw.js
│   ├── manifest.json
│   └── libs/
├── ci-api/
│   ├── app.py
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── litestream.yml
├── ci-data/
│   └── ci.db
├── ci-lojas/
│   ├── cliente-inteligente/
│   └── cliente-inteligente-v2/
├── prospeccao-campanella/
│   ├── dashboard.html
│   ├── gerar_dashboard.py
│   ├── classificar.py
│   ├── campanella_prospeccao.db
│   ├── campanella_prospeccao_enriquecida.db
│   ├── campanella_prospeccao_enriquecida_v3.db
│   └── field_kit/
├── enriquecimento_v5max_cnpj/
│   └── cliente_inteligente_enriquecimento_v5_max_cnpj/
│       ├── enriquecer_v5_max.py
│       ├── prospectos_v4_enriquecidos.csv
│       ├── run_v5max.log
│       └── out_v5max/
└── app/
    ├── main.py
    ├── db.py
    └── frontend/
```

## 3. Docker e servicos em execucao

`docker ps` mostrou:

| Container | Servico | Papel | Status |
|---|---|---|---|
| `wins_agro_v1-nginx-1` | `nginx` | HTTPS, rotas, arquivos estaticos, proxy API | Up 11 days |
| `wins_agro_v1-ci-api-1` | `ci-api` | Backend Cliente Inteligente | Up 4 days, healthy |
| `wins_agro_v1-api-1` | `api` | API WiNS Agro legada | Up 5 days, healthy |
| `wins_agro_v1-db-1` | `db` | Postgres 16 | Up 5 days, healthy |
| `wins_agro_v1-certbot-1` | `certbot` | Renovacao TLS | Up 2 weeks |

O `docker-compose.yml` monta:

- `./ci` em `/var/www/ci`.
- `./ci-lojas` em `/var/www/lojas:ro`.
- `./prospeccao-campanella` em `/var/www/prospec:ro`.
- `./ci-data` em `/data` no `ci-api`.
- `./ci-lojas` em `/data/lojas` no `ci-api`, com escrita para publicar cardapios/lojas.

## 4. Rotas publicas e privadas atuais

### `ci.winshubagro.cloud`

| Rota | Origem | Observacao |
|---|---|---|
| `/` | `/var/www/ci/index.html` | App comerciante estatico/PWA |
| `/api/register`, `/api/login`, `/api/recovery` | `ci-api:8000` | Rate limit mais restrito |
| `/api/*` | `ci-api:8000` | Backup, loja, conta |
| `/loja/cliente-inteligente/` | `/var/www/lojas/cliente-inteligente/` | One Pages MVP |
| `/loja/<slug>/` | `/var/www/lojas/<slug>/` | Lojas/cardapios publicados |
| `/guia/` | `/var/www/lojas/cliente-inteligente/` | Alias demonstrativo |
| `/libs/` | `/var/www/ci/libs/` | Bibliotecas cacheadas |
| `/prospec/` | `/var/www/prospec/` | Privado com Basic Auth |

### `winshubagro.cloud`

| Rota | Origem | Observacao |
|---|---|---|
| `/` | `api:8000` | API/app WiNS Agro |
| `/api/*` | `api:8000` | Rotas legadas protegidas por sessao, exceto simulador |
| `/login` | `api:8000` | Login legado |

## 5. Nginx, CSP e riscos de bloqueio

O Nginx esta relativamente bem segmentado, mas ha pontos de atencao:

- A rota `/prospec/` usa `^~`, Basic Auth, `deny all` para `.py`, `.db`, `.log`, `.md` e CSP propria liberando `unpkg.com` e tiles OpenStreetMap. Isso explica por que o Leaflet da prospeccao funciona mesmo usando CDN.
- As One Pages em `/loja/cliente-inteligente/` e `/loja/` usam CSP com `script-src 'self' 'unsafe-inline'`, `style-src 'self' 'unsafe-inline'`, imagens de tiles e Google Maps, mas `connect-src 'self'`. Se alguma pagina publica passar a carregar API externa, iframe ou JS externo, a CSP atual vai bloquear.
- O app CI usa CSP propria `$ci_csp`, com `nominatim.openstreetmap.org` e `wa.me` em `connect-src`, alem de `unsafe-eval` por dependencias como jsPDF/Chart.
- `X-Frame-Options SAMEORIGIN` nas paginas do CI pode impedir incorporacao externa por parceiros; isso e bom como padrao, mas deve ser considerado se houver widget/iframe no futuro.
- Nao alterar Nginx sem backup e confirmacao. A configuracao atual protege bem a separacao `/prospec/` privada vs `/loja/` publica.

## 6. Estado do app comerciante

Arquivos principais:

- `/root/wins_agro_v1/ci/index.html`: 4.948 linhas.
- `/root/wins_agro_v1/ci/sw.js`: 75 linhas.
- `/root/wins_agro_v1/ci/libs/`: Chart.js, Dexie, Fuse, jsPDF, Leaflet, QRCode e fontes.

Caracteristicas confirmadas:

- App single-file, sem build.
- PWA offline-first.
- IndexedDB via Dexie como persistencia principal.
- `localStorage` como espelho/fallback.
- Backup JSON local.
- Backup em nuvem opcional e cifrado no cliente.
- Publicacao de loja via `PUT /api/loja`.
- Uso de Nominatim/Leaflet no fluxo de delivery/mapa.

O `ci-api` hoje tem estas rotas:

- `GET /api/health`
- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`
- `PUT /api/backup`
- `GET /api/backup`
- `PUT /api/loja`
- `GET /api/me`
- `PUT /api/recovery`
- `GET /api/recovery/info`
- `POST /api/recovery/reset`

Banco `ci-data/ci.db`:

- Tabelas: `contas`, `sessions`.
- Linhas atuais: `contas = 0`, `sessions = 0`.
- Nao existe ainda tabela de Base Mestre, perfil de estabelecimento, status comercial ou anotacao de prospeccao no `ci-api`.

## 7. Estado das One Pages

Pastas:

- `/root/wins_agro_v1/ci-lojas/cliente-inteligente`
- `/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2`

Ambas possuem:

- 813 paginas em `negocios/<slug>/index.html`.
- `data/negocios.json` com 813 registros.
- `assets/index.js`, `assets/page.js`, `assets/site.css`.

Campos no `data/negocios.json`:

```text
nome, segmento, endereco, telefone, tem_site, nota, num_avaliacoes,
tier, prioridade, score, seg_key, url, maps_url
```

Problema importante: embora nao haja CNPJ, dor ou reclamacao no JSON publico, ha campos internos expostos: `tier`, `prioridade` e `score` em todos os 813 registros. Esses campos nao devem aparecer em pagina publica.

O CSS atual das One Pages usa tema verde (`--brand:#0f6b4d`, `--brand2:#13a06f`), diferente do padrao desejado cinza/preto/vermelho. A estetica ainda nao esta padronizada com o app e a prospeccao.

## 8. Estado da prospeccao interna

Banco base:

- `campanella_prospeccao.db`
- `estabelecimentos`: 813 linhas.
- `reclamacoes`: 581 linhas.
- Campos relevantes: nome, endereco, telefone, website, instagram, segmento, nota, avaliacoes, horario, status, lat/lng, maps, score, prioridade.

Banco enriquecido:

- `campanella_prospeccao_enriquecida.db`
- `estabelecimentos_enriquecidos`: 813 linhas.
- `external_enrichment`: 503 linhas.

Banco V3:

- `campanella_prospeccao_enriquecida_v3.db`
- `estabelecimentos_enriquecidos`: 813 linhas.
- `estabelecimentos_enriquecidos_v3`: 813 linhas.
- `external_enrichment`: 93 linhas.
- `reclamacoes`: 581 linhas.

Campos V3 relevantes:

- Dados publicos: nome, segmento, endereco, telefone, nota, avaliacoes, lat/lng, maps.
- Dados digitais: website, instagram, cardapio, ifood, whatsapp, presenca web.
- Dados internos: CNPJ provavel, razao social, situacao cadastral, CNAE, score comercial, legal risk, lead tier, abordagem recomendada.
- Dados de venda: dor dominante, exemplos de dor, pitch, oferta, modulos recomendados, acao.
- Dados de campo: visitado, responsavel, sistema atual, dor confirmada, status funil, resultado, proxima acao, observacoes.

### Fallback emergencial encontrado

O arquivo `/root/wins_agro_v1/prospeccao-campanella/dashboard.html` tem o dashboard gerado e, depois do fechamento do script principal, um segundo bloco:

```html
<script id="CI_FALLBACK_RENDER_PROSPEC">
```

Esse bloco:

- Rele `#dados`.
- Sobrescreve renderizacao da lista e do painel.
- Reimplementa filtros.
- Injeta CSS proprio com `id="ci-fallback-style"`.
- Cria ficha de captacao local.
- Salva anotacoes em `localStorage` com chave `ci_prospec_note_<id>`.
- Mostra CNPJ, confianca, dores/reclamacoes e pitch.

Isso confirma que a prospeccao esta usando um fallback emergencial. Ele resolve a operacao imediata, mas cria risco de divergencia, comportamento imprevisivel e perda de anotacoes por ficarem no navegador.

## 9. Enriquecimento V5 MAX CNPJ

Processo confirmado no host:

```text
python3 enriquecer_v5_max.py --input prospectos_v4_enriquecidos.csv --all --limit 0 --sleep 4 --provider both --max-results 8 --max-pages 8 --deep
```

Status:

- O processo estava rodando no momento da analise.
- Nao foi morto nem alterado.
- O comando `ps aux | grep enriquecer_v5_max | grep -v grep` confirmou o PID `3737234`.

Arquivos de saida:

| Arquivo | Status observado |
|---|---|
| `out_v5max/prospectos_v5max_externos.csv` | existe, crescendo |
| `out_v5max/prospectos_v5max_externos.json` | existe, crescendo |
| `out_v5max/relatorio_v5max.html` | existe |

Estatisticas observadas em 2026-07-07 por volta de 11:49 UTC:

- CSV: 657 linhas, 84 campos, separador `;`.
- JSON: 657 registros no momento da ultima leitura estruturada.
- `v5max_status`: 657 `ok`.
- `v5max_prioridade_final`: C = 316, B = 266, A = 55, A+ externo = 20.
- `lead_tier_v4`: C = 316, B = 266, A = 55, A+ = 20.
- `cnpj_status`: 657 `pendente_enriquecimento_externo`.
- `v5max_cnpj_confidence`: 657 com `0`.
- Sem valores preenchidos ainda nos campos `v5max_site_oficial_candidato`, `v5max_instagram_url`, `v5max_facebook_url`, `v5max_delivery_cardapio_url`, `v5max_whatsapp_externo` e `v5max_cnpj_candidato`.

Observacao: os arquivos tinham `mtime` mais recente que o log `run_v5max.log`; portanto, o log pode nao refletir o progresso final. Usar os arquivos de saida como fonte de acompanhamento.

## 10. Problemas encontrados

### Criticos

1. **Dados internos aparecem em artefatos publicos**
   - `data/negocios.json` das One Pages expoe `tier`, `prioridade` e `score`.
   - Isso deve sair da camada publica.

2. **Prospecção depende de fallback emergencial**
   - O dashboard tem dois sistemas de renderizacao no mesmo HTML.
   - Filtros, ficha de captacao e detalhes devem ser reconstruidos no gerador oficial, nao em patch anexado.

3. **Anotacoes de campo nao persistem no servidor**
   - O fallback salva anotacoes no `localStorage`.
   - Isso perde dados ao trocar navegador/dispositivo e nao permite gestao centralizada.

4. **Base Mestre ainda nao existe como contrato unico**
   - Hoje ha SQLites, CSVs, JSONs e HTMLs com campos parecidos, mas sem camada canonica.
   - Cada superficie consome uma versao diferente dos dados.

### Altos

5. **One Pages nao usam Base Mestre enriquecida filtrada**
   - As paginas foram geradas de uma base anterior e nao aplicam uma politica explicita de publicacao.

6. **Mistura conceitual entre publico e interno**
   - A prospeccao pode ter CNPJ, dor, score e pitch; One Page nao pode.
   - Hoje essa regra depende de disciplina do gerador, nao de schema/validador.

7. **Arquivos duplicados**
   - Ha duas copias completas de One Pages (`cliente-inteligente` e `cliente-inteligente-v2`) com 813 paginas cada.
   - Ha backups de dashboards e bancos na prospeccao.
   - Isso e util como historico, mas aumenta risco de publicar a versao errada.

8. **CSS global e estilos embutidos**
   - App CI e prospeccao usam CSS/JS grandes e inline.
   - O fallback injeta CSS que pode conflitar com o dashboard original.

### Medios

9. **Design nao padronizado**
   - App CI tem identidade propria.
   - One Pages estao verdes.
   - Prospecção usa azul/slate e fallback preto/branco.
   - A direcao cinza/preto/vermelho ainda nao virou design system.

10. **CSP pode bloquear evolucoes futuras**
   - One Pages bloqueiam `connect-src` externo.
   - Iframes de mapa nao estao claramente liberados via `frame-src`.
   - Hoje parece aceitavel para a versao estatica, mas precisa ajuste se adicionar mapa interativo/iframe/API externa.

11. **`ci-api` ainda nao e multi-tenant de verdade**
   - Tem contas e slug, mas nao ha modelo de estabelecimento, usuarios por empresa, papeis, auditoria ou relacao com Base Mestre.

## 11. Proposta de Base Mestre Cliente Inteligente

Criar uma Base Mestre canonica, preferencialmente como SQLite/Postgres ou CSV/JSON versionado gerado por pipeline, com validacao antes de publicar.

Tabela principal sugerida: `cliente_inteligente_master`.

Campos:

```text
id
place_id
slug
nome_comercial
categoria
segmento
familia_segmento
endereco
latitude
longitude
telefone
whatsapp_confirmado
whatsapp_provavel
site_oficial
instagram
facebook
cardapio_url
delivery_url
maps_url
nota
num_avaliacoes
horario
descricao_publica

cnpj
cnpj_status
cnpj_confidence
razao_social
nome_fantasia
situacao_cadastral
cnae
cnae_descricao
porte
data_abertura

score_digital
score_dor
score_comercial
lead_tier
dor_dominante
oferta_recomendada
modulos_recomendados
pitch_presencial
mensagem_whatsapp
acao_recomendada

usar_onepage
usar_app_comerciante
usar_prospeccao
publicavel_status
nivel_confianca_publico
nivel_confianca_interno
fontes_json
quality_flags
updated_at
```

Tabelas auxiliares recomendadas:

- `ci_master_sources`: fonte, URL, data, confianca, campo afetado.
- `ci_master_publicacao`: slug, status, publicado_em, versao_publicada, hash_html.
- `ci_master_prospeccao_status`: lead_id, status_funil, responsavel, proxima_acao, anotacoes, atualizado_por, atualizado_em.
- `ci_master_auditoria`: evento, usuario, origem, payload resumido, data.
- `ci_segmento_rules`: segmento/familia -> modulos, produtos sugeridos, copy publica, oferta, pitch.

## 12. Regras por ferramenta

### One Page publica

Permitido:

- `nome_comercial`
- `categoria`
- `segmento`
- `endereco`
- `telefone` publico
- `whatsapp_confirmado` somente se publico/confiavel
- `site_oficial`
- `instagram`
- `facebook`
- `cardapio_url`
- `delivery_url`
- `maps_url`
- `horario`
- `nota`
- `num_avaliacoes`
- `descricao_publica`

Proibido:

- CNPJ candidato/provavel
- razao social sem revisao
- socios
- scores internos
- lead tier
- prioridade
- dores/reclamacoes
- pitch interno
- risco legal
- campos de confianca interna
- dados marcados como `CANDIDATO`, `FRACO` ou `NAO_ENCONTRADO`

Regra de publicacao:

- So publicar se `publicavel_status = PUBLICAVEL` e `nivel_confianca_publico >= 80`.
- Se duvidoso, mostrar apenas dados basicos de mapa/contato publico ou nao gerar pagina individual.

### App comerciante

Usar:

- segmento
- categoria
- familia_segmento
- produtos sugeridos
- modulos recomendados
- templates de cardapio/catalogo
- configuracao inicial de PDV/estoque/CRM/fidelidade
- dados que o comerciante confirmar no onboarding

Nao usar automaticamente:

- dor/reclamacao como texto visivel ao comerciante sem contexto.
- CNPJ candidato como dado oficial.
- score comercial como elemento de UI.

### Prospecção interna

Pode usar:

- todos os campos da Base Mestre
- CNPJ candidato/confirmado
- confianca
- score
- tier
- dor dominante
- reclamacoes
- pitch
- mensagem WhatsApp
- rota
- status de visita
- anotacoes

Obrigatorio:

- Sempre exibir nivel de confianca.
- Separar `CONFIRMADO`, `PROVAVEL`, `CANDIDATO`, `FRACO`, `NAO_ENCONTRADO`.
- Permitir correcao manual e registrar auditoria.

## 13. Classificacao de confianca recomendada

Para o pos-processamento do V5:

| Classe | Regra sugerida |
|---|---|
| `CONFIRMADO` | match forte por nome + endereco/telefone/site oficial; confianca >= 85 |
| `PROVAVEL` | match bom com uma divergencia menor; confianca 65-84 |
| `CANDIDATO` | evidencia parcial; confianca 40-64 |
| `FRACO` | evidencia baixa ou fonte generica; confianca 15-39 |
| `NAO_ENCONTRADO` | sem evidencia util; confianca < 15 |

Aplicar por campo, nao apenas por registro:

- `cnpj_confidence`
- `site_confidence`
- `instagram_confidence`
- `whatsapp_confidence`
- `cardapio_confidence`
- `delivery_confidence`

## 14. Avaliacao de frontend

### App CI

Pontos fortes:

- Funciona offline.
- Sem build/dependencias externas em runtime.
- Usa IndexedDB e service worker.
- Tem backup cifrado em nuvem.

Riscos:

- `index.html` com quase 5 mil linhas concentra UI, regra de negocio e persistencia.
- Mudancas visuais globais podem quebrar muitos fluxos.
- Tema e componentes nao estao isolados.

Recomendacao:

- Nao refatorar tudo agora.
- Criar camada de tokens CSS no topo e componentes pequenos por classe.
- Ajustar tema por variaveis, nao por seletores globais destrutivos.

### One Pages

Pontos fortes:

- Estrutura simples e estavel.
- 813 paginas ja geradas.
- Funciona como estatico.

Riscos:

- Dados internos `tier`, `prioridade`, `score` expostos.
- Visual verde fora do padrao pedido.
- Dados duplicados em JSON e embutidos no HTML.

Recomendacao:

- Criar `gerar_onepages_publicas.py` com whitelist de campos.
- Gerar `public/negocios_publicos.json` apenas com dados publicos.
- Remover score/tier/prioridade da camada publica.

### Prospecção

Pontos fortes:

- Dados ricos e úteis para campo.
- Protegida por Basic Auth.
- Nginx nega `.py`, `.db`, `.log`, `.md`.

Riscos:

- Fallback emergencial duplicando a UI.
- Anotacoes em `localStorage`.
- Dependencia de CDN `unpkg` para Leaflet.

Recomendacao:

- Reescrever `gerar_dashboard.py` como fonte unica da tela.
- Mover ficha de captacao e filtros para o gerador.
- Persistir status/anotacoes em API simples protegida ou arquivo SQLite interno, nunca so no navegador.

## 15. Design system simples sugerido

Paleta:

```text
--ci-bg: #f5f5f5
--ci-surface: #ffffff
--ci-ink: #111111
--ci-muted: #5f6368
--ci-line: #dedede
--ci-red: #c1121f
--ci-red-dark: #8f0d17
--ci-black: #0b0b0b
--ci-gray-50: #fafafa
--ci-gray-100: #f3f4f6
--ci-gray-900: #111827
```

Componentes:

- `.ci-button`, `.ci-button--primary`, `.ci-button--danger`, `.ci-button--ghost`
- `.ci-input`, `.ci-select`, `.ci-textarea`
- `.ci-chip`, `.ci-badge`, `.ci-status`
- `.ci-layout`, `.ci-panel`, `.ci-table`, `.ci-toolbar`
- `.ci-public-page` separado de `.ci-internal`

Regra importante:

- Evitar CSS global como `.card`, `.btn`, `.tag` sem prefixo.
- Prefixar componentes novos com `ci-`.
- Nao trocar visual do app inteiro por seletores amplos.

## 16. Avaliacao de backend e persistencia

### `ci-api`

Bom:

- Separado da API Agro.
- SQLite simples.
- Conta/token.
- Backup cifrado no cliente.
- Sanitizacao basica ao publicar HTML (`<script>` bloqueado, handlers inline removidos, `javascript:` neutralizado).

Limites atuais:

- Nao armazena Base Mestre.
- Nao armazena estabelecimentos.
- Nao persiste status/anotacao de prospeccao.
- Nao tem multiusuario/tenant robusto.
- Publicacao de loja grava HTML direto em filesystem.

### API legada `/app`

Papel:

- FastAPI grande do WiNS Agro.
- Postgres via `db.py`.
- Muitas rotas de agro, prospeccao legada, campo e simulador.

Recomendacao:

- Nao misturar Cliente Inteligente novo dentro do monolito Agro.
- Manter `ci-api` como backend do CI e evoluir com contratos pequenos.

## 17. Plano de correcao em fases

### Fase 0 - Congelamento e backup

1. Nao mexer no V5 enquanto roda.
2. Fazer backup de:
   - `ci/`
   - `ci-lojas/`
   - `prospeccao-campanella/`
   - `ci-data/ci.db`
   - `nginx/nginx.conf`
3. Registrar checksums dos arquivos publicados.

### Fase 1 - Base Mestre e regras de publicacao

1. Criar pipeline de consolidacao V3/V4/V5 para `cliente_inteligente_master`.
2. Aplicar classificacao de confianca por campo.
3. Gerar tres visoes:
   - `master_public.json`
   - `master_app_seed.json`
   - `master_prospeccao.json`
4. Validar que `master_public.json` nao contem CNPJ, dor, score, pitch ou tier.

### Fase 2 - Rebuild da prospeccao

1. Remover dependencia do fallback emergencial por meio de novo `gerar_dashboard.py`.
2. Implementar filtros oficiais:
   - tier
   - segmento/familia
   - site/presenca
   - CNPJ status
   - confianca
   - oferta
   - rota
   - status funil
3. Implementar ficha de captacao oficial.
4. Persistir anotacoes/status em SQLite/API, com export CSV.

### Fase 3 - One Pages publicas seguras

1. Criar gerador publico com whitelist.
2. Remover `tier`, `prioridade`, `score` do JSON publico e HTML publico.
3. Padronizar visual cinza/preto/vermelho.
4. Regerar em pasta staging.
5. Revisar amostras antes de trocar producao.

### Fase 4 - App comerciante com pre-configuracao

1. Criar seed por segmento.
2. Onboarding pede confirmacao do comerciante.
3. Preencher modulos recomendados sem expor origem interna.
4. Evoluir `ci-api` para guardar perfil de estabelecimento.

### Fase 5 - Multi-tenant futuro

1. Tabelas `tenants`, `users`, `memberships`, `stores`.
2. `store_id` em backups/publicacoes.
3. Auditoria por tenant.
4. Separar permissao de comerciante, operador interno e admin.

## 18. O que deve ser feito primeiro

1. Esperar ou acompanhar o V5 MAX terminar; nao matar o processo.
2. Criar pos-processador da Base Mestre com classificacao de confianca.
3. Gerar `master_public.json` e validar automaticamente campos proibidos.
4. Reconstruir a prospeccao sem fallback emergencial.
5. Regerar One Pages publicas em staging, sem score/tier/prioridade.

## 19. O que nao deve ser mexido agora

- Nao matar `enriquecer_v5_max.py`.
- Nao alterar Nginx em producao sem backup e confirmacao.
- Nao sobrescrever `/ci-lojas/cliente-inteligente` diretamente.
- Nao misturar CNPJ/dor/reclamacao em One Page publica.
- Nao refatorar o `ci/index.html` inteiro antes da Base Mestre estar definida.
- Nao migrar tudo para Postgres agora se SQLite/JSON versionado resolver a primeira fase.
- Nao publicar dados V5 com confianca `0` ou `pendente_enriquecimento_externo`.

## 20. Checklist da proxima implementacao

- [ ] Verificar novamente se o V5 terminou e quantas linhas finais gerou.
- [ ] Fazer backup timestampado das pastas e bancos envolvidos.
- [ ] Criar script `ci_master_build.py` ou equivalente.
- [ ] Ler `prospectos_v5max_externos.csv/json` com separador correto `;`.
- [ ] Normalizar IDs: `place_id`, `slug`, `id`.
- [ ] Aplicar confidence por campo.
- [ ] Gerar `master_prospeccao.json`.
- [ ] Gerar `master_public.json` com whitelist.
- [ ] Testar validador que falha se campo proibido aparecer no publico.
- [ ] Recriar dashboard de prospeccao sem `CI_FALLBACK_RENDER_PROSPEC`.
- [ ] Persistir anotacoes/status fora do `localStorage`.
- [ ] Regerar One Pages em pasta staging.
- [ ] Conferir CSP antes de publicar mapa, iframe ou recurso externo.
- [ ] Fazer diff visual de amostras por segmento.
- [ ] So depois trocar Nginx/publicacao, com backup e confirmacao.

