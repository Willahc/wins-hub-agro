#!/bin/bash
# Empresas (razão = nome PF p/ Empresário Individual/Produtor) + Sócios (nome PF do sócio)
# para os CNPJs de VETERINÁRIA/INSEMINAÇÃO já carregados em cnpj.estabelecimento_vet.
# Espelha load_rfb_emp_soc.sh (gado) mas mira o conjunto vet e grava em tabelas *_vet.
set -uo pipefail
FALHAS=0
BASE='https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/2026-05'
# token do WebDAV da RFB vem do .env (não fica no código/git)
AUTH="$(grep '^RFB_WEBDAV_TOKEN=' /root/wins_agro_v1/.env | cut -d= -f2):"
[ "$AUTH" != ':' ] || { echo 'RFB_WEBDAV_TOKEN ausente no .env' >&2; exit 1; }
DB=wins_agro_v1_db_1
mkdir -p /tmp/rfbvet
dl(){ local pref=$1 n=$2; for t in 1 2 3; do curl -s -u "$AUTH" "$BASE/$pref$n.zip" -o /tmp/rfbvet/$pref$n.zip
  local s=$(stat -c%s /tmp/rfbvet/$pref$n.zip 2>/dev/null||echo 0); [ "$s" -gt 5000000 ] && { echo "  $pref$n ok $((s/1024/1024))MB"; return; }; done; echo "  $pref$n FALHOU"; }
export -f dl; export AUTH BASE

# tabelas-alvo (espelham as rurais) + staging
docker exec $DB psql -U postgres -d wins_agro -c "
CREATE TABLE IF NOT EXISTS cnpj.empresa_vet (cnpj_basico varchar(8) PRIMARY KEY, razao_social text,
  natureza_juridica varchar(4), qualificacao_responsavel varchar(2), capital_social numeric(20,2),
  porte varchar(2), ente_federativo_responsavel text);
CREATE TABLE IF NOT EXISTS cnpj.socio_vet (cnpj_basico varchar(8), identificador_de_socio varchar(1),
  nome_socio text, cnpj_cpf_do_socio text, qualificacao_do_socio varchar(2),
  data_entrada_sociedade varchar(8), pais varchar(3), faixa_etaria varchar(1));
CREATE INDEX IF NOT EXISTS idx_socio_vet_basico ON cnpj.socio_vet(cnpj_basico);
DROP TABLE IF EXISTS cnpj.stg_emp_v; CREATE UNLOGGED TABLE cnpj.stg_emp_v (c0 text,c1 text,c2 text,c3 text,c4 text,c5 text,c6 text);
DROP TABLE IF EXISTS cnpj.stg_soc_v; CREATE UNLOGGED TABLE cnpj.stg_soc_v (c0 text,c1 text,c2 text,c3 text,c4 text,c5 text,c6 text,c7 text,c8 text,c9 text,c10 text);" >/dev/null 2>&1

# pattern dos básicos de vet (todos os ativos)
echo "[$(date +%H:%M:%S)] gerando pattern de basicos vet..."
docker exec $DB psql -U postgres -d wins_agro -t -A -c "
SELECT DISTINCT '\"'||cnpj_basico||'\";' FROM cnpj.estabelecimento_vet WHERE situacao_cadastral='02';" > /tmp/rfbvet/pat.txt
echo "  basicos vet: $(wc -l < /tmp/rfbvet/pat.txt)"

echo "[$(date +%H:%M:%S)] === EMPRESAS: baixando (5 paralelos) ==="
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ Empresas {}
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfbvet/Empresas$N.zip ] || continue
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfbvet/Empresas$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfbvet/Empresas$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfbvet/Empresas$N.zip; continue; }
  unzip -p /tmp/rfbvet/Empresas$N.zip 2>/dev/null | grep -aFf /tmp/rfbvet/pat.txt > /tmp/rfbvet/e.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/rfbvet/Empresas$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_emp_v;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_emp_v FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfbvet/e.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.empresa_vet (cnpj_basico,razao_social,natureza_juridica,qualificacao_responsavel,capital_social,porte,ente_federativo_responsavel)
    SELECT c0,c1,c2,c3,NULLIF(replace(c4,',','.'),'')::numeric,c5,c6 FROM cnpj.stg_emp_v
    ON CONFLICT (cnpj_basico) DO NOTHING;" 2>&1 | tail -1
  rm -f /tmp/rfbvet/e.csv
  echo "  [$(date +%H:%M:%S)] Empresas$N feito"
done

echo "[$(date +%H:%M:%S)] === SOCIOS: baixando (5 paralelos) ==="
seq 0 9 | xargs -P5 -I{} bash -c 'dl "$@"' _ Socios {}
for N in 0 1 2 3 4 5 6 7 8 9; do
  [ -f /tmp/rfbvet/Socios$N.zip ] || continue
  # zip corrompido NÃO pode virar carga silenciosamente incompleta: testa antes
  unzip -tq /tmp/rfbvet/Socios$N.zip >/dev/null 2>&1 || { echo "ZIP CORROMPIDO: /tmp/rfbvet/Socios$N.zip — bloco pulado, re-rodar" >&2; FALHAS=$((FALHAS+1)); rm -f /tmp/rfbvet/Socios$N.zip; continue; }
  unzip -p /tmp/rfbvet/Socios$N.zip 2>/dev/null | grep -aFf /tmp/rfbvet/pat.txt > /tmp/rfbvet/s.csv || [ $? -eq 1 ]  # grep sem match = ok; outro erro estoura
  rm -f /tmp/rfbvet/Socios$N.zip
  docker exec $DB psql -U postgres -d wins_agro -c "TRUNCATE cnpj.stg_soc_v;" >/dev/null 2>&1
  docker exec -i $DB psql -U postgres -d wins_agro -c "\copy cnpj.stg_soc_v FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')" < /tmp/rfbvet/s.csv 2>&1 | tail -1
  docker exec $DB psql -U postgres -d wins_agro -c "
    INSERT INTO cnpj.socio_vet (cnpj_basico,identificador_de_socio,nome_socio,cnpj_cpf_do_socio,qualificacao_do_socio,data_entrada_sociedade,pais,faixa_etaria)
    SELECT c0,c1,c2,c3,c4,c5,c6,c10 FROM cnpj.stg_soc_v;" 2>&1 | tail -1
  rm -f /tmp/rfbvet/s.csv
  echo "  [$(date +%H:%M:%S)] Socios$N feito"
done
docker exec $DB psql -U postgres -d wins_agro -t -c "
SELECT 'empresa_vet: '||count(*) FROM cnpj.empresa_vet;
SELECT 'socio_vet: '||count(*) FROM cnpj.socio_vet;"
echo "[$(date +%H:%M:%S)] === VET EMP+SOC CONCLUIDO ==="
[ "$FALHAS" -eq 0 ] || { echo "ATENÇÃO: $FALHAS bloco(s) com zip corrompido — carga INCOMPLETA" >&2; exit 1; }
