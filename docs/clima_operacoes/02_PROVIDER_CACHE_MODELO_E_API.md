# Provider, Cache, Modelo de Dados e API

## Provider

### Open-Meteo (Padrão)
- URL: `https://api.open-meteo.com/v1/forecast`
- Gratuito, sem chave de API
- Dados: temperatura, umidade, chuva, vento, rajadas, nuvens
- Rate limit: 10.000 req/dia

### Configuração
```env
ENABLE_WEATHER_OPERATIONS=true
WEATHER_PROVIDER=open-meteo
WEATHER_API_BASE_URL=https://api.open-meteo.com/v1/forecast
WEATHER_API_KEY=
WEATHER_TIMEOUT_SECONDS=10
WEATHER_CACHE_CURRENT_MINUTES=20
WEATHER_CACHE_HOURLY_MINUTES=45
WEATHER_CACHE_DAILY_MINUTES=120
WEATHER_FALLBACK_MAX_AGE_HOURS=12
```

## Cache

- **Persistente**: snapshots armazenados no PostgreSQL
- **FRESH**: < 30 minutos
- **STALE**: 30-180 minutos (ainda exibe, marca como desatualizado)
- **FALLBACK**: 180-720 minutos (usa cache antigo com aviso)
- **UNAVAILABLE**: > 720 minutos (sem dados)

## Modelo de Dados

### Schema: `climate`

#### `farm_weather_profiles`
- `public_id` (UUID)
- `latitude`, `longitude` (coordenadas)
- `timezone` (fuso horário)
- `provider` (provedor)
- `enabled` (ativo/inativo)
- `status` (active/stale/error/disabled/not_configured)

#### `weather_snapshots`
- `snapshot_type` (current/hourly_forecast/daily_forecast/recent_history)
- `payload_normalized` (JSONB com dados normalizados)
- `fetched_at`, `expires_at`, `stale_after`
- `checksum` (integridade)

#### `operational_window_evaluations`
- `window_type` (harvest_cut/ensiling/haymaking/pasture_management/field_operation/heat_attention)
- `score` (0-100)
- `classification` (favorable/attention/unfavorable/insufficient_data)
- `positive_factors`, `risk_factors` (JSONB)

## API

### Endpoints
```
GET  /profile                           - Perfil climático
PUT  /profile                           - Criar/atualizar perfil
GET  /current                           - Condição atual
GET  /forecast/hourly                   - Previsão horária
GET  /forecast/daily                    - Previsão diária
GET  /rainfall/recent                   - Chuva recente
POST /refresh                           - Forçar atualização
GET  /operational-windows               - Janelas operacionais
GET  /dashboard                         - Dashboard completo
POST /evaluations                       - Salvar avaliação
GET  /evaluations                       - Listar avaliações
GET  /pasture-context                   - Contexto para Pasto Vivo
GET  /harvest-plans/{plan_uuid}/weather-context - Contexto para Colheita
```

### Normalização
- Temperatura: °C
- Precipitação: mm
- Vento: km/h
- Umidade: %
- Versão: `weather_normalization.v1`
