#!/bin/bash
# 2ª fase: Empresas (razão/capital/porte) + Sócios (decisor) NACIONAL, filtrando pelos
# CNPJs de gado já carregados (grep -Ff dos basicos). Roda DEPOIS dos Estabelecimentos.
set -uo pipefail
FALHAS=0
BASE='https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/2026-05'
# token do WebDAV da RFB vem do .env (não fica no código/git)
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1_db_1
mkdir -p /tmp/rfb
dl(){ local pref=$1 n=$2; for t in 1 2 3; do curl -s -u "$AUTH" "$BASE/$pref$n.zip" -o /tmp/rfb/$pref$n.zip
  local s=$(stat -c%s /tmp/rfb/$pref$n.zip 2>/dev/null||echo 0); [ "$s" -gt 5000000 ] && { echo "  $pref$n ok $((s/1024/1024))MB"; return; }; done; echo "  $pref$n FALHOU"; }
export -f dl; export AUTH BASE

# staging
docker exec $DB psql -U postgres -d wins_agro -c "
DROP TABLE IF EXISTS cnpj.stg_emp; CREATE UNLOGGED TABLE cnpj.stg_emp (c0 text,c1 text,c2 text,c3 text,c4 text,c5 text,c6 text);
DROP TABLE IF EXISTS cnpj.stg_soc; CREATE UNLOGGED TABLE cnpj.stg_soc (c0 text,c1 text,c2 text,c3 text,c4 text,c5 text,c6 text,c7 text,c8 text,c9 text,c10 text);" >/dev/null 2>&1

# pattern files dos basicos de gado
echo "[$(date +%H:%M:%S)] gerando pattern de basicos..."
docker exec $DB psql -U postgres -d wins_agro -t -A -c "
SELECT DISTINCT '\"'||cnpj_basico||'\";' FROM cnpj.estabelecimento_rural WHERE cnae_fiscal_principal IN ('0151201','0151202');" > /tmp/rfb/pat_emp.txt
docker exec $DB psql -U postgres -d wins_agro -t -A -c "
SELECT DISTINCT '\"'||e.cnpj_basico||'\";' FROM cnpj.estabelecimento_rural e
WHERE e.cnae_fiscal_principal IN ('0151201','0151202')
  AND NOT EXISTS (SELECT 1 FROM cnpj.socio_rural s WHERE s.cnpj_basico=e.cnpj_basico);" > /tmp/rfb/pat_soc.txt
echo "  empresas pat: $(wc -l < /tmp/rfb/pat_emp.txt) | socios pat: $(wc -l < /tmp/rfb/pat_soc.txt)"

echo "[$(date +%H:%M:%S)] === EMPRESAS: baixando (5 paralelos) ==="
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ Empresas {}
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfb/Empresas$N.zip ] || continue
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfb/Empresas$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfb/Empresas$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfb/Empresas$N.zip; continue; }
  unzip -p /tmp/rfb/Empresas$N.zip 2>/dev/null | grep -aFf /tmp/rfb/pat_emp.txt > /tmp/rfb/e.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/rfb/Empresas$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_emp;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_emp FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfb/e.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.empresa_rural (cnpj_basico,razao_social,natureza_juridica,qualificacao_responsavel,capital_social,porte,ente_federativo_responsavel)
    SELECT c0,c1,c2,c3,NULLIF(replace(c4,',','.'),'')::numeric,c5,c6 FROM cnpj.stg_emp
    ON CONFLICT (cnpj_basico) DO NOTHING;" 2>&1 | tail -1
  rm -f /tmp/rfb/e.csv
  echo "  [$(date +%H:%M:%S)] Empresas$N feito"
done

echo "[$(date +%H:%M:%S)] === SOCIOS: baixando (5 paralelos) ==="
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ Socios {}
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfb/Socios$N.zip ] || continue
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfb/Socios$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfb/Socios$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfb/Socios$N.zip; continue; }
  unzip -p /tmp/rfb/Socios$N.zip 2>/dev/null | grep -aFf /tmp/rfb/pat_soc.txt > /tmp/rfb/s.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/rfb/Socios$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_soc;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_soc FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfb/s.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.socio_rural (cnpj_basico,identificador_de_socio,nome_socio,cnpj_cpf_do_socio,qualificacao_do_socio,data_entrada_sociedade,pais,faixa_etaria)
    SELECT DISTINCT c0,c1,c2,c3,c4,c5,c6,c10 FROM cnpj.stg_soc s
    WHERE NOT EXISTS (SELECT 1 FROM cnpj.socio_rural x
       WHERE x.cnpj_basico = s.c0 AND x.nome_socio = s.c2
         AND COALESCE(x.cnpj_cpf_do_socio,'') = COALESCE(s.c3,''));" 2>&1 | tail -1
  rm -f /tmp/rfb/s.csv
  echo "  [$(date +%H:%M:%S)] Socios$N feito"
done
docker exec $DB psql -U postgres -d wins_agro -t -c "
SELECT 'empresa_rural: '||count(*) FROM cnpj.empresa_rural;
SELECT 'socio_rural: '||count(*) FROM cnpj.socio_rural;"
echo "[$(date +%H:%M:%S)] === EMP+SOC CONCLUIDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
