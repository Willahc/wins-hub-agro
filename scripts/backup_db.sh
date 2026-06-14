#!/bin/bash
# Backup diário do Postgres (wins_agro) — chamado pelo cron do host.
# Dump custom-format (pg_dump -Fc) -> /root/backups_db, rotação de 14 dias,
# verificação de sanidade (tamanho mínimo) e log em /var/log/wins_backup.log.
# Offsite: se OFFSITE_TARGET estiver definido (ex.: user@host:/path), faz scp.
# CIFRADO: o dump é cifrado p/ a chave pública 'WiNS Backup' (GPG) e o plaintext é
#   apagado (shred). A chave PRIVADA fica OFFSITE — sem ela, nenhum .gpg é legível.
# RESTORE:  gpg --decrypt arquivo.dump.gpg | docker exec -i <db> pg_restore -U postgres -d wins_agro
#   (precisa da chave privada importada; chave pública em scripts/wins_backup_pubkey.asc).
set -u -o pipefail

DEST=/root/backups_db
LOG=/var/log/wins_backup.log
KEEP_DAYS=14
MIN_BYTES=10000000   # dump são ~44MB; menos de 10MB = algo errado
OFFSITE_TARGET="${OFFSITE_TARGET:-}"   # ex.: william@187.127.253.42:/home/william/backups_agro
# Cifra ASSIMÉTRICA do backup (chave pública no servidor; PRIVADA fica OFFSITE). Assim,
# servidor comprometido ou backup roubado = .gpg inútil sem a privada. Recipient = a chave
# 'WiNS Backup'. Se a chave pública não estiver no keyring, NÃO faz backup em claro (fail-safe).
GPG_RECIPIENT="${GPG_RECIPIENT:-backup@winshubagro.cloud}"

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

# --- CIFRAGEM (assimétrica) — o plaintext NUNCA fica em repouso ---
# fail-safe: sem a chave pública no keyring, aborta e remove o plaintext (não guarda em claro).
if ! gpg --list-keys "$GPG_RECIPIENT" >/dev/null 2>&1; then
  say "ERRO: chave pública '$GPG_RECIPIENT' ausente no keyring — backup ABORTADO (não guardo em claro)"
  shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
  exit 1
fi
ENC="$FILE.gpg"
if ! gpg --batch --yes --trust-model always --encrypt --recipient "$GPG_RECIPIENT" --output "$ENC" "$FILE" 2>>"$LOG"; then
  say "ERRO: cifragem GPG falhou ($FILE) — backup ABORTADO"
  shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
  rm -f "$ENC"
  exit 1
fi
chmod 600 "$ENC"
shred -u "$FILE" 2>/dev/null || rm -f "$FILE"   # apaga o dump em claro
FILE="$ENC"                                      # daqui pra frente, só o cifrado existe
ENCSIZE=$(stat -c%s "$FILE")

# rotação: remove backups locais (claro legado OU cifrado) com mais de KEEP_DAYS dias
find "$DEST" -name 'wins_agro_*.dump*' -mtime +"$KEEP_DAYS" -delete

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
