#!/bin/bash
# Source 1 paralelo: VETERINÁRIA + INSEMINAÇÃO da Receita, 5 downloads simultâneos.
#   7500100=ativ. veterinárias · 0162801=inseminação artificial · 0162899=apoio à pecuária
set -uo pipefail
FALHAS=0
BASE='https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/2026-05'
# token do WebDAV da RFB vem do .env (não fica no código/git)
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1_db_1
INS="cnpj_basico,cnpj_ordem,cnpj_dv,identificador_matriz_filial,nome_fantasia,situacao_cadastral,data_situacao_cadastral,cnae_fiscal_principal,cnae_fiscal_secundaria,tipo_logradouro,logradouro,numero,complemento,bairro,cep,uf,municipio,ddd_1,telefone_1,ddd_2,telefone_2,correio_eletronico,data_inicio_atividade"
SEL="c0,c1,c2,c3,c4,c5,c6,c11,c12,c13,c14,c15,c16,c17,c18,c19,c20,c21,c22,c23,c24,c27,c10"
CNAE_RE='"(7500100|0162801|0162899)"'
CNAE_IN="'7500100','0162801','0162899'"
mkdir -p /tmp/rfbvet
dl(){
  local n=$1
  for try in 1 2 3; do
    curl -s -u "$AUTH" "$BASE/Estabelecimentos$n.zip" -o /tmp/rfbvet/est$n.zip
    local s=$(stat -c%s /tmp/rfbvet/est$n.zip 2>/dev/null || echo 0)
    if [ "$s" -gt 50000000 ]; then echo "  est$n ok $((s/1024/1024))MB"; return; fi
  done
  echo "  est$n FALHOU"
}
export -f dl; export AUTH BASE
echo "[$(date +%H:%M:%S)] baixando 10 arquivos (5 paralelos)..."
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ {}
echo "[$(date +%H:%M:%S)] download done: $(du -sh /tmp/rfbvet 2>/dev/null)"
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfbvet/est$N.zip ] || { echo "est$N ausente, pulo"; continue; }
  echo "[$(date +%H:%M:%S)] processando est$N"
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfbvet/est$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfbvet/est$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfbvet/est$N.zip; continue; }
  unzip -p /tmp/rfbvet/est$N.zip 2>/dev/null | grep -aE "$CNAE_RE" > /tmp/rfbvet/f.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  echo "  vet/insem filtrado: $(wc -l < /tmp/rfbvet/f.csv)"
  rm -f /tmp/rfbvet/est$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_estab;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_estab FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfbvet/f.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "INSERT INTO cnpj.estabelecimento_vet ($INS) SELECT $SEL FROM cnpj.stg_estab WHERE c11 IN ($CNAE_IN) ON CONFLICT (cnpj_basico,cnpj_ordem,cnpj_dv) DO NOTHING;" 2>&1 | tail -1
  rm -f /tmp/rfbvet/f.csv
done
docker exec $DB psql -U postgres -d wins_agro -t -c "
  SELECT 'FINAL vet: '||count(*)
    ||' | 7500100='||count(*) FILTER (WHERE cnae_fiscal_principal='7500100')
    ||' 0162801='||count(*) FILTER (WHERE cnae_fiscal_principal='0162801')
    ||' 0162899='||count(*) FILTER (WHERE cnae_fiscal_principal='0162899')
    ||' | ativos='||count(*) FILTER (WHERE situacao_cadastral='02')
  FROM cnpj.estabelecimento_vet;"
echo "[$(date +%H:%M:%S)] === VET PARALELO CONCLUIDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
