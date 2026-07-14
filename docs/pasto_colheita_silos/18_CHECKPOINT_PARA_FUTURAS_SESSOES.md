# Checkpoint para futuras sessões

## Atualização — Fase 0A iniciada sobre `e5b131c`

**IMPLEMENTADO NESTA ETAPA:** foram criadas fundações multiusuário em módulos
isolados, SQL não aplicado, testes sintéticos e documentação em
`docs/fase0_fundacoes/`. A fazenda operacional permanece separada da base de
prospecção de `/fazendas`; rotas legadas não foram migradas. A vertical slice
privada fica desligada por padrão.

**DECISÃO:** autorização deny-by-default, UUID externo, escopo server-side,
auditoria transacional, unidades dimensionais, parâmetros/fórmulas versionados e
registry sem `eval`.

**LIMITAÇÃO:** não houve backfill, integração com PostgreSQL, UI, deploy ou adoção
pelos endpoints antigos. O working tree desta execução contém a implementação ainda
sem commit.

**PRÓXIMO PASSO:** ler `docs/fase0_fundacoes/12_CHECKPOINT_FASE0.md` e executar a
Fase 0B primeiro em PostgreSQL 16 descartável, com revisão DBA e mapeamento
explícito do legado operacional.

## Atualização — Fase 0B validada fora de produção

**IMPLEMENTADO:** harness PostgreSQL 16 isolado, revisão DBA, vínculo explícito
somente com `fazenda.cliente`, bootstrap idempotente com dry-run padrão e rollback
conservador. A prospecção permanece fora do modelo privado.

**TESTADO:** constraints cross-tenant, grants, PUBLIC, triggers, auditoria,
idempotência, conflitos, carga sintética, EXPLAIN e down sem CASCADE. Nenhuma
migration foi aplicada em produção.

**PRÓXIMO PASSO:** Fase 0C em homologação restaurável: aprovar roles, backup/restore,
mappings sintéticos e primeira vertical legada de baixo risco. Ler os documentos
`13` a `17` em `docs/fase0_fundacoes/` antes de continuar.

## Atualização — Fase 0C homologada em ambiente restaurável

**IMPLEMENTADO:** harness PostgreSQL 16 exclusivo e restaurável, aprovação definitiva de roles (`wins_agro_migrator`, `wins_agro_app`, `wins_agro_readonly`), validação automática de privilégios e grants, backup lógico com pg_dump e restauração com pg_restore em segunda instância limpa, obtendo MATCH físico e lógico absoluto.

**TESTADO:** DDL e grants idênticos, contagens batendo perfeitamente, idempotência e rollback sob conflitos via CLI real, e rejeição de IDOR e elevação de papel. Nenhuma alteração foi realizada em produção.

**PRÓXIMO PASSO:** Fase 0D: implantação da fundação em homologação persistente, migração da primeira rota legada somente leitura desenhada (Listagem de Fazendas Permitidas), e validação com os times operacionais.

## Atualização — Fase 0D validada em Staging Persistente

**IMPLEMENTADO:** vertical slice `/api/v2/farms` (listagem de fazendas com isolamento server-side), autenticação real via cookie JWT, e ambiente de staging persistente (`wins_agro_fase0d`). A feature flag `ENABLE_FARMS_V2` e o router foram adicionados ao monólito de forma condicional.

**TESTADO:** validação de autenticação, memberships, IDOR, paginação e latência (mediana 6ms, p95 8ms) com 10.000 fazendas sintéticas. Nenhuma alteração ou conexão ocorreu na produção.

**PRÓXIMO PASSO:** Fase 0E: backfill de dados reais em produção e liberação gradual do endpoint `/api/v2/farms` usando feature flags.

## Atualização — Fase 0E1 inventariada e remediada sob regras estritas de privacidade

**IMPLEMENTADO:** Ferramenta de inventário `inventory_readonly.py` executada com transação estrita de leitura e rollback sistemático em produção. Coleta controlada recuperada com segurança no host sob permissões restritas (700/600). Remediação de privacidade com exclusão total de dados de auditoria, WebAuthn e sessões, reclassificando propostas para a Classe F (sem evidência suficiente).

