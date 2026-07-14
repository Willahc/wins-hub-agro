# Clima e Janelas Operacionais — Módulo 5

Visão geral do módulo de clima e janelas operacionais do WiNS Hub Agro.

## Escopo

- Configuração climática por fazenda (coordenadas, timezone, provider)
- Consulta ao provedor Open-Meteo (gratuito, sem chave)
- Cache persistente com fallback
- Condição atual, previsão horária e diária
- Chuva acumulada recente
- Janelas operacionais explicáveis (corte, ensilagem, fenação, pastagem, campo, calor)
- Dashboard unificado
- Integração com Pasto Vivo (contexto sem alteração automática)
- Integração com Colheita e Silos (contexto sem alteração de planos)
- Feature flag `ENABLE_WEATHER_OPERATIONS`
- API REST sob `/api/v2/farms/{farm_uuid}/weather-operations/`
- Frontend em `/clima-operacoes`

## Arquitetura

```
app/
  domain/weather_operations.py      # Cálculos puros, normalização, score, janelas
  integrations/weather_provider.py  # Adapter HTTP (Open-Meteo), circuit breaker
  repositories/weather_operations.py # PostgreSQL (profiles, snapshots, evaluations)
  services/weather_operations.py    # Orquestração: auth, cache, provider, cálculos
  schemas/weather_operations.py     # Pydantic request/response
  routers/weather_operations.py     # Endpoints FastAPI
  frontend/clima_operacoes.html     # Dashboard integrado
scripts/fase5_clima_janelas/        # Migrations SQL, seeds, testes HTTP/UI
```

## Limitações

- Não altera planos de colheita automaticamente
- Não altera estado de piquetes automaticamente
- Não cria ou movimenta estoques automaticamente
- Não emite recomendações agronômicas definitivas
- Provider Open-Meteo é gratuito mas tem resolução limitada
- Não substitui estação meteorológica física
