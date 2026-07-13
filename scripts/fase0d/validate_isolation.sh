#!/usr/bin/env bash
# validate_isolation.sh — Garante o isolamento absoluto de staging em relação à produção
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/scripts/fase0d/docker-compose.staging.yml"
STAGING_ENV="/root/.config/wins_agro/fase0d/staging.env"

echo "=== Validação de Isolamento (Fase 0D) ==="

# 1. Verifica se staging.env possui hosts ou senhas reais
echo -n "Teste 1: Verificando env de staging (sem secrets de produção)... "
if grep -q "POSTGRES_PASSWORD=.*[A-Za-z0-9]\{20\}" "$STAGING_ENV" || grep -q "db:5432" "$STAGING_ENV"; then
    echo "FALHA (Contém padrões de produção)"
    exit 1
else
    echo "OK"
fi

# 2. Verifica se o compose usa volumes ou redes de produção
echo -n "Teste 2: Verificando volumes e redes do docker-compose.staging.yml... "
if grep -q "pgdata" "$COMPOSE_FILE" || grep -q "wins_agro_v1" "$COMPOSE_FILE" || grep -q "external:" "$COMPOSE_FILE"; then
    echo "FALHA (Referência a volumes ou redes externas de produção detectada)"
    exit 1
else
    echo "OK"
fi

# 3. Verifica se a API de staging publica alguma porta do PostgreSQL
echo -n "Teste 3: Verificando exposição do PostgreSQL de staging... "
if docker inspect wins_agro_fase0d_db --format='{{range $p, $conf := .HostConfig.PortBindings}}{{$p}}{{end}}' | grep -q "5432"; then
    echo "FALHA (PostgreSQL exposto no Host)"
    exit 1
else
    echo "OK (PostgreSQL não publica portas)"
fi

# 4. Verifica se a API escuta somente em localhost (127.0.0.1)
echo -n "Teste 4: Verificando endereço de escuta da API de staging... "
binding=$(docker inspect wins_agro_fase0d_api --format='{{range $p, $conf := .HostConfig.PortBindings}}{{range $conf}}{{.HostIp}}{{end}}{{end}}')
if [[ "$binding" == "127.0.0.1" ]]; then
    echo "OK (API binded a 127.0.0.1)"
else
    echo "FALHA (API escutando em $binding em vez de 127.0.0.1)"
    exit 1
fi

echo "=========================================================="
echo "ISOLAMENTO DE STAGING VALIDADO COM SUCESSO!"
echo "=========================================================="
