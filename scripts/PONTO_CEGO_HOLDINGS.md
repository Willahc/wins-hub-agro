# Ponto cego das holdings agro

## 1. O problema

A nossa base de prospecção (`cnpj.empresa_rural` / `cnpj.estabelecimento_rural`) foi
ingerida dos Dados Abertos CNPJ da Receita **com filtro de CNAE pecuário/agro** —
veja `scripts/load_rfb_nacional.sh`, que no stream do zip só captura
`"015120[12]"` (`0151201`/`0151202` — bovinos de corte/leite) e poucos CNAEs vet.

Consequência: toda fazenda cuja **pessoa jurídica não é classificada como agro**
nunca entrou na base. O caso emblemático é a **LAMÃO PARTICIPAÇÕES** (CNPJ base
`21098855`), cujo nome fantasia é **"Fazenda Estrela D'Oeste"** — uma fazenda real,
de gado, mas registrada como **holding/participação**. O CNAE dela é da família
imobiliária/holding (`6810` — compra/venda/aluguel de imóveis próprios — ou `646x`
— sociedades de participação), **não** `0151201`. Pelo filtro de ingestão, ela é
invisível para nós, embora seja exatamente um ICP.

Isso é estrutural, não um bug pontual: é prática comum o produtor maior segregar a
terra/o patrimônio numa **holding patrimonial/rural** (CNAE imobiliário ou de
participação) por motivos sucessórios e tributários. Quanto **mais qualificado e
maior** o produtor, **maior** a chance de estar estruturado assim — ou seja, o ponto
cego concentra justamente os leads de maior valor.

## 2. Por que SIGEF/SICAR não resolvem

A tentação seria cruzar com as bases fundiárias do governo. Não fecha:

- **SICAR** (Cadastro Ambiental Rural): os dados públicos são **anonimizados** — o
  download traz a geometria do imóvel e atributos ambientais, mas **não o CPF/CNPJ
  nem o nome do proprietário**. Serve para mapa/área, não para identificar e contatar
  o dono.
- **SIGEF** (georreferenciamento de imóveis rurais, INCRA): a camada pública entrega
  **geometria, área e o Responsável Técnico (RT — o agrimensor/engenheiro)**, mas
  **não o proprietário**. O RT é um terceiro contratado, não o decisor.

Ou seja: as bases fundiárias dizem *onde* está a fazenda, mas não *de quem* é de forma
acionável. Para ligar terra → CNPJ → decisor, o caminho continua sendo o **CNPJ da
Receita** (que é onde mora o sócio/telefone/e-mail), não o cadastro fundiário.

## 3. Os dois vetores de descoberta (independentes)

### Vetor A — sócio em comum
Arquivos: `scripts/load_rfb_socios_holdings.sh` + `scripts/run_socios_join.sql`.

Ideia: pega os **CPFs mascarados distintos dos sócios PF da nossa base agro**
(`cnpj.socio_rural`, `identificador_de_socio='2'`, formato `***NNNNNN**`) e faz
`grep -aF -f` desses CPFs no stream do dump **NACIONAL de Sócios** da RFB — sem
carregar os ~50M de linhas, guardando só o que casa em `cnpj.stg_socios_match`.
O SQL final (`run_socios_join.sql`) refina por **CPF + nome** (over-match por CPF
sozinho, pois o CPF mascarado tem só 6 dígitos visíveis) e mantém **apenas as
empresas que NÃO estão na base agro** (`NOT EXISTS` em `cnpj.empresa_rural`) →
materializa em `prospeccao.holding_blind_spot`.

Resultado: empresas cujo sócio **também é sócio de uma empresa agro nossa** mas que
escaparam do filtro de CNAE. Inclui contagem `n_socios_agro` (quantos sócios agro em
comum — sinal de confiança).

- **Força:** preciso. Quando casa por CPF+nome, há altíssima probabilidade de ser o
  mesmo produtor → a empresa "nova" é quase certamente agro dele. Já vem ancorado no
  nosso universo.
- **Fraqueza:** **perde holdings "puras"** — a fazenda-holding cujo(s) sócio(s)
  **não** aparecem em nenhuma empresa agro nossa (ex.: o produtor estruturou TUDO em
  holding e nunca teve um CNPJ com CNAE de gado). Esses casos não têm âncora e ficam
  fora do vetor A. Também depende da qualidade do match de nome (homônimos com mesmo
  CPF mascarado são filtrados pelo nome, mas variações de grafia podem perder casos).

### Vetor B — CNAE de holding nacional (este loader)
Arquivos: `scripts/load_rfb_estab_holdings.sh` (carga) → staging `cnpj.stg_estab_holding`.

Ideia: o **inverso** do filtro de ingestão. Em vez de buscar CNAE de gado, faz o
stream do dump **NACIONAL de Estabelecimentos** e captura **só os CNAEs de
holding/imobiliária/participação**:

