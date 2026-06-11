#!/bin/bash
# Item 3: amplia a base com estabelecimentos cujo CNAE de inseminação/apoio/veterinária está como
# SECUNDÁRIO (e o primário é outro — tipicamente consultoria/assessoria pecuária, onde caem zootecnistas
# de repro/genética que não abrem clínica vet). O load original só pegou CNAE primário.
# Grava em cnpj.estabelecimento_vet (mesma tabela, ON CONFLICT DO NOTHING) — primário ≠ vet os distingue.
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
TARGET="'7500100','0162801','0162899'"
mkdir -p /tmp/rfbvet
dl(){ local n=$1; for try in 1 2 3; do curl -s -u "$AUTH" "$BASE/Estabelecimentos$n.zip" -o /tmp/rfbvet/est$n.zip
  local s=$(stat -c%s /tmp/rfbvet/est$n.zip 2>/dev/null||echo 0); [ "$s" -gt 50000000 ] && { echo "  est$n ok $((s/1024/1024))MB"; return; }; done; echo "  est$n FALHOU"; }
export -f dl; export AUTH BASE
echo "[$(date +%H:%M:%S)] baixando 10 Estabelecimentos (5 paralelos)..."
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ {}
ins_total=0
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfbvet/est$N.zip ] || { echo "est$N ausente"; continue; }
  echo "[$(date +%H:%M:%S)] processando est$N"
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfbvet/est$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfbvet/est$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfbvet/est$N.zip; continue; }
  unzip -p /tmp/rfbvet/est$N.zip 2>/dev/null | grep -aE "$CNAE_RE" > /tmp/rfbvet/f.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/rfbvet/est$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_estab;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_estab FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfbvet/f.csv 2>&1 | tail -1
  # SECUNDÁRIO casa o target E primário NÃO está no target (= estab novo, não-clínica)
  r=$(docker exec $DB psql -U postgres -d wins_agro -t -c "
    INSERT INTO cnpj.estabelecimento_vet ($INS)
    SELECT $SEL FROM cnpj.stg_estab
    WHERE c12 ~ '(7500100|0162801|0162899)' AND c11 NOT IN ($TARGET)
    ON CONFLICT (cnpj_basico,cnpj_ordem,cnpj_dv) DO NOTHING;" 2>&1 | tr -d ' \n')
  echo "  $r"
  rm -f /tmp/rfbvet/f.csv
done
docker exec $DB psql -U postgres -d wins_agro -t -c "
  SELECT 'NOVOS (primário não-vet, secundário repro): '
    ||count(*) FILTER (WHERE cnae_fiscal_principal NOT IN ($TARGET) AND situacao_cadastral='02')
    ||' | total estab_vet agora: '||count(*) FROM cnpj.estabelecimento_vet;"
echo "[$(date +%H:%M:%S)] === SECUNDARIO CONCLUIDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
