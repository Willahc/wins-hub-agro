# Autonomia Alimentar — Runbook do Staging

## Pré-requisitos

- Docker e Docker Compose instalados
- Porta 18080 livre
- Scripts da Fase 0D disponíveis

## Iniciar

```bash
# 1. Iniciar staging base (Fase 0D)
bash scripts/fase0d/start_staging.sh

# 2. Aplicar migration do módulo
bash scripts/fase1_autonomia/apply_staging.sh

# 3. Ativar feature flag
# Adicione ao docker-compose.staging.yml:
#   environment:
#     ENABLE_FOOD_AUTONOMY: "true"

# 4. Reiniciar API
docker compose -p wins_agro_fase0d -f scripts/fase0d/docker-compose.staging.yml restart api
```

## Verificar

```bash
# Status
docker compose -p wins_agro_fase0d -f scripts/fase0d/docker-compose.staging.yml ps

# Health
curl http://127.0.0.1:18080/healthz

# Página
curl -b cookies.txt http://127.0.0.1:18080/autonomia-alimentar
```

## Parar

```bash
bash scripts/fase0d/stop_staging.sh
```

## Testar

```bash
# HTTP
STAGING_TEST=1 bash scripts/fase1_autonomia/test_http.sh

# UI
STAGING_TEST=1 bash scripts/fase1_autonomia/test_ui.sh
```

## Logs

```bash
docker logs wins_agro_fase0d_api --tail 50
docker logs wins_agro_fase0d_db --tail 50
```

## Troubleshooting

| Problema | Solução |
|---|---|
| Migration falha | Verifique se o container do DB está rodando |
| 401 nos endpoints | Faça login primeiro via /api/login |
| Página não aparece | Verifique se ENABLE_FOOD_AUTONOMY=true |
| Cálculo errado | Verifique os dados de entrada |
