#!/bin/bash
# Re-ingestão NACIONAL dos Dados Abertos CNPJ da Receita, filtrando só gado (corte+leite)
# direto do stream do zip (grep, sem descompactar os ~50GB). Dedup por PK.
set -uo pipefail
FALHAS=0
BASE='https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/2026-05'
# token do WebDAV da RFB vem do .env (não fica no código/git)
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1_db_1
INS="cnpj_basico,cnpj_ordem,cnpj_dv,identificador_matriz_filial,nome_fantasia,situacao_cadastral,data_situacao_cadastral,cnae_fiscal_principal,cnae_fiscal_secundaria,tipo_logradouro,logradouro,numero,complemento,bairro,cep,uf,municipio,ddd_1,telefone_1,ddd_2,telefone_2,correio_eletronico,data_inicio_atividade"
SEL="c0,c1,c2,c3,c4,c5,c6,c11,c12,c13,c14,c15,c16,c17,c18,c19,c20,c21,c22,c23,c24,c27,c10"

for N in 0 1 2 3 4 5 6 7 8 9; do
  echo "[$(date +%H:%M:%S)] === Estabelecimentos$N ==="
  curl -s -u "$AUTH" "$BASE/Estabelecimentos$N.zip" -o /tmp/est.zip
  sz=$(stat -c%s /tmp/est.zip 2>/dev/null || echo 0)
  echo "  baixado $((sz/1024/1024)) MB"
  if [ "$sz" -lt 1000000 ]; then echo "  ARQUIVO SUSPEITO (<1MB), pulando"; rm -f /tmp/est.zip; continue; fi
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/est.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/est.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/est.zip; continue; }
  unzip -p /tmp/est.zip 2>/dev/null | grep -aE '"015120[12]"' > /tmp/est_f.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/est.zip
  echo "  linhas gado filtradas: $(wc -l < /tmp/est_f.csv)"
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_estab;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_estab FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/est_f.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.estabelecimento_rural ($INS)
    SELECT $SEL FROM cnpj.stg_estab WHERE c11 IN ('0151201','0151202')
    ON CONFLICT (cnpj_basico,cnpj_ordem,cnpj_dv) DO NOTHING;" 2>&1 | tail -1
  rm -f /tmp/est_f.csv
  docker exec $DB psql -U postgres -d wins_agro -t -c "SELECT '  total estab agora: '||count(*)||' | MT='||count(*) FILTER (WHERE uf='MT')||' MS='||count(*) FILTER (WHERE uf='MS')||' GO='||count(*) FILTER (WHERE uf='GO') FROM cnpj.estabelecimento_rural;" 2>&1
done
echo "[$(date +%H:%M:%S)] === ESTABELECIMENTOS NACIONAL CONCLUÍDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
