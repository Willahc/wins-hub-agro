# Fechamento do enriquecimento Hunter — Monte Sião (jun/13)

## Estado: ENRIQUECIMENTO IN-ICP ESGOTADO
A fronteira nos **estados de pecuária Nelore** (MT/MS/GO/PA/TO/MG/BA/RO) está esgotada:
**0 fazendas nomeáveis com domínio próprio limpo ainda não rodadas.** Tudo que tem nome de
pessoa + domínio corporativo nesses estados já passou pelo Hunter. Não há mais o que minerar
dentro do ICP além das 15 cabanhas abaixo.

## Entregável final
- **`entrega_hunter_montesiao.csv`** — 704 e-mails (decisor/operador), tierados:
  - **A-confirmada (404)** — caixa `valid`. Topo: Colonial Agro (391 touros Nelore), etc.
  - **B-catchall (268)** — caixa `accept_all` (entregável, mas pode bouncear — Tier B).
  - **X-conglomerado (32, 29 fazendas)** — capital ≥ R$150M (J&F, JBS, Votorantim, Bom Futuro,
    Amaggi, holdings). **SEPARADOS** da fila SMB — tratar como venda enterprise, não misturar.
  - Ordenado por tier → qualidade do sinal genético (alta>media>baixa) → nº touros Nelore.
  - `touros_nelore_conf` zera quando o match genético é coincidência (`descartar`), p/ não inflar.
- **View `prospeccao.hunter_entrega`** — fonte viva do CSV (CREATE OR REPLACE; reconstrói o CSV via COPY).
  - Reconstruir: `scripts/build_entrega_hunter.sql`.

## Fronteira que SOBRA (precisa da chave Hunter)
Materializada em **`prospeccao.hunter_frontier_todo`** (montar: `scripts/build_hunter_frontier.sql`):
- **`cabanha_extra_icp` (15)** — cabanhas de elite com domínio próprio limpo, IN-ICP. **Vale rodar.**
- **`fora_icp_cap5m` (260)** — cap≥R$5M FORA dos estados de pecuária (SP/PR/RS/ES/SC). Geografia
  taurina/leiteira/grão → **baixa aderência ao sêmen Nelore**. Opt-in; não é prioridade.

### Rodar (worker container, ver gotcha #11 da infra)
```bash
# imagem 1x (se não existir): docker build -t hunterpy - <<<$'FROM python:3.12-slim\nRUN pip install httpx psycopg2-binary'
PGPW=$(docker exec wins_agro_v1_api_1 printenv POSTGRES_PASSWORD)   # senha real (32 ch) só no api
docker run -d --name hfront --network wins_agro_v1_default -v /root/wins_agro_v1/scripts:/s \
  -e HK=<chave_hunter> -e PGPW="$PGPW" -e PGHOST=db hunterpy python /s/hunter_finder_frontier.py
# (incluir o opt-in fora do ICP: acrescentar  -e FONTE=todas)
docker logs -f hfront
```
Depois: verificar (`hunter_verify.py`) → reconstruir entrega (`build_entrega_hunter.sql`) → re-exportar CSV.

## "O RESTO" dos operadores jovens (correção jun/13)
Os **7.481 operadores "filho de dono idoso"** (alvo de ouro) NÃO foram todos rodados: só ~1.500
(os de fazenda COM domínio próprio limpo). Os **5.847 candidatos restantes não têm domínio próprio**
no RFB (4.064 gmail, ~1.228 sem e-mail, ~555 só contador/advogado, **0 domínio próprio**) — por isso
o método domínio+nome de ontem não os alcança. A nota "0% / não escalar 7.070" de ontem era do
**WhatsApp/Serper scraping**, não do Hunter.

Única via p/ os 5.847: **Hunter email-finder com `company` (razão social)** — o Hunter resolve o
domínio sozinho. ⚠️ Hit-rate desconhecido e provavelmente baixo (fazenda de gmail raramente tem
domínio corporativo p/ achar — mesma parede do WhatsApp). Por isso: **testar 100 de melhor sinal
ICP primeiro, medir, e só escalar se hit-rate > ~5%.**
- Alvo: **`prospeccao.hunter_resto_todo`** (4.364 nomeáveis; build `scripts/build_hunter_resto.sql`).
  Por sinal: alta 123 / media 260 / baixa 328 / descartar 331 / sem sinal 3.322.
- Runner: **`scripts/hunter_finder_resto.py`** → grava em `prospeccao.hunter_resto` (tabela separada;
  domínio aqui é INFERIDO, qualidade diferente do canal domínio-próprio).
```bash
PGPW=$(docker exec wins_agro_v1_api_1 printenv POSTGRES_PASSWORD)
docker run -d --name hresto --network wins_agro_v1_default -v /root/wins_agro_v1/scripts:/s \
  -e HK=<chave> -e PGPW="$PGPW" -e PGHOST=db -e LIM=100 -e MAXPRI=2 hunterpy python /s/hunter_finder_resto.py
docker logs -f hresto   # mede o % antes de subir LIM/MAXPRI
```
Budget ~1.255 buscas cobre os 711 de sinal (alta+media+baixa) com folga; não cobre os 3.322 sem sinal.

## Achar DOMÍNIO antes do Hunter (teste jun/13, ideia do William) — RESULTADO
Pra os operadores sem domínio próprio, buscar a pessoa/fazenda no Serper p/ recuperar um domínio
e só então alimentar o Hunter. Testado em 2 ângulos (`scripts/enrich_resto_dominio.py`, grava
`prospeccao.resto_referencia`):
- **`pessoa` ("nome" + empresa): MORTO.** 0% domínio real, 0% LinkedIn — só devolve sites de
  data-broker (advdinamico, casadosdados, b2bleads, serasaexperian) que indexam CNPJ/nome.
- **`marca` (nome da fazenda + contexto pecuária): FUNCIONA.** Em fazendas de sinal genético:
  **~11% domínio próprio REAL** (fazendacamparino.com.br, tulipaagropecuaria.com.br, fazendacachoeirao…
  match estrutural domínio×nome da fazenda) + **~45% Instagram** real (DM) + ~1% e-mail direto.
  LinkedIn 0%.
- **Pipeline:** `enrich_resto_dominio.py N MAXPRI marca` (Serper, chave no .env do api) → preenche
  `resto_referencia.dominio_cand`/`instagram`. Depois `hunter_finder_resto.py` (default) consome SÓ
  as fazendas com `dominio_cand` real via `domain` (alta qualidade); `-e COMPANY=1` cai pra
  resolução por razão nas demais. O **Instagram (~45%) é canal paralelo** p/ a Mari (DM), não passa
  pelo Hunter.
- Rodar harvest (dentro do api, que tem SERPER_API_KEY): `docker cp scripts/enrich_resto_dominio.py
  wins_agro_v1_api_1:/tmp/ && docker exec wins_agro_v1_api_1 python /tmp/enrich_resto_dominio.py 711 3 marca`

## Budget Hunter
Starter: ~1.255 buscas / ~2.460 verif restantes; **reseta 11/jul**. As 15 in-ICP custam ~15 buscas.
Chave NÃO fica no `.env` (segurança) — o dono passa por sessão.