- `"6810` → compra/venda/aluguel de imóveis próprios (`6810201/202/203`) — é onde
  caem as **fazendas-holding** patrimoniais (caso LAMÃO).
- `"6462` → holdings de instituições não-financeiras.
- `"6463` → outras sociedades de participação (holdings).

Carrega TODAS essas empresas do Brasil em `cnpj.stg_estab_holding` (mesma estrutura
c0..c29 de `cnpj.stg_estab`).

- **Força:** **completo** — pega TODAS as holdings/imobiliárias, inclusive as "puras"
  que o vetor A não vê. Não depende de âncora na nossa base.
- **Fraqueza:** **ruidoso** — a imensa maioria das empresas `6810/646x` do Brasil é
  imobiliária urbana, fundo patrimonial, holding de varejo etc., **não agro**. O
  vetor B sozinho não sabe quais são fazendas. Precisa de **sinal extra de "é agro"**
  para filtrar:
  1. **endereço rural** — município de fronteira pecuária / `tipo_logradouro` =
     fazenda/sítio/rodovia / CEP rural / UF do agro (MT/MS/GO/TO…);
  2. **nome com termo agro** — razão social ou nome fantasia contendo
     `FAZENDA|AGRO|PECUARIA|RURAL|NELORE|GADO|SITIO|RANCHO|AGROPECU` (no caso LAMÃO o
     gancho é o fantasia "Fazenda Estrela D'Oeste");
  3. **sócio agro** — sócio da holding também sócio em empresa agro nossa (que é
     exatamente o vetor A).

## 4. Como combinar (A ∩ B) e enriquecer

Os vetores são complementares:

- **A ∩ B** (a holding está no `holding_blind_spot` **e** tem CNAE `6810/646x` na
  `stg_estab_holding`) = **alta confiança**: é holding, é de sócio agro nosso, e o
  CNAE confirma o padrão patrimonial. Promover direto para prospecção.
- **B \ A** com sinal agro (nome/endereço) = **candidatos a investigar**: holdings que
  parecem fazenda mas cujo sócio não está na nossa base — expande o universo além do
  que já conhecemos (é aqui que aparecem produtores totalmente novos).
- **A \ B** = empresas de sócio agro que não são holding por CNAE (outros CNAEs fora
  do filtro original) — ainda úteis, mas fora do escopo "holding".

Passo de enriquecimento (mesma esteira já existente):
1. Filtrar `stg_estab_holding` por sinal agro (nome/endereço) e/ou interseção com
   `prospeccao.holding_blind_spot`.
2. Para os CNPJs selecionados, **BrasilAPI** (`scripts/enrich_decisores.py`, QSA
   grátis) → quadro societário completo, situação, endereço.
3. Materializar em `cnpj.cnpj_rural` / `lead_decisor` na esteira normal de leads
   (decisor, WhatsApp/telefone, ICP com teto de faturamento).

## 5. Limitações honestas

- **CPF mascarado** (vetor A): só 6 dígitos visíveis → match por CPF é over-match;
  dependemos de **CPF + nome** para desambiguar. Homônimo exato com mesmo CPF mascarado
  é raro mas possível; variação de grafia do nome perde casos legítimos.
- **Sinal agro do vetor B é heurístico**: nome/endereço dão recall alto mas precisão
  imperfeita — uma holding agro registrada num endereço urbano de escritório, sem
  termo agro no nome e sem sócio na nossa base, **escapa dos dois vetores**. Esse é o
  resíduo irredutível do método gratuito.
- **Nenhum vetor liga geometria de terra → dono** (vide §2): não conseguimos partir de
  "esta fazenda no mapa" e chegar no CNPJ; só o contrário.
- **Telefone/e-mail/WhatsApp**: o dump da RFB traz contato do estabelecimento, mas
  frequentemente desatualizado ou de contador; enriquecimento via BrasilAPI/QSA não
  entrega WhatsApp do decisor — isso continua dependendo da esteira de enriquecimento
  de contato (regra `check-data-before-external`).
- **O que exigiria base paga:** resolver o ponto cego residual (holding agro sem
  termo agro no nome, endereço urbano, sócio fora da base) exigiria uma fonte que ligue
  **proprietário ↔ imóvel rural ↔ atividade pecuária** de forma identificada — p.ex.
  bases cartoriais/de matrícula, dados de crédito rural identificado, ou provedores de
  dados (Speedio para BR; Apollo/ZoomInfo têm cobertura BR fraca para este nicho).
  Sem isso, A ∪ B + sinal agro é o teto do que se consegue de graça.

## Resumo dos arquivos
- `scripts/load_rfb_socios_holdings.sh` + `scripts/run_socios_join.sql` → **Vetor A**
  (`prospeccao.holding_blind_spot`).
- `scripts/load_rfb_estab_holdings.sh` → **Vetor B** (`cnpj.stg_estab_holding`).
- `scripts/enrich_decisores.py` → enriquecimento QSA/BrasilAPI dos candidatos.
