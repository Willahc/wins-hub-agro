# Inventário atual

## Stack e execução

| Achado | Evidência | Consequência |
|---|---|---|
| FastAPI, Jinja2 e Pydantic | `app/main.py`, linhas 1–23 | APIs e páginas podem evoluir incrementalmente. |
| PostgreSQL 16 e pool psycopg2 | `docker-compose.yml`, linhas 14–34; `app/db.py`, linhas 11–107 | SQL explícito, sem ORM/repository atual. |
| Alpine.js, Leaflet e Chart.js self-hosted | `app/frontend/base.html`, linhas 1–100; `app/frontend/vendor/` | Reutilizar padrão visual e mapa sem SPA. |
| WeasyPrint/HTML para PDF | `app/pdf_html.py`; chamadas em `app/main.py`, linhas 1.078, 1.738, 2.420, 3.017, 5.132, 5.289 | Exportações explicáveis podem seguir o padrão. |
| Docker Compose e Nginx | `docker-compose.yml`; `nginx/nginx.conf` | Deploy atual é por serviço; sem orquestrador/fila. |
| Sem PostGIS confirmado | dependências e SQL versionado não mostram extensão espacial | Não presumir funções/índices espaciais. |

**CONFIRMADO NO CÓDIGO** — `app/db.py` oferece pool, leitura e transação, mas não repository, migrations automatizadas ou filtro de tenant. O monólito consulta tabelas diretamente.

## Estrutura do produto

- Páginas autenticadas: Fazendas, Técnica, Cruzamento, Mapa, Comercial, holdings/prospecção e Campo (`app/main.py`, linhas 1.975–2.294 e 4.050).
- Shell Jinja com sidebar/topbar e estado ativo (`app/frontend/base.html`, linhas 1–103).
- ROI Pasto Limpo autenticado no shell e versão pública no mesmo caminho escolhida por sessão (`app/routers/simulador.py`, linhas 27–47; templates `_pasto_limpo_*`).
- Cliente Inteligente é PWA estática + backend separado `ci-api`, SQLite/arquivos, host próprio (`docker-compose.yml`, linhas 66–105; `nginx/nginx.conf`, linhas 40–151; `ci/README.md`).

**RISCO** — documentos comerciais descrevem capacidades e escala que não equivalem a rotas, tabelas ou controles confirmados. Este inventário considera código/SQL versionado como fonte de verdade.

## Autenticação, autorização e auditoria

- Um e-mail configurado no ambiente, bcrypt, MFA opcional e JWT HS256 de oito horas (`app/auth.py`, linhas 8–75).
- Cookie de sessão é verificado globalmente para `/api/*`, salvo simulador e login passkey (`app/main.py`, linhas 81–109).
- CSRF por `Sec-Fetch-Site`/`Origin` e SameSite no login; headers/CSP/rate limit no Nginx (`app/main.py`, linhas 81–101 e 276–298; `nginx/nginx.conf`, linhas 1–37).
- Auditoria de visualização/exportação existe em `prospeccao.audit_log`, best-effort e fora da transação do evento (`app/main.py`, linhas 195–219).
- O código declara explicitamente app single-tenant (`app/main.py`, linhas 27–30).
- Endpoints Campo consultam/alteram por IDs recebidos; não existe membership/organization nem checagem central de propriedade (`app/main.py`, linhas 4.100–5.323).

**DECISÃO RECOMENDADA** — não estender o padrão atual de autorização aos módulos novos.

## Fazenda, rebanho e operações de campo

| Recurso confirmado | Evidência | Reuso possível | Limite |
|---|---|---|---|
| `fazenda.cliente` | consultas em `app/main.py`, linhas 4.100–4.267 | ponto de migração para fazenda/organização | “cliente” e “fazenda” estão semanticamente misturados. |
| Grupo/lote | `GrupoIn` e endpoints, linhas 3.872 e 4.268 | agrupamento inicial do balanço | não é unidade produtiva/piquete. |
| Animal | `AnimalIn`, linhas 3.879–3.907; endpoints 4.316–4.548 | cabeças, categoria, peso, status | autorização por animal ausente. |
| Pesagem | `PesagemIn`, linhas 3.908–3.920; endpoint 4.978 | peso recente/médio | exige regra de validade e agregação. |
| Sanitário/agenda | linhas 3.921–3.939 e 5.024–5.131 | alertas/padrão de eventos | domínio distinto. |
| Estação/IATF/DG | linhas 3.940–3.999 e 4.549–4.887 | padrão de evento/lote/idempotência | não reutilizar entidades como safra. |
| Movimentação animal | linhas 4.010–4.027 e 5.259–5.323 | padrão de ledger/evento | novo estoque deve ter ledger próprio. |
| PDF | rotas citadas acima | snapshot/exportação | requer autorização do recurso. |

