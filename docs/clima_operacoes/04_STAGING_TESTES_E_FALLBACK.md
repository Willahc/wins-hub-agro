# Staging, Testes e Fallback

## Staging

### Aplicar Migration
```bash
bash scripts/fase5_clima_janelas/apply_staging.sh
```

### Variáveis de Ambiente (Staging)
```env
ENABLE_WEATHER_OPERATIONS=true
WEATHER_PROVIDER=open-meteo
WEATHER_API_BASE_URL=https://api.open-meteo.com/v1/forecast
WEATHER_TIMEOUT_SECONDS=10
WEATHER_CACHE_CURRENT_MINUTES=20
WEATHER_CACHE_HOURLY_MINUTES=45
WEATHER_CACHE_DAILY_MINUTES=120
WEATHER_FALLBACK_MAX_AGE_HOURS=12
```

## Testes HTTP
```bash
STAGING_TEST=1 bash scripts/fase5_clima_janelas/test_http.sh
```

Valida:
- 401 sem autenticação
- Login
- Perfil
- Condição atual
- Previsão horária e diária
- Chuva recente
- Dashboard
- Janelas operacionais
- Refresh e cooldown
- Cross-tenant
- Contexto Pasto Vivo
- Contexto Colheita

## Testes UI
```bash
STAGING_TEST=1 bash scripts/fase5_clima_janelas/test_ui.sh
```

Valida:
- Página carrega
- Menu existe
- Alpine.js integrado
- Assets CSS

## Testes Unitários
```bash
cd app && python -m pytest tests/test_fase5_weather_operations_*.py -v
```

## Fallback

### Provider Indisponível com Cache Válido
- Usa cache existente (até 12 horas)
- Marca `cache_status: "fallback"`
- Exibe aviso de dados desatualizados

### Provider Indisponível sem Cache
- Retorna estado de indisponibilidade
- Não inventa dados
- Não causa erro 500

### Circuit Breaker
- Após 5 falhas consecutivas, abre circuito por 5 minutos
- Bloqueia chamadas externas temporariamente
- Registra evento de auditoria
