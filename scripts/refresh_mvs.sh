#!/usr/bin/env bash
# Refresh das materialized views quentes do Hub. Corrige a defasagem em que a MV
# fica com menos linhas que a fonte (ex: fazenda_nacional 200.489 vs lead_decisor
# 227.516) por nunca ter refresh agendado. Idempotente; logar a saída.
# Cron sugerido (crontab do host, fora do horário comercial):
#   30 4 * * *  /root/wins_agro_v1/scripts/refresh_mvs.sh >> /var/log/wins_refresh_mvs.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
set -a && . ./.env && set +a
export PGPASSWORD="$POSTGRES_PASSWORD"

MVS=(
  prospeccao.fazenda_nacional
  prospeccao.lead_demanda
  prospeccao.territorio_oportunidade
  prospeccao.tecnico_carteira
)
for mv in "${MVS[@]}"; do
  echo "$(date -Iseconds) REFRESH $mv"
  psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
    -c "REFRESH MATERIALIZED VIEW $mv;" || echo "  (falhou — segue p/ próxima)"
done
echo "$(date -Iseconds) refresh concluído"
