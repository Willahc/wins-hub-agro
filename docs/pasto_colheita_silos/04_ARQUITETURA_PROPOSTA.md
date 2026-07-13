# Arquitetura proposta

## Direção

**DECISÃO RECOMENDADA** — manter FastAPI/PostgreSQL/Jinja/Alpine/Leaflet/Docker Compose e modularizar por domínio gradualmente. Não criar microserviços para cada módulo e não reescrever o frontend.

```text
Nginx
  └─ FastAPI
      ├─ routers (HTTP, authz, validação)
      ├─ application (casos de uso/transações)
      ├─ domain (cálculos e regras puras/versionadas)
      ├─ repositories (SQL com tenant obrigatório)
      ├─ adapters (SIDRA, clima, satélite, storage, Log)
      └─ jobs (ingestão/checkpoint/retry)
             └─ PostgreSQL + arquivos/objetos protegidos
```

## Organização incremental de código

**PROPOSTA**:

```text
app/
  routers/{organizations,farms,feed,forage,climate,harvest,silage,grain_storage}.py
  application/{feed_balance,inventory,alerts,harvest_plan}.py
  domain/{units,formula_registry,feed,storage,confidence}.py
  repositories/{farms,herd,inventory,climate,geospatial}.py
  adapters/{sidra,nasa_power,copernicus,inmet,conab,osm,wins_log}.py
  jobs/{runner,climate_sync,satellite_sync,regional_sync}.py
  frontend/{...templates...}
```

O `main.py` inclui routers; rotas antigas continuam. Cada módulo novo nasce fora do monólito. `app/db.py` pode ser reutilizado inicialmente, mas repository recebe `actor_scope` e nunca executa consulta de negócio sem tenant/fazenda.

## Fluxo de requisição

1. Middleware decodifica sessão e monta `ActorContext(user_id, memberships, request_id)`.
2. Router resolve a fazenda selecionada e chama policy central.
3. Schema valida tipo/unidade/faixa; IDs são opacos/UUID quando expostos.
4. Caso de uso inicia transação e chama repositories escopados.
5. Evento e auditoria entram na mesma transação da mutação.
6. Resposta inclui versão/ETag quando edição concorrente for possível.

**RISCO** — confiar apenas no middleware atual autentica, mas não autoriza objetos.

## Banco e histórico

- PostgreSQL permanece sistema de registro.
- Schemas sugeridos: `identity`, `farm`, `feed`, `climate`, `geo`, `harvest`, `storage`, `integration`, ou prefixos equivalentes; nomes finais devem respeitar o inventário real.
- Ledger imutável para estoque; tabelas temporais/apêndice para observações e índices.
- `source_record` e `formula_run` guardam proveniência/snapshot.
- Índices sempre começam por `organization_id`/`farm_id` nas consultas privadas.
- Materialized views apenas para agregações regionais grandes, com refresh explícito e `as_of`.

## Geoespacial e PostGIS

**Avaliação:** o piloto precisa desenhar polígonos, calcular área, testar interseção/ponto-no-polígono, buscar vizinhos e agregar séries. GeoJSON + biblioteca na aplicação atende um volume pequeno, mas perde constraints espaciais, índices e consultas robustas. PostGIS agrega valor quando houver centenas/milhares de geometrias ou joins espaciais frequentes.

**DECISÃO RECOMENDADA** — spike isolado:

1. importar amostra anonimizada de geometrias simplificadas;
2. medir tamanho, área geodésica, `ST_Intersects`, busca por bbox e manutenção;
3. comparar GeoJSON `jsonb` + bbox/centroide versus PostGIS;
4. escolher antes da migration de piquetes.

Impactos: extensão/imagem compatível, backup/restore, migration, skills operacionais. Não ativar automaticamente em produção.

## Jobs e processamento

Na primeira versão, um runner separado pode usar a mesma imagem e uma tabela `job_run` com lock PostgreSQL. Não executar ingestão pesada dentro do worker web. Se volume/latência crescer, avaliar Redis/RQ/Celery somente com métrica concreta.

- idempotency key: fonte + dataset + versão + escopo + período;
- checkpoint por página/cena/estação;
- timeout e retry com jitter;
- circuit breaker por fonte;
- limite global e por organização;
- dead-letter revisável;
- prioridade para fazendas ativas;
- gravação em staging, validação e promoção transacional.

## Cache

| Camada | Uso | Regra |
|---|---|---|
| memória | metadado pequeno e não crítico | TTL curto; não é fonte de verdade |
| PostgreSQL | clima, índices, regional, checkpoints | chave/versionamento e `expires_at` |
| HTTP upstream | ETag/Last-Modified | respeitar termos e headers |
| browser/PWA | shell e dados explicitamente offline | nunca cachear API privada indiscriminadamente |
| arquivos/objetos | fotos, rasters recortados, exports | path opaco, autorização e retenção |

## Arquivos e anexos

O `StaticFiles` atual deliberadamente não expõe a raiz de templates/downloads (`app/main.py`, linhas 45–62). Preservar esse princípio. Fotos e anexos entram em storage privado com metadado no banco, hash, tamanho/MIME, antivírus quando aplicável, URL assinada/rota autorizada e política de retenção. Não guardar CNPJ/nome no caminho.

## Contratos de API

- prefixo `/api/v1/` para domínios novos;
- envelope de erro com `code`, mensagem segura, `request_id` e campos inválidos;
- paginação cursor para séries/movimentos;
- timestamps ISO-8601 UTC; data agronômica mantém timezone da fazenda;
- quantidades como decimal/string quando precisão importar;
- `Idempotency-Key` em mutações offline;
- OpenAPI interno/autenticado ou artefato gerado em CI, sem reabrir docs públicas.

## Observabilidade

- request/job/source/formula version no log, sem PII;
- métricas: latência/erro por rota e fonte, idade do dado, backlog, retries, cache hit, duração de job;
- readiness separada de liveness e teste de dependências sem restart loop;
- alertas operacionais para fonte vencida, job atrasado, disco e erro de autorização;
- auditoria de negócio pesquisável e distinta de logs técnicos.

## Compatibilidade com VPS

**CONFIRMADO NO CÓDIGO** — API tem limite 1,5 GiB, DB 2 GiB e serviços compartilham a VPS (`docker-compose.yml`, linhas 14–105). Não houve medição de CPU/disco nesta análise.

**DECISÃO RECOMENDADA** — satélite por processamento remoto/recorte, cache de resultado e lote diário. Não baixar mosaico nacional nem raster bruto continuamente. Antes de jobs, medir headroom, I/O, volume de backup e tempo de restore.

## Estratégia de entrega

- feature flags por organização;
- migrations futuras pequenas, reversíveis e testadas fora de produção;
- dual-read só quando indispensável; nenhuma escrita dupla sem idempotência;
- endpoints/telas antigos preservados e regressão automatizada;
- shadow calculation no MVP antes de usar alertas operacionais;
- rollout para uma fazenda piloto, depois organizações adicionais.
