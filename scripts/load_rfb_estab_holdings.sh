#!/bin/bash
# Vetor B do ponto cego das holdings: carrega do dump NACIONAL de Estabelecimentos
# da RFB SÓ os CNAEs de holding/imobiliária/participações (que NÃO entraram na base
# agro, ingerida com filtro de CNAE pecuário). Faz o stream do zip com unzip -p | grep
# (SEM descompactar os ~20GB) e \copy pra staging nova cnpj.stg_estab_holding (c0..c29).
# Resumível por bloco (.done). O refino "quais dessas holdings são agro" fica no SQL
# de cruzamento (endereço rural / nome com termo agro / sócio agro) — ver PONTO_CEGO_HOLDINGS.md.
set -uo pipefail
DUMP='2026-06'
BASE="https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/$DUMP"
# token do WebDAV da RFB vem do .env (não fica no código/git)
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1-db-1   # compose v2: nome com HÍFEN (o load_rfb_nacional.sh antigo usa underscore, está DESATUALIZADO)
WORK=/tmp/rfb_estab_holding; mkdir -p "$WORK"
FALHAS=0

# CNAEs alvo (campo cnae_fiscal_principal vem entre aspas no CSV da RFB):
#   "6810  -> compra/venda/aluguel de imóveis próprios (6810201/6810202/6810203) — onde caem as fazendas-holding
#   "6462  -> holdings de instituições não-financeiras (6462000)
#   "6463  -> outras sociedades de participação (holdings) (6463800)
GREP_RE='"6810|"6462|"6463'

# staging nova com a MESMA estrutura de cnpj.stg_estab (c0..c29 text)
docker exec "$DB" psql -U postgres -d wins_agro -c "
  CREATE TABLE IF NOT EXISTS cnpj.stg_estab_holding (
    c0 text, c1 text, c2 text, c3 text, c4 text, c5 text, c6 text, c7 text, c8 text, c9 text,
    c10 text, c11 text, c12 text, c13 text, c14 text, c15 text, c16 text, c17 text, c18 text, c19 text,
    c20 text, c21 text, c22 text, c23 text, c24 text, c25 text, c26 text, c27 text, c28 text, c29 text
  );" >/dev/null 2>&1

for N in 0 1 2 3 4 5 6 7 8 9; do
  done_f="$WORK/E$N.done"
  [ -f "$done_f" ] && { echo "[E$N] já feito, pulando"; continue; }
  echo "[$(date +%H:%M:%S)] === Estabelecimentos$N ==="
  curl -s -u "$AUTH" "$BASE/Estabelecimentos$N.zip" -o "$WORK/est.zip"
  sz=$(stat -c%s "$WORK/est.zip" 2>/dev/null || echo 0)
  echo "  baixado $((sz/1024/1024)) MB"
  if [ "$sz" -lt 1000000 ]; then echo "  ARQUIVO SUSPEITO (<1MB), pulando"; rm -f "$WORK/est.zip"; FALHAS=$((FALHAS+1)); continue; fi
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq "$WORK/est.zip" >/dev/null 2>&1 || { echo "  ZIP CORROMPIDO: $WORK/est.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f "$WORK/est.zip"; continue; }
  # stream + grep dos CNAEs de holding/imobiliária; grep sem match (rc=1) = ok, outro erro estoura
  unzip -p "$WORK/est.zip" 2>/dev/null | grep -aE "$GREP_RE" > "$WORK/est_f.csv" || [ $? -eq 1 ]
  rm -f "$WORK/est.zip"
  echo "  linhas holding filtradas: $(wc -l < "$WORK/est_f.csv")"
  docker exec -i "$DB" psql -U postgres -d wins_agro \
    -c "\copy cnpj.stg_estab_holding FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < "$WORK/est_f.csv" 2>&1 | tail -1
  rm -f "$WORK/est_f.csv"
  touch "$done_f"
  docker exec "$DB" psql -U postgres -d wins_agro -tAc "SELECT '  staging agora: '||count(*) FROM cnpj.stg_estab_holding"
done

echo "[$(date +%H:%M:%S)] === ESTABELECIMENTOS HOLDING NACIONAL CARREGADO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com problema — carga INCOMPLETA, re-rodar" >&2; exit 1; }
echo "Próximo passo: cruzar cnpj.stg_estab_holding com sinal agro (endereço rural / nome agro / sócio agro) — ver scripts/PONTO_CEGO_HOLDINGS.md"
