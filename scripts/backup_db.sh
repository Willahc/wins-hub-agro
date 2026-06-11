#!/bin/bash
# Backup diário do Postgres (wins_agro) — chamado pelo cron do host.
# Dump custom-format (pg_dump -Fc) -> /root/backups_db, rotação de 14 dias,
# verificação de sanidade (tamanho mínimo) e log em /var/log/wins_backup.log.
# Offsite: se OFFSITE_TARGET estiver definido (ex.: user@host:/path), faz scp.
set -u -o pipefail

DEST=/root/backups_db
LOG=/var/log/wins_backup.log
KEEP_DAYS=14
MIN_BYTES=10000000   # dump são ~44MB; menos de 10MB = algo errado
OFFSITE_TARGET="${OFFSITE_TARGET:-}"   # ex.: william@187.127.253.42:/home/william/backups_agro

mkdir -p "$DEST"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
say() { echo "[$(ts)] $*" >> "$LOG"; }

DB_CONT=$(docker ps --format '{{.Names}}' | grep db | head -1)
if [ -z "$DB_CONT" ]; then
  say "ERRO: container do db não encontrado — backup NÃO feito"
  exit 1
fi

FILE="$DEST/wins_agro_$(date +%Y%m%d_%H%M%S).dump"
if ! docker exec "$DB_CONT" pg_dump -U postgres -Fc wins_agro > "$FILE" 2>>"$LOG"; then
  say "ERRO: pg_dump falhou ($FILE)"
  rm -f "$FILE"
  exit 1
fi

chmod 600 "$FILE"   # dump contém PII (leads) — só root lê

SIZE=$(stat -c%s "$FILE")
if [ "$SIZE" -lt "$MIN_BYTES" ]; then
  say "ERRO: dump suspeito de incompleto (${SIZE} bytes) — mantido p/ inspeção: $FILE"
  exit 1
fi

# rotação: remove dumps locais com mais de KEEP_DAYS dias
find "$DEST" -name 'wins_agro_*.dump' -mtime +"$KEEP_DAYS" -delete

if [ -n "$OFFSITE_TARGET" ]; then
  # garante o diretório remoto (user@host:/path -> ssh user@host mkdir -p /path)
  ssh -o BatchMode=yes -o ConnectTimeout=15 "${OFFSITE_TARGET%%:*}" "mkdir -p '${OFFSITE_TARGET#*:}'" >> "$LOG" 2>&1
  if scp -o BatchMode=yes -o ConnectTimeout=15 "$FILE" "$OFFSITE_TARGET/" >> "$LOG" 2>&1; then
    say "OK: $FILE (${SIZE} bytes) + offsite $OFFSITE_TARGET"
  else
    say "AVISO: dump local OK ($FILE, ${SIZE} bytes) mas OFFSITE FALHOU ($OFFSITE_TARGET)"
  fi
else
  say "OK: $FILE (${SIZE} bytes) — offsite não configurado"
fi
