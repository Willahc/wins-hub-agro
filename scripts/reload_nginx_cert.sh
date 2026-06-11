#!/bin/bash
# Cron do host: recarrega o nginx quando o certbot renovou o cert (flag do deploy-hook).
# Reload é graceful (zero downtime) e re-lê os certs do mount de diretório.
# Belt-and-braces: com FORCE=1 (cron semanal) recarrega mesmo sem flag, p/ cobrir
# o caso do hook não disparar.
set -u
FLAG=/root/wins_agro_v1/certbot/conf/.nginx-reload-needed
LOG=/var/log/wins_backup.log
NGINX=$(docker ps --format '{{.Names}}' | grep nginx | head -1)
[ -z "$NGINX" ] && exit 0

if [ -e "$FLAG" ] || [ "${FORCE:-0}" = "1" ]; then
  if docker exec "$NGINX" nginx -s reload 2>>"$LOG"; then
    rm -f "$FLAG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] nginx recarregado (cert)$([ "${FORCE:-0}" = "1" ] && echo ' [forçado]')" >> "$LOG"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERRO ao recarregar nginx" >> "$LOG"
  fi
fi
