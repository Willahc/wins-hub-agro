#!/bin/bash
# Ponto cego das holdings: cruza o dump NACIONAL de Sócios da RFB contra os sócios
# da nossa base agro (cnpj.socio_rural). Em vez de carregar ~50M sócios, faz grep -F
# da lista de CPFs mascarados da base agro no stream do zip (Aho-Corasick) e guarda
# só o que casa -> cnpj.stg_socios_match. O join fino (CPF+nome) e a materialização
# do ponto cego ficam no SQL final (run_socios_join.sql). Resumível por bloco (.done).
set -uo pipefail
DUMP='2026-06'
BASE="https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/$DUMP"
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1-db-1
WORK=/tmp/rfb_socios; mkdir -p "$WORK"
CPFS="$WORK/agro_cpfs.txt"
FALHAS=0

# 1) lista de CPFs mascarados distintos da base agro (PF apenas) -> arquivo p/ grep -F
if [ ! -s "$CPFS" ]; then
  echo "[$(date +%H:%M:%S)] extraindo CPFs da base agro..."
  docker exec "$DB" psql -U postgres -d wins_agro -tAc \
    "SELECT DISTINCT cnpj_cpf_do_socio FROM cnpj.socio_rural
     WHERE identificador_de_socio='2' AND cnpj_cpf_do_socio ~ '^\*\*\*[0-9]{6}\*\*$'" > "$CPFS"
  echo "  $(wc -l < "$CPFS") CPFs distintos"
fi

# 2) por bloco: baixa, valida zip, stream + grep -F dos nossos CPFs, \copy no staging
for N in 0 1 2 3 4 5 6 7 8 9; do
  done_f="$WORK/S$N.done"
  [ -f "$done_f" ] && { echo "[S$N] já feito, pulando"; continue; }
  echo "[$(date +%H:%M:%S)] === Socios$N ==="
  curl -s -u "$AUTH" "$BASE/Socios$N.zip" -o "$WORK/s.zip"
  sz=$(stat -c%s "$WORK/s.zip" 2>/dev/null || echo 0)
  echo "  baixado $((sz/1024/1024)) MB"
  if [ "$sz" -lt 1000000 ]; then echo "  ARQUIVO SUSPEITO (<1MB), pulando"; rm -f "$WORK/s.zip"; FALHAS=$((FALHAS+1)); continue; fi
  unzip -tq "$WORK/s.zip" >/dev/null 2>&1 || { echo "  ZIP CORROMPIDO — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f "$WORK/s.zip"; continue; }
  # grep -aF -f : casa qualquer linha que contenha um dos nossos CPFs mascarados
  unzip -p "$WORK/s.zip" 2>/dev/null | grep -aF -f "$CPFS" > "$WORK/m.csv" || [ $? -eq 1 ]
  rm -f "$WORK/s.zip"
  echo "  linhas casadas: $(wc -l < "$WORK/m.csv")"
  docker exec -i "$DB" psql -U postgres -d wins_agro \
    -c "\copy cnpj.stg_socios_match FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < "$WORK/m.csv" 2>&1 | tail -1
  rm -f "$WORK/m.csv"
  touch "$done_f"
  docker exec "$DB" psql -U postgres -d wins_agro -tAc "SELECT '  staging agora: '||count(*) FROM cnpj.stg_socios_match"
done

echo "[$(date +%H:%M:%S)] === SÓCIOS NACIONAL CARREGADO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com problema — carga INCOMPLETA, re-rodar" >&2; exit 1; }
echo "Próximo passo: psql -f scripts/run_socios_join.sql"
