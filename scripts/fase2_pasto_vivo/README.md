# Pasto Vivo — README

## Visão geral

Módulo de Pasto Vivo que permite ao produtor:

1. Gerenciar piquetes com espécie, cultivar, área e alvos de manejo.
2. Registrar medições de pastagem (altura, kg MS/ha, utilização).
3. Rastrear ciclos de pastejo e descanso (início, fim, duração).
4. Monitorar status visual de cada piquete (pronto, pastejando, descanso, atenção).
5. Calcular estoque de MS disponível e utilizável por piquete.
6. Alimentar fontes de autonomia alimentar com dados de pastagem real.
7. Receber alertas quando piquetes ficam abaixo da altura de entrada.

## Estrutura

```
scripts/fase2_pasto_vivo/
  001_pasture_schema.sql          -- Schema (3 tabelas)
  002_pasture_grants.sql          -- Grants de segurança
  090_pasture_seed_staging.sql    -- Dados sintéticos
  099_pasture_down.sql            -- Rollback
  apply_staging.sh                -- Aplica migration no staging
  test_http.sh                    -- Testes HTTP de integração
  test_ui.sh                      -- Testes de interface

app/domain/pasture.py             -- Fórmulas de pastagem
app/repositories/pasture.py       -- Acesso a dados
app/services/pasture.py           -- Lógica de negócio
app/schemas/pasture.py            -- Validação Pydantic
app/routers/pasture.py            -- API endpoints

app/frontend/pasto_vivo.html      -- Interface web

app/tests/test_fase2_pasture_domain.py
app/tests/test_fase2_pasture_service.py
app/tests/test_fase2_pasture_api.py
app/tests/test_fase2_pasture_staging.py
```

## Feature Flag

```bash
ENABLE_PASTURE_LIVE=true  # ativa o módulo
```

- Default: `false` (desligado)
- Produção: nunca ativar sem revisão
- Staging: ativar explicitamente

## Iniciar staging

```bash
# 1. Iniciar staging da Fase 0D
bash scripts/fase0d/start_staging.sh

# 2. Aplicar migration do módulo
bash scripts/fase2_pasto_vivo/apply_staging.sh

# 3. Ativar feature flag no compose de staging
# Adicione ENABLE_PASTURE_LIVE=true no environment do docker-compose.staging.yml

# 4. Reiniciar a API de staging
docker compose -p wins_agro_fase0d -f scripts/fase0d/docker-compose.staging.yml restart api
```

## Testes

```bash
# Todos os testes
python3 -m unittest discover -s app/tests -p 'test_fase2_pasture_*.py' -v

# Apenas domínio
python3 -m unittest app/tests/test_fase2_pasture_domain.py -v

# HTTP (staging ligado)
STAGING_TEST=1 bash scripts/fase2_pasto_vivo/test_http.sh

# UI (staging ligado)
STAGING_TEST=1 bash scripts/fase2_pasto_vivo/test_ui.sh
```

## Fórmulas

- **MS total**: `área_ha × kg_MS/ha`
- **MS utilizável**: `MS_total × (utilização_% / 100)`
- **Status**: pasto vivo baseado na altura atual vs. alvos de entrada/saída
- **Ciclo pastejo**: `data_fim - data_início = dias_pastejo`
- **Ciclo descanso**: `data_prevista_fim - data_início = dias_descanso`

## Status dos piquetes

| Status | Descrição |
|--------|-----------|
| `ready` | Pronto para entrar — altura acima do alvo de entrada |
| `grazing` | Em pastejo ativo |
| `resting` | Em descanso — aguardando rebrote |
| `attention` | Atenção — abaixo da altura de entrada |
| `unavailable` | Indisponível (manejo, reforma, etc.) |
| `inactive` | Inativo |
| `no_measurement` | Sem medição registrada |

## Limitações

- Medições são manuais (sem integração com drones/sensores)
- Não modela variação de crescimento por estação
- Não inclui predição de rebrote
- Sem alertas automáticos por WhatsApp/e-mail
