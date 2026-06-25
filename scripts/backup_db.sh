#!/bin/bash
# Backup diário do Postgres (wins_agro) — chamado pelo cron do host.
# Dump custom-format (pg_dump -Fc) -> /root/backups_db, rotação de 14 dias,
# verificação de sanidade (tamanho mínimo) e log em /var/log/wins_backup.log.
# Offsite: se OFFSITE_TARGET estiver definido (ex.: user@host:/path), faz scp.
# CIFRADO: o dump é cifrado p/ a chave pública 'WiNS Backup' (GPG) e o plaintext é
#   apagado (shred). A chave PRIVADA fica OFFSITE — sem ela, nenhum .gpg é legível.
# RESTORE:  gpg --decrypt arquivo.dump.gpg | docker exec -i <db> pg_restore -U postgres -d wins_agro
#   (precisa da chave privada importada; chave pública em scripts/wins_backup_pubkey.asc).
#
# CONFIG/ALERTA: variáveis podem vir do ambiente (cron) OU de /root/wins_agro_v1/.backup_env
# (chmod 600). Alertas são OPT-IN (nada de endpoint hardcoded):
#   OFFSITE_TARGET : destino do scp (user@host:/path). Vazio = ALERTA (esperamos offsite).
#   ALERT_WEBHOOK  : URL p/ POST JSON em FALHA (Slack/Discord/Google Chat/Mattermost…).
#   HEARTBEAT_URL  : dead-man's switch — ping em SUCESSO, /fail em falha (healthchecks.io
#                    etc.). Pega ATÉ o caso "o cron nem rodou" — que só o log não pega.
set -u -o pipefail

CFG=/root/wins_agro_v1/.backup_env
# shellcheck disable=SC1090
[ -f "$CFG" ] && . "$CFG"

DEST=/root/backups_db
LOG=/var/log/wins_backup.log
KEEP_DAYS=14
MIN_BYTES=10000000   # dump cifrado ~440MB; menos de 10MB = algo muito errado
OFFSITE_TARGET="${OFFSITE_TARGET:-}"   # ex.: william@187.127.253.42:/home/william/backups_agro
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
HEARTBEAT_URL="${HEARTBEAT_URL:-}"
# Cifra ASSIMÉTRICA do backup (chave pública no servidor; PRIVADA fica OFFSITE). Assim,
# servidor comprometido ou backup roubado = .gpg inútil sem a privada. Recipient = a chave
# 'WiNS Backup'. Se a chave pública não estiver no keyring, NÃO faz backup em claro (fail-safe).
GPG_RECIPIENT="${GPG_RECIPIENT:-backup@winshubagro.cloud}"

mkdir -p "$DEST"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
say() { echo "[$(ts)] $*" >> "$LOG"; }

# notify ok|fail "mensagem" — dispara webhook (só em falha) e heartbeat (sempre que
# configurado). Best-effort: nunca derruba o backup se a notificação falhar.
notify() {
  local kind="$1"; shift; local msg="$*"
  if [ "$kind" = "fail" ] && [ -n "$ALERT_WEBHOOK" ]; then
    curl -fsS -m 15 -X POST -H 'Content-Type: application/json' \
         --data "{\"text\":\"[WiNS backup] $msg\",\"content\":\"[WiNS backup] $msg\"}" \
         "$ALERT_WEBHOOK" >/dev/null 2>>"$LOG" || say "AVISO: webhook de alerta falhou"
  fi
  if [ -n "$HEARTBEAT_URL" ]; then
    local u="$HEARTBEAT_URL"; [ "$kind" = "fail" ] && u="${HEARTBEAT_URL%/}/fail"
    curl -fsS -m 15 "$u" >/dev/null 2>>"$LOG" || true
  fi
}

DB_CONT=$(docker ps --format '{{.Names}}' | grep db | head -1)
if [ -z "$DB_CONT" ]; then
  say "ERRO: container do db não encontrado — backup NÃO feito"
  notify fail "container do db não encontrado — backup NÃO feito"
  exit 1
fi

FILE="$DEST/wins_agro_$(date +%Y%m%d_%H%M%S).dump"
# Exclui DADOS das tabelas de staging da RFB (cnpj.stg_*) — ~7GB de dados
# intermediários, re-geráveis do dump público da Receita. O SCHEMA (DDL) é mantido,
# só os dados saem; o restore recria as tabelas vazias e o pipeline de ingestão
# repopula. Isso reduz o dump de ~1.8GB de volta p/ ~0.4GB (e viabiliza o offsite).
if ! docker exec "$DB_CONT" pg_dump -U postgres -Fc \
       --exclude-table-data='cnpj.stg_*' \
       wins_agro > "$FILE" 2>>"$LOG"; then
  say "ERRO: pg_dump falhou ($FILE)"
  rm -f "$FILE"
  notify fail "pg_dump falhou"
  exit 1
