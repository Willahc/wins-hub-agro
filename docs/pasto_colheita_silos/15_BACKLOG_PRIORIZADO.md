# Backlog priorizado

Tamanhos XS/S/M/L/XL são relativos. Não são prazo. Cada fase exige discovery, desenho, implementação, testes, rollout e documentação.

## Fase 0 — Fundações (L)

- **Objetivo/valor:** permitir múltiplas organizações/fazendas sem vazamento e criar base explicável.
- **Dependências:** inventário/mapeamento do schema, papéis e processo de migração; ambiente de teste PostgreSQL.
- **Escopo:** user/org/membership/farm, policy/ActorContext, auditoria transacional, unidades, fontes, fórmula/parâmetro/versionamento, repositories, feature flag.
- **Fora:** módulos de alimento/clima/satélite.
- **Dados/tabelas:** identity + farm mapping, `data_source`, `formula_*`, `audit_event`, `job_run`.
- **Telas/APIs:** seleção de contexto, membros/papéis, parâmetros; `/api/v1/me`, organizations/farms.
- **Segurança:** IDOR, revogação, sessão, export/anexo e admin time-bound.
- **Testes/aceite:** matriz tenant A/B em toda rota nova; audit e mutação atômicos; unidade/fórmula reproduzível; backup/restore em staging.
- **Risco:** mapear `fazenda.cliente` incorretamente; mitigar com tabela de correspondência e rollout sem renomeação destrutiva.

## Fase 1 — MVP autonomia alimentar (L)

- **Objetivo/valor:** dias de autonomia, déficit e cenários usando dados manuais/rebanho atual.
- **Dependências:** Fase 0 e validação técnico-zootécnica.
- **Escopo:** feed items/locations/ledger, demanda de lotes, pasto manual, silagem/feno/suplemento, balanço diário, cenário, alerta, PDF, capturas offline mínimas.
- **Fora:** satélite, sensor, dieta ótima, compra integrada.
- **Dados:** `feed_*`, `pasture_assessment`, `feed_balance_run`, `scenario`, alertas.
- **Telas/APIs:** wizard Autonomia, Estoques, Visão geral, Cenários, Alertas e Campo.
- **Segurança:** ajuste com alçada, idempotência, partição offline e export.
- **Testes/aceite:** golden cases, conservação de massa, tenant A/B, replay/conflito offline e PDF reproduzível.
- **Risco/esforço/valor:** L; alto valor e risco de unidade/parâmetro. Pilotar em shadow mode.

## Fase 2 — Clima (M)

- **Objetivo/valor:** contexto climático confiável e alertas de chuva/seca/calor.
- **Dependências:** adapters/fontes validados, geolocalização e jobs.
- **Escopo:** estação/grade, observações/previsões, chuva/dias secos/temperatura/THI, freshness e fallback.
- **Fora:** previsão própria e automação de manejo.
- **Dados:** `weather_station`, observation/forecast, `climate_metric`.
- **Telas/APIs:** card climático, histórico e fonte; endpoints por fazenda/ponto.
- **Segurança:** coordenada minimizada; allowlist/segredo de adapters.
- **Testes/aceite:** timezone, faltantes, estação versus grade, forecast runs, source outage e cache.
- **Risco/esforço/valor:** M; fonte instável e falsa precisão; valor transversal.

## Fase 3 — Piquetes e Pasto Vivo (XL)

- **Objetivo/valor:** histórico espacial e priorização de validação em campo.
- **Dependências:** Fases 0/2, spike PostGIS, Copernicus/licença e método de campo.
- **Escopo:** polígonos/versionamento, área, observações/fotos, série Sentinel-2, vigor/anomalia/tendência/confiança e alertas.
- **Fora:** diagnóstico definitivo e processamento nacional.
- **Dados:** boundaries/fields/paddocks, observations, scenes/indices/derivatives.
- **Telas/APIs:** editor/mapa, detalhe temporal, comparação, captura Campo.
- **Segurança:** ownership espacial/anexo; nenhum bbox/export cruza tenant.
- **Testes/aceite:** geometria/CRS, baixa cobertura/nuvem, mudança de polígono, linguagem e validação de campo.
- **Risco/esforço/valor:** XL; alto risco científico/operacional, alto valor após calibrado.

## Fase 4 — Colheita e silagem (L)

