#!/bin/bash
# Versão PARALELA do Vetor B: baixa os 10 blocos Estabelecimentos em N conexões
# concorrentes (a RFB limita ~1MB/s POR conexão, então paralelizar é o ganho real).
# Cada bloco usa arquivos próprios (est_$N.zip / est_$N.csv) -> sem colisão. grep dos
# CNAEs de holding, \copy concorrente em cnpj.stg_estab_holding (Postgres aceita inserts
# concorrentes). Resumível por bloco (.done). Cap de concorrência = PAR.
set -uo pipefail
DUMP='2026-06'
BASE="https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/$DUMP"
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1-db-1
WORK=/tmp/rfb_estab_holding; mkdir -p "$WORK"
GREP_RE='"6810|"6462|"6463'
PAR=5   # downloads concorrentes

docker exec "$DB" psql -U postgres -d wins_agro -c "
  CREATE TABLE IF NOT EXISTS cnpj.stg_estab_holding (
    c0 text,c1 text,c2 text,c3 text,c4 text,c5 text,c6 text,c7 text,c8 text,c9 text,
    c10 text,c11 text,c12 text,c13 text,c14 text,c15 text,c16 text,c17 text,c18 text,c19 text,
    c20 text,c21 text,c22 text,c23 text,c24 text,c25 text,c26 text,c27 text,c28 text,c29 text);" >/dev/null 2>&1

bloco() {   # $1 = N
  local N="$1" f="$WORK/est_$1.zip" csv="$WORK/est_$1.csv" done_f="$WORK/E$1.done"
  [ -f "$done_f" ] && { echo "[E$N] já feito"; return 0; }
  echo "[$(date +%H:%M:%S)] [E$N] baixando…"
  curl -s -u "$AUTH" "$BASE/Estabelecimentos$N.zip" -o "$f"
  local sz; sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt 1000000 ]; then echo "[E$N] SUSPEITO (<1MB)"; rm -f "$f"; return 1; fi
  unzip -tq "$f" >/dev/null 2>&1 || { echo "[E$N] ZIP CORROMPIDO" >&2; rm -f "$f"; return 1; }
  echo "[$(date +%H:%M:%S)] [E$N] baixado $((sz/1024/1024))MB — grep+copy…"
  unzip -p "$f" 2>/dev/null | grep -aE "$GREP_RE" > "$csv" || [ $? -eq 1 ]
  rm -f "$f"
  docker exec -i "$DB" psql -U postgres -d wins_agro \
    -c "\copy cnpj.stg_estab_holding FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < "$csv" 2>&1 | tail -1
  echo "[$(date +%H:%M:%S)] [E$N] OK — $(wc -l < "$csv") linhas holding"
  rm -f "$csv"; touch "$done_f"
}
export -f bloco; export AUTH BASE DB WORK GREP_RE

# pool de PAR workers via xargs
printf '%s\n' 0 1 2 3 4 5 6 7 8 9 | xargs -P "$PAR" -I{} bash -c 'bloco "$@"' _ {}

echo "[$(date +%H:%M:%S)] === VETOR B (paralelo) CONCLUÍDO ==="
ok=$(ls "$WORK"/E*.done 2>/dev/null | wc -l)
echo "blocos prontos: $ok/10"
[ "$ok" -eq 10 ] || { echo "INCOMPLETO ($ok/10) — re-rodar (resumível)" >&2; exit 1; }
