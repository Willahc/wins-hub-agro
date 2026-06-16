#!/bin/bash
# Empresas RFB (razão social, natureza jurídica, capital, porte) — carga CHEIA paralela.
# Necessário para enriquecer A∩B e tipo-Lamão SEM BrasilAPI (Estabelecimento dá CNAE/
# endereço/telefone; Empresa dá razão social/capital). 10 blocos, 5 conexões concorrentes.
# Layout RFB Empresa: c0=cnpj_basico c1=razao_social c2=natureza_juridica
#   c3=qualif_resp c4=capital_social c5=porte c6=ente_federativo. Resumível por bloco (.done).
set -uo pipefail
DUMP='2026-06'
BASE="https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/$DUMP"
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1-db-1
WORK=/tmp/rfb_empresas; mkdir -p "$WORK"
PAR=5

docker exec "$DB" psql -U postgres -d wins_agro -c "
  CREATE TABLE IF NOT EXISTS cnpj.stg_empresas_full (
    c0 text, c1 text, c2 text, c3 text, c4 text, c5 text, c6 text);" >/dev/null 2>&1

bloco() {
  local N="$1" f="$WORK/emp_$1.zip" csv="$WORK/emp_$1.csv" done_f="$WORK/EMP$1.done"
  [ -f "$done_f" ] && { echo "[EMP$N] já feito"; return 0; }
  echo "[$(date +%H:%M:%S)] [EMP$N] baixando…"
  curl -s -u "$AUTH" "$BASE/Empresas$N.zip" -o "$f"
  local sz; sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt 1000000 ]; then echo "[EMP$N] SUSPEITO (<1MB)"; rm -f "$f"; return 1; fi
  unzip -tq "$f" >/dev/null 2>&1 || { echo "[EMP$N] ZIP CORROMPIDO" >&2; rm -f "$f"; return 1; }
  echo "[$(date +%H:%M:%S)] [EMP$N] baixado $((sz/1024/1024))MB — copy…"
  unzip -p "$f" 2>/dev/null > "$csv"
  rm -f "$f"
  docker exec -i "$DB" psql -U postgres -d wins_agro \
    -c "\copy cnpj.stg_empresas_full FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < "$csv" 2>&1 | tail -1
  echo "[$(date +%H:%M:%S)] [EMP$N] OK — $(wc -l < "$csv") empresas"
  rm -f "$csv"; touch "$done_f"
}
export -f bloco; export AUTH BASE DB WORK

printf '%s\n' 0 1 2 3 4 5 6 7 8 9 | xargs -P "$PAR" -I{} bash -c 'bloco "$@"' _ {}

echo "[$(date +%H:%M:%S)] === EMPRESAS (paralelo) CONCLUÍDO ==="
ok=$(ls "$WORK"/EMP*.done 2>/dev/null | wc -l); echo "blocos: $ok/10"
[ "$ok" -eq 10 ] || { echo "INCOMPLETO ($ok/10) — re-rodar" >&2; exit 1; }
docker exec "$DB" psql -U postgres -d wins_agro -tAc "SELECT 'empresas carregadas: '||count(*) FROM cnpj.stg_empresas_full"