fi

chmod 600 "$FILE"   # dump contém PII (leads) — só root lê

SIZE=$(stat -c%s "$FILE")
if [ "$SIZE" -lt "$MIN_BYTES" ]; then
  say "ERRO: dump suspeito de incompleto (${SIZE} bytes) — mantido p/ inspeção: $FILE"
  notify fail "dump suspeito de incompleto (${SIZE} bytes)"
  exit 1
fi

# --- CIFRAGEM (assimétrica) — o plaintext NUNCA fica em repouso ---
# fail-safe: sem a chave pública no keyring, aborta e remove o plaintext (não guarda em claro).
if ! gpg --list-keys "$GPG_RECIPIENT" >/dev/null 2>&1; then
  say "ERRO: chave pública '$GPG_RECIPIENT' ausente no keyring — backup ABORTADO (não guardo em claro)"
  shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
  notify fail "chave pública GPG '$GPG_RECIPIENT' ausente — backup ABORTADO"
  exit 1
fi
ENC="$FILE.gpg"
if ! gpg --batch --yes --trust-model always --encrypt --recipient "$GPG_RECIPIENT" --output "$ENC" "$FILE" 2>>"$LOG"; then
  say "ERRO: cifragem GPG falhou ($FILE) — backup ABORTADO"
  shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
  rm -f "$ENC"
  notify fail "cifragem GPG falhou — backup ABORTADO"
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
    say "OK: $(basename "$FILE") (${ENCSIZE} bytes) + offsite $OFFSITE_TARGET"
    notify ok "OK $(basename "$FILE") (${ENCSIZE}B) + offsite"
  else
    say "AVISO: dump local OK ($FILE, ${ENCSIZE} bytes) mas OFFSITE FALHOU ($OFFSITE_TARGET)"
    notify fail "dump local OK mas OFFSITE FALHOU ($OFFSITE_TARGET)"
  fi
else
  # OFFSITE_TARGET vazio: como o offsite é esperado (DR), tratamos como FALHA de config —
  # foi exatamente esse o gap silencioso de 16→18/jun (cron perdeu o env).
  say "AVISO: dump local OK ($FILE, ${ENCSIZE} bytes) mas OFFSITE_TARGET VAZIO — offsite NÃO feito"
  notify fail "OFFSITE_TARGET vazio — offsite NÃO feito (regressão de config?)"
fi

# ---------------------------------------------------------------------------
# Cliente Inteligente (ci-api): contas + backups CIFRADOS dos clientes + cardápios.
# Vivem só nesta VPS (bind mounts ci-data/ci-lojas). Os .b64 já são ZERO-KNOWLEDGE
# (bytes opacos), então cifrar de novo p/ offsite não fere a privacidade. SEM este
# backup, perder o volume = perder TODAS as contas e backups de nuvem dos clientes,
# sem recuperação possível. Tar -> GPG (mesma chave) -> rotação -> offsite.
CI_BASE=/root/wins_agro_v1
if [ -d "$CI_BASE/ci-data" ]; then
  TARGETS="ci-data"
  [ -d "$CI_BASE/ci-lojas" ] && TARGETS="$TARGETS ci-lojas"
  CIFILE="$DEST/ci_data_$(date +%Y%m%d_%H%M%S).tar"
  # shellcheck disable=SC2086
  if tar -cf "$CIFILE" -C "$CI_BASE" $TARGETS 2>>"$LOG" \
     && gpg --batch --yes --trust-model always --encrypt --recipient "$GPG_RECIPIENT" \
            --output "$CIFILE.gpg" "$CIFILE" 2>>"$LOG"; then
    shred -u "$CIFILE" 2>/dev/null || rm -f "$CIFILE"
    chmod 600 "$CIFILE.gpg"
    CISIZE=$(stat -c%s "$CIFILE.gpg")
    find "$DEST" -name 'ci_data_*.tar.gpg' -mtime +"$KEEP_DAYS" -delete
    if [ -n "$OFFSITE_TARGET" ]; then
      scp -o BatchMode=yes -o ConnectTimeout=15 "$CIFILE.gpg" "$OFFSITE_TARGET/" >> "$LOG" 2>&1 \
        && say "OK: ci-data (${CISIZE}B) + offsite" \
        || { say "AVISO: ci-data local OK mas OFFSITE FALHOU"; notify fail "ci-data offsite FALHOU"; }
    else
      say "OK: ci-data (${CISIZE}B) local (offsite NÃO configurado)"
    fi
  else
    rm -f "$CIFILE" "$CIFILE.gpg" 2>/dev/null
    say "ERRO: backup do ci-data falhou (tar/gpg)"
    notify fail "backup do ci-data falhou (tar/gpg)"
  fi
fi