- **Objetivo/valor:** planejar janela/capacidade e fechar ciclo até estoque de silagem.
- **Dependências:** clima, safra/talhão, MVP de estoque e recursos.
- **Escopo:** planting/harvest plan, graus-dia/observação, máquina/transporte/recepção, viagens, silo/batch/retirada.
- **Fora:** controle de máquina e contratação automática.
- **Dados:** crop/season/planting/harvest/resources/plan, silage silo/batch.
- **Telas/APIs:** Safra, Janela, Plano diário, Silo de silagem.
- **Segurança:** aprovação/versionamento, recursos e custos escopados.
- **Testes/aceite:** faixa/gargalo, forecast version, balanço massa, concorrência e integração com autonomia.
- **Risco/esforço/valor:** L; qualidade das entradas operacionais; alto valor sazonal.

## Fase 5 — Silos de grãos (XL)

- **Objetivo/valor:** rastreabilidade, qualidade, perda e custo por lote.
- **Dependências:** Fase 0, ledger maduro, processo operacional e especialistas.
- **Escopo:** unidade/lote/movimento, umidade/impureza/temperatura, inspeção, secagem, aeração, FIFO, perda/custo/inventário.
- **Fora:** automação de hardware e negociação de commodities.
- **Dados:** `grain_*`, inspection/drying/aeration/loss.
- **Telas/APIs:** resumo, lote, ledger, inspeção, agenda e export.
- **Segurança:** alçada/bloqueio/segregação e anexos.
- **Testes/aceite:** peso corrigido, ledger concorrente, FIFO/exceção, capacidade e tenant.
- **Risco/esforço/valor:** XL; regras de umidade/custeio e operação física complexas.

## Fase 6 — Armazenagem regional (L)

- **Objetivo/valor:** encontrar unidades e contextualizar pressão teórica municipal/regional.
- **Dependências:** Conab/licença/método, SIDRA/PAM, geodados e roteamento.
- **Escopo:** external warehouses, capacidade cadastrada, serviços, distância, indicadores municipais/radar.
- **Fora:** disponibilidade real sem parceiro e reserva.
- **Dados:** `external_warehouse`, `municipal_indicator`, `regional_storage_indicator`.
- **Telas/APIs:** Armazéns próximos, Radar, Inteligência municipal.
- **Segurança:** contatos/minimização e separação público/privado.
- **Testes/aceite:** anos/fontes, “teórico”, sem inferir ocupação, cache/versionamento.
- **Risco/esforço/valor:** L; atualização/licença e identidade de unidades.

## Fase 7 — Integração Log (XL)

- **Objetivo/valor:** custo/capacidade/viagens e fluxo Agro→Log sem acoplamento de banco.
- **Dependências:** contrato e sandbox Log, identidade de serviço e governança.
- **Escopo:** request/options/status, outbox/inbox, cotação e confirmação.
- **Fora:** marketplace automático/telemetria detalhada inicialmente.
- **Dados:** integration outbox/inbox e referências/snapshots.
- **Telas/APIs:** opções logísticas no plano, status e ação autorizada.
- **Segurança:** assinatura/replay/consentimento/minimização.
- **Testes/aceite:** contract tests, duplicata/outage/version mismatch e isolamento.
- **Risco/esforço/valor:** XL; dependência organizacional externa, valor de rede no longo prazo.

## Backlog transversal ordenado

1. **P0/L:** threat model + identidade/tenant/policies.
2. **P0/M:** banco de teste e pipeline seguro de migrations futuras.
3. **P0/M:** catálogo de unidades/fonte/fórmula/parâmetros.
4. **P0/M:** repositories novos e auditoria atômica.
5. **P1/L:** ledger de alimento e motor puro do MVP.
6. **P1/M:** wizard/visão/PDF e alertas.
7. **P1/M:** IndexedDB/partition para operações MVP.
8. **P2/M:** adapters de clima + job runner.
9. **P3/M:** spike espacial/PostGIS/Copernicus.
10. **P3/XL:** Pasto Vivo calibrado.

P0/P1 indicam prioridade, não prazo.

## Gates entre fases

Uma fase só avança quando isolamento, unidade, proveniência, recuperação de falha, testes e observabilidade do domínio anterior estiverem aceitos. Fonte externa nova entra atrás de feature flag e não se torna dependência única até demonstrar estabilidade.