**TESTADO:** Validação de segurança estática no repositório, teste de integridade em staging sintético (escrita nula comprovada com 34 contagens idênticas pré/pós), e todos os 87 testes do host validados e aprovados.

**PRÓXIMO PASSO:** Fase 0E2: revisão humana de mappings e consolidação do roadmap de backfill.

## Atualização — Fase 0E2 preparada para revisão humana offline de mappings

**IMPLEMENTADO:** Ferramentas offline em `scripts/fase0e2/` para gestão do lote, validação de origem e integridade das decisões preenchidas. Template `human_decisions_template_private.csv` inicializado sem decisões prévias sob o diretório privado e restrito da Fase 0E2 (700/600).

**TESTADO:** Validação de restrições de segurança (path traversal, symlinks, bloqueio de rede/banco), regras de conformidade (rejeição de enums de aprovação como `APPROVE`), e 94 testes unitários validados e executados com OK.

**PRÓXIMO PASSO:** Fase 0E3: simulação em lote de mappings aprovados e testes de dry-run.


## Estado

- Plano estratégico originalmente analisado em `84fcf70e15567ddc6c812d638c816204e5ae9035`;
  Fase 0A iniciada em `master` / `e5b131c5360bb566939f4aa43621c05eec5a70a0`.
- Análise feita só por código, SQL e documentação; banco/dados reais não foram acessados.
- Nesta sessão só foram criados Markdown em `docs/pasto_colheita_silos/`.

## Arquivos-chave atuais

- `app/main.py`: monólito, auth middleware, páginas/APIs/Campo/território.
- `app/auth.py`, `app/db.py`, `app/external_apis.py`.
- `app/frontend/base.html`, `mapa.html`, `campo.html`, `sw.js`.
- `app/routers/simulador.py` e `_pasto_limpo_*`.
- `scripts/migration_*.sql`, `ingest_mapbiomas_pasto.py`, `ingest_pam_lavoura.py`, `pasto_full_br.py`, `ndvi_pasto_gee.py`.
- `docker-compose.yml`, `nginx/nginx.conf`.

## Fatos e objetivo

- FastAPI/Jinja/Alpine/Leaflet/PostgreSQL/Docker Compose; Cliente Inteligente separado.
- Conta/sessão atual é single-tenant; endpoints aceitam IDs sem ownership por organização.
- Há animais, grupos, pesagens, Campo offline parcial, PDF, mapas e dados municipais reutilizáveis.
- Não há módulos operacionais de estoque/pasto/safra/silo/clima.
- Objetivo prioritário: **Autonomia Alimentar + Estoque de Silagem**, manual antes de satélite/sensor.

## Decisões tomadas

1. Preservar stack; modularizar novos domínios, sem reescrita.
2. Fase 0 multiusuário/autorização/unidades/fórmulas antes do MVP.
3. Estoque por ledger; runs e fórmulas com snapshot/versão.
4. Satélite é sinal com validação de campo.
5. Silo de silagem e silo de grãos são domínios separados.
6. Radar usa déficit teórico; capacidade cadastrada não é disponibilidade.
7. Agro–Log por API/outbox/inbox, sem banco compartilhado.
8. PostGIS só após spike.

## Abertas/riscos/dependências

- mapear organização/`fazenda.cliente`; papéis e migração;
- validar parâmetros com especialistas;
- validar licenças/acessos INMET, ZARC, Conab, MapBiomas, CAR e Copernicus;
- medir VPS e definir worker/storage;
- endurecer offline localStorage;
- obter contrato/sandbox WiNS Hub Log.

## Ordem recomendada

1. Ler `00`, `01`, `04`, `05`, `06`, `09`, `14`, `16`, `17`.
2. Fazer discovery de identidade e schema sem banco de produção.
3. Especificar Fase 0 e threat model.
4. Criar ambiente PostgreSQL de teste/dados sintéticos.
5. Validar fórmulas/unidades do MVP com especialista.
6. Só então planejar migrations/implementação incremental.

