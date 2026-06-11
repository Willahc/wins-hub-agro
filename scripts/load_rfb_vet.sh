#!/bin/bash
# Source 1 (canal técnicos): ingere CNPJs de VETERINÁRIA + INSEMINAÇÃO direto do
# stream do zip da Receita (sem descompactar ~50GB), filtrando por CNAE primário.
#   7500100 = Atividades veterinárias (clínica + visita a fazenda)
#   0162801 = Serviço de inseminação artificial em animais  (técnico de maleta!)
#   0162899 = Atividades de apoio à pecuária n.e. (consultoria de campo)
# Destino: cnpj.estabelecimento_vet (mesma estrutura da rural -> reusa enrich_decisores).
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

for N in 0 1 2 3 4 5 6 7 8 9; do
  echo "[$(date +%H:%M:%S)] === Estabelecimentos$N ==="
  curl -s -u "$AUTH" "$BASE/Estabelecimentos$N.zip" -o /tmp/estv.zip
  sz=$(stat -c%s /tmp/estv.zip 2>/dev/null || echo 0)
  echo "  baixado $((sz/1024/1024)) MB"
  if [ "$sz" -lt 1000000 ]; then echo "  ARQUIVO SUSPEITO (<1MB), pulando"; rm -f /tmp/estv.zip; continue; fi
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/estv.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/estv.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/estv.zip; continue; }
  unzip -p /tmp/estv.zip 2>/dev/null | grep -aE "$CNAE_RE" > /tmp/estv_f.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/estv.zip
  echo "  linhas vet/insem filtradas: $(wc -l < /tmp/estv_f.csv)"
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_estab;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_estab FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/estv_f.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.estabelecimento_vet ($INS)
    SELECT $SEL FROM cnpj.stg_estab WHERE c11 IN ($CNAE_IN)
    ON CONFLICT (cnpj_basico,cnpj_ordem,cnpj_dv) DO NOTHING;" 2>&1 | tail -1
  rm -f /tmp/estv_f.csv
  docker exec $DB psql -U postgres -d wins_agro -t -c "
    SELECT '  total vet agora: '||count(*)
      ||' | 7500100='||count(*) FILTER (WHERE cnae_fiscal_principal='7500100')
      ||' 0162801='||count(*) FILTER (WHERE cnae_fiscal_principal='0162801')
      ||' 0162899='||count(*) FILTER (WHERE cnae_fiscal_principal='0162899')
      ||' | ativos='||count(*) FILTER (WHERE situacao_cadastral='02')
    FROM cnpj.estabelecimento_vet;" 2>&1
done
echo "[$(date +%H:%M:%S)] === VET/INSEM NACIONAL CONCLUÍDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
