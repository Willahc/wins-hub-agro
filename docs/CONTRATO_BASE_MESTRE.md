# Contrato da Base Mestre - Cliente Inteligente

## Objetivo

A Base Mestre deve ser a fonte canonica para reconciliar One Pages, App comerciante e Prospecção interna. Ela deve preservar a identidade do estabelecimento por `place_id` e gerar views separadas para cada camada.

## Chave canonica

Campo principal: `place_id`.

Motivo:

- e extraido do `maps_url`;
- bate 813/813 entre One Pages e Prospecção na auditoria atual;
- e mais estavel que nome comercial ou slug;
- permite manter `slug_publico` e `slug_app` como identificadores de rota, nao como identidade principal.

## Campos obrigatorios

| Campo | Uso |
|---|---|
| `place_id` | Chave tecnica canonica do estabelecimento. |
| `slug_publico` | Slug da One Page inicial. |
| `slug_app` | Slug da loja publicada/reivindicada no app. |
| `nome_comercial` | Nome publico do comercio. |
| `segmento` | Segmento principal. |
| `familia_segmento` | Agrupamento para modulos e seed. |
| `endereco` | Endereco publico. |
| `latitude` | Coordenada publica. |
| `longitude` | Coordenada publica. |
| `telefone` | Telefone publico. |
| `whatsapp_publico` | WhatsApp confirmado/publicavel. |
| `site_oficial` | Site publico confiavel. |
| `instagram` | Perfil publico. |
| `maps_url` | URL de origem para mapa e reconciliacao. |
| `nota` | Nota publica. |
| `num_avaliacoes` | Quantidade publica de avaliacoes. |
| `onepage_url` | URL da One Page demonstrativa/publica. |
| `app_claim_url` | URL de reivindicacao no App. |
| `prospeccao_url` | URL interna da ficha de prospeccao. |
| `publicavel_status` | Estado de publicacao publica. |
| `usar_onepage` | Flag para gerar/exibir One Page. |
| `usar_app_comerciante` | Flag para gerar seed do app. |
| `usar_prospeccao` | Flag para aparecer na ferramenta interna. |
| `nivel_confianca_publico` | Confianca dos dados publicos. |
| `nivel_confianca_interno` | Confianca da visao interna. |

## Campos internos

Estes campos podem existir na Base Mestre, mas nao podem ir para `master_public.json`:

| Campo | Uso permitido |
|---|---|
| `cnpj` | Prospecção e validacao interna. |
| `cnpj_confidence` | Nivel de confianca do CNPJ. |
| `score_comercial` | Priorizacao interna. |
| `lead_tier` | Priorizacao interna. |
| `prioridade` | Roteiro e operacao de campo. |
| `dor_dominante` | Diagnostico interno. |
| `reclamacoes` | Evidencia interna, quando aplicavel. |
| `pitch_presencial` | Abordagem de campo. |
| `mensagem_whatsapp` | Abordagem interna. |
| `modulos_recomendados` | Seed do app e prospeccao. |
| `status_funil` | Estado comercial centralizado. |
| `anotacoes` | Historico operacional interno. |

## Views obrigatorias

### `master_public.json`

Destino: One Pages publicas.

Regra: somente whitelist publica.

Nao pode conter CNPJ, score, tier, prioridade, dor, reclamacoes, pitch ou confianca interna.

### `master_app_seed.json`

Destino: App comerciante.

Pode conter:

- `place_id`;
- `slug_publico`;
- segmento e familia de segmento;
- modulos recomendados;
- configuracao inicial;
- produtos/servicos sugeridos;
- URL de reivindicacao.

Nao deve expor dor/reclamacao como texto bruto para o comerciante.

### `master_prospeccao.json`

Destino: ferramenta interna.

Pode conter dados publicos e internos, desde que acompanhados de confianca, status e origem quando necessario.

## Estados de confianca recomendados

- `CONFIRMADO`
- `PROVAVEL`
- `CANDIDATO`
- `FRACO`
- `NAO_ENCONTRADO`

Campos com `CANDIDATO`, `FRACO` ou `NAO_ENCONTRADO` nao devem ser publicados automaticamente.