## Offline e PWA

- Service worker guarda vendors e shell `/campo`; `/api` não é cacheada (`app/frontend/sw.js`, linhas 1–76).
- Campo usa `localStorage` para catálogo, fazenda atual e outbox; UUID, data de captura, timeout, retries, dead-letter e replay (`app/frontend/campo.html`, linhas 986–1.160).
- Algumas tabelas têm `uuid UNIQUE` para idempotência (`scripts/migration_cruzamento.sql`, linhas 4–23; `migration_estacao.sql`, linhas 4–19; `migration_venda.sql`, linhas 3–21).
- Operações offline incluem animal, pesagem, sanitário, descarte, cruzamento, venda e movimentação (`campo.html`, linhas 1.188–1.700).

**RISCO** — `localStorage` não fornece cifragem, transação robusta, quota previsível ou isolamento por usuário/organização/fazenda. O shell autenticado pode existir no cache para uso offline, mas dados sincronizados ainda podem permanecer no dispositivo após troca de usuário.

**PROPOSTA** — migrar somente os novos registros de campo para IndexedDB versionado, com partition key e limpeza/revogação; não reescrever toda a PWA no primeiro passo.

## Mapas, território e dados agrícolas

- Leaflet + tiles OSM e camadas municipais de rebanho, lotação, pasto, vigor, lavoura, ILP, leite e valor (`app/frontend/mapa.html`, linhas 1–167).
- APIs territoriais agregadas e relatórios PDF (`app/main.py`, linhas 2.656–3.036).
- SIDRA já é consumido com cache em memória de 24h para rebanho/leite/valor municipal (`app/external_apis.py`, linhas 1–165).
- Scripts versionados ingerem PAM/IBGE e MapBiomas; CAR/SICAR é baixado/processado e geometrias são guardadas como GeoJSONL comprimido (`scripts/ingest_pam_lavoura.py`; `ingest_mapbiomas_pasto.py`; `pasto_full_br.py`, linhas 1–188).
- Endpoint NDVI usa um serviço público de série por ponto e grava cache em `imovel_rural` (`app/main.py`, linhas 3.780–3.825); há experimento Earth Engine por polígono (`scripts/ndvi_pasto_gee.py`).

**RISCO** — camadas atuais são sinais agregados/experimentais. “Vigor degradado” modal e NDVI pontual não equivalem a diagnóstico por piquete, nem têm série temporal, máscara de nuvem, incerteza e validação de campo suficientes.

## Integrações externas atuais

`app/external_apis.py` implementa cache em memória, timeout e acesso a SIDRA, BrasilAPI, BCB/Frankfurter e páginas de cotação. Não há interface de adapter, persistência de checkpoints, circuit breaker, telemetria por fonte ou versionamento do payload.

**RISCO** — algumas cotações vêm de HTML republicado/terceiro (`app/external_apis.py`, linhas 166–259). Não devem ser copiadas como padrão para fontes agronômicas; usar documentação e fonte oficial.

## Testes e observabilidade

- Pytest cobre autenticação; unittest cobre ROI Pasto Limpo (`app/tests/`).
- Scripts Playwright exercitam Campo, mas criam dados de demonstração e não são seguros contra produção (`scripts/test_campo_*.py`).
- `/healthz` é liveness sem banco; logs Python estruturados; Docker limita/rotaciona logs (`app/main.py`, linhas 24–76; `docker-compose.yml`, linhas 7–63).
- Não foram confirmados métricas, tracing, Sentry, fila de jobs, testes de autorização multi-tenant ou ambiente de integração isolado.

## Componentes que podem ser reaproveitados

1. `base.html`, `app.css` e componentes de cards/filtros/tabelas.
2. Leaflet e utilitários de mapa, após extrair código compartilhável.
3. helpers de DB/transação, temporariamente, encapsulados em repositories.
4. animais, grupos e pesagens como insumos da demanda.
5. UUID/outbox/retry como experiência, não como armazenamento final.
6. renderização de PDF e proteção de downloads.
7. SIDRA/cache como primeiro adapter a ser formalizado.
8. geometrias CAR e dados MapBiomas/PAM como candidatos, após proveniência/licença/identidade da fazenda.

## Lacunas

- organização, membership, papéis e autorização por objeto;
- cadastro operacional inequívoco de fazenda/unidade/talhão/piquete;
- geometria editável e histórico espacial;
- estoques, silos, culturas, safras, clima, séries e alertas;
- fórmulas/parametrização/versionamento/unidades;
- scheduler/fila/checkpoint/observabilidade de ETL;
- storage protegido de fotos/anexos;
- testes isolados e banco de teste;
- contrato com WiNS Hub Log.