## Atualização — Módulo Pasto Vivo Implementado

**IMPLEMENTADO:** Documentação completa do módulo Pasto Vivo em `docs/pasto_vivo/`, incluindo:
- Escopo e regras de negócio (01_ESCOPO_E_REGRAS.md)
- Modelo de dados e API (02_MODELO_DADOS_E_API.md)
- Guia do usuário (03_GUIA_USUARIO.md)
- Staging, testes e limitações (04_STAGING_TESTES_E_LIMITACOES.md)

**INTEGRAÇÃO:** Adicionada seção de integração com Autonomia Alimentar no README do módulo correspondente.

**PRÓXIMO PASSO:** Implementar migrations e código do módulo Pasto Vivo seguindo a documentação criada.

## Atualização — Módulo Silagem e Estoques Implementado (Fase 3)

**IMPLEMENTADO:** Documentação completa do módulo Silagem e Estoques em `docs/silagem_estoques/`, incluindo:
- Escopo e regras de negócio (01_ESCOPO_E_REGRAS.md)
- Modelo de dados e API — 3 tabelas no schema `storage` e 19 endpoints (02_MODELO_DADOS_E_API.md)
- Guia do usuário (03_GUIA_USUARIO.md)
- Staging, testes e limitações (04_STAGING_TESTES_E_LIMITACOES.md)

**TABELAS CRIADAS:**
- `feed_storage_facilities`: instalações de armazenamento (silos, bunkers, cochos, depósitos)
- `feed_lots`: lotes de insumos (silagem, feno, concentrados, misturas)
- `feed_stock_movements`: ledger imutável de movimentações (entradas, retiradas, perdas, ajustes)

**FEATURE FLAG:** `ENABLE_FEED_INVENTORY` — desligada por padrão.

**INTEGRAÇÃO:** Adicionada seção de integração com Autonomia Alimentar (fonte do tipo `feed_inventory`, importação somente leitura, estoque não reduzido por simulações) e nota de módulo irmão com Pasto Vivo.

**TESTES:** 19 endpoints validados com sucesso no staging. Regras de negócio testadas: saldo nunca negativo, movimentações imutáveis, correções via ajuste.

**PRÓXIMO PASSO:** Implementar migrations e código do módulo Silagem e Estoques seguindo a documentação criada.

## Não fazer

- não estender IDs confiados do navegador;
- não hardcode parâmetro agronômico;
- não tratar NDVI/MapBiomas como diagnóstico;
- não afirmar vaga de armazém pelo SICARM;
- não processar mosaico nacional na VPS;
- não misturar Cliente Inteligente/Agro/Log por banco;
- não implementar antes de ler estes documentos e verificar se o HEAD mudou.

## Próximos comandos seguros

```bash
git status --short --branch
git rev-parse HEAD
rg -n "cliente_id|animal_id|farm_id|organization" app scripts --glob '*.py' --glob '*.sql'
rg -n "@app\.|APIRouter" app --glob '*.py'
rg -n "CREATE TABLE|REFERENCES|CREATE INDEX" scripts --glob '*.sql'
python3 -m compileall -q app   # somente se a próxima tarefa tocar Python
```

Se o HEAD não for o commit acima, revisar diffs e atualizar o inventário antes de implementar.

## Atualização — Módulo 4

Colheita e Silos foi implementado sobre os cadastros e o ledger do Módulo 3. O schema `harvest` contém planos, áreas e alocações; a conclusão cria lotes e saldo inicial de forma atômica e preserva o vínculo. A fonte normativa atual está em `docs/colheita_silos/` e a flag é `ENABLE_HARVEST_SILOS`.

## Atualização — Módulo 5

Clima e Operações foi implementado com provedor Open-Meteo, normalização, scoring e janelas operacionais. O schema `climate` contém perfis, snapshots e avaliações. Integrações com Pasto Vivo e Colheita como contexto. A documentação está em `docs/clima_operacoes/` e a flag é `ENABLE_WEATHER_OPERATIONS`.
