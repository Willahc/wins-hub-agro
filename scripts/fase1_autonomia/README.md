# Autonomia Alimentar — README

## Visão geral

Módulo de Autonomia Alimentar que permite ao produtor responder:

1. Quanto de matéria seca meu rebanho consome por dia?
2. Quanto alimento efetivamente tenho disponível?
3. Por quantos dias esse estoque sustenta o rebanho?
4. Quanto falta para atingir minha meta de autonomia?
5. Quais fontes de alimento representam meu estoque?
6. O que acontece se eu alterar rebanho, peso, consumo ou estoque?
7. Quais cenários já foram calculados para a fazenda?

## Estrutura

```
scripts/fase1_autonomia/
  001_food_autonomy_schema.sql      -- Schema (4 tabelas)
  002_food_autonomy_grants.sql      -- Grants de segurança
  090_food_autonomy_seed_staging.sql -- Dados sintéticos
  099_food_autonomy_down.sql        -- Rollback
  apply_staging.sh                  -- Aplica migration no staging
  test_http.sh                      -- Testes HTTP de integração
  test_ui.sh                        -- Testes de interface

app/domain/food_autonomy.py         -- Fórmulas (Decimal puro)
app/repositories/food_autonomy.py   -- Acesso a dados
app/services/food_autonomy.py       -- Lógica de negócio
app/schemas/food_autonomy.py        -- Validação Pydantic
app/routers/food_autonomy.py        -- API endpoints

app/frontend/autonomia_alimentar.html -- Interface web

app/tests/test_fase1_food_autonomy_domain.py
app/tests/test_fase1_food_autonomy_service.py
app/tests/test_fase1_food_autonomy_api.py
app/tests/test_fase1_food_autonomy_security.py
app/tests/test_fase1_food_autonomy_staging.py
```

## Feature Flag

```bash
ENABLE_FOOD_AUTONOMY=true  # ativa o módulo
```

- Default: `false` (desligado)
- Produção: nunca ativar sem revisão
- Staging: ativar explicitamente

## Iniciar staging

```bash
# 1. Iniciar staging da Fase 0D
bash scripts/fase0d/start_staging.sh

# 2. Aplicar migration do módulo
bash scripts/fase1_autonomia/apply_staging.sh

# 3. Ativar feature flag no compose de staging
# Adicione ENABLE_FOOD_AUTONOMY=true no environment do docker-compose.staging.yml

# 4. Reiniciar a API de staging
docker compose -p wins_agro_fase0d -f scripts/fase0d/docker-compose.staging.yml restart api
```

## Testes

```bash
# Todos os testes
python3 -m unittest discover -s app/tests -p 'test_fase1_food_autonomy_*.py' -v

# Apenas domínio
python3 -m unittest app/tests/test_fase1_food_autonomy_domain.py -v

# HTTP (staging ligado)
STAGING_TEST=1 bash scripts/fase1_autonomia/test_http.sh

# UI (staging ligado)
STAGING_TEST=1 bash scripts/fase1_autonomia/test_ui.sh
```

## Fórmulas

- **Demanda**: `cabeças × peso_médio_kg × (consumo_% / 100)`
- **Pastagem**: `área_ha × kg_MS/ha × (utilização_% / 100)`
- **Estoque**: `quantidade_kg × (MS_% / 100) × (aproveitamento_% / 100)`
- **Autonomia**: `MS_utilizado / demanda_diária`
- **Status**: crítico (< 50% meta), atenção (50–100%), adequado (≥ 100%)

## Limitações

- Cálculo assume consumo constante (sem variação sazonal)
- Não substitui avaliação nutricional ou agronômica
- Dados são manuais (sem integração com sensores)
- Sem alertas automáticos por WhatsApp/e-mail
