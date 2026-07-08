# Fluxo de Dados das 3 Camadas - Cliente Inteligente

## Veredito

Classificacao: **parcialmente integrado**.

One Pages, App comerciante e Prospecção interna compartilham a mesma base historica de 813 estabelecimentos. A chave tecnica mais confiavel hoje e o `place_id` extraido do `maps_url`. A correspondencia entre One Pages e Prospecção bate **813/813**.

O problema e que essa correspondencia ainda nao virou fluxo operacional completo. As camadas nao possuem Base Mestre comum e nao trocam status, mas o vinculo conta <-> estabelecimento ja e persistido via `/api/claim-estabelecimento` apos login/cadastro no app.

## Matriz de fluxo atual

| Origem | Destino | Existe integracao? | Como funciona hoje | Problema | Correcao recomendada |
|---|---|---|---|---|---|
| Prospecção | One Page | Parcial por dados historicos | Ambas derivam dos mesmos 813 estabelecimentos e reconciliam por `place_id`. | A ficha de prospeccao nao mostra link da One Page correspondente. | Incluir `onepage_url` e botao "Abrir pagina publica". |
| One Page | App | Operacional | A One Page publica o botao "Sou o responsavel por este comercio" com `claim_place_id` e `claim_slug`. | O app ja persiste o vinculo via `/api/claim-estabelecimento` apos login/cadastro. | `claim_place_id` leva ao App, `claim-seed` preenche onboarding e `/api/claim-estabelecimento` persiste o vinculo. |
| App | One Page | Parcial, mas separado | O app publica em `/loja/<slug>/`. | Esse caminho e separado de `/loja/cliente-inteligente/negocios/<slug>/`; pode haver duas paginas para o mesmo comercio. | Definir se a pagina do app substitui, complementa ou reivindica a One Page inicial. |
| Prospecção | App | Nao operacional | Segmento, oferta e modulos existem isolados na prospeccao. | O app nao usa esses dados para onboarding ou seed. | Gerar `app_seed` por segmento e `place_id`. |
| App | Prospecção | Parcial | O app ja preenche seed seguro e tenta persistir o claim. | Ainda nao ha verificacao manual/documental do responsavel. | Persistir o claim em `estabelecimento_claims` e depois expor status para a prospecção. |
| Base V5 | Prospecção | Pendente | V5 gera saidas em disco. | A prospeccao atual ainda nao consome `master_prospeccao.json`. | Pos-processar V5 para Base Mestre e view interna. |
| Base V5 | One Page | Pendente | One Pages usam JSON publico estatico atual. | V5 pode conter dados internos/incertos e nao pode ir direto para publico. | Gerar `master_public.json` por whitelist. |
| Base V5 | App | Pendente | App nao le saidas V5. | Sem seed por comercio/segmento vindo do enriquecimento. | Gerar `master_app_seed.json`. |

## Dados compartilhados hoje

| Campo | One Page publica | App comerciante | Prospecção interna | ci-api/backend | Observacao |
|---|---|---|---|---|---|
| `place_id` | Extraivel de `maps_url` | Nao | Sim | Nao | Melhor chave tecnica atual. |
| `slug` | Sim, slug publico | Sim, slug de loja publicada | Nao centralizado | Sim para publicacao | Slugs ainda nao estao associados ao mesmo estabelecimento. |
| `nome` | Sim | Local/conta | Sim | Parcial | Pode variar; nao deve ser chave canonica. |
| `segmento` | Sim | Generico/local | Sim | Nao | Deve alimentar seed do app. |
| endereco/telefone | Sim | Local/conta | Sim | Parcial | Dados publicos quando confiaveis. |
| WhatsApp/site/Instagram | Sim quando publico | Local/conta | Sim | Nao centralizado | Precisa de confianca por origem. |
| `maps_url` | Sim | Nao | Sim | Nao | Fonte atual para extrair `place_id`. |
| nota/avaliacoes | Sim | Nao | Sim | Nao | Publicavel se for dado publico. |
| score/tier/prioridade | Nao | Nao | Sim | Nao | Interno; proibido em One Pages. |
| CNPJ/confidence | Nao | Nao como oficial sem confirmacao | Sim | Nao | Interno ou confirmavel. |
| dor/reclamacoes/pitch | Nao | Nao como texto bruto | Sim | Nao | Interno. |
| status/anotacao | Nao | Nao centralizado | Local/isolado | Nao | Deve ir para backend. |
| claim do responsavel | Nao | Parcial | Botao publico e seed seguro ja existem | Sim no backend, apos login | Persistir em `estabelecimento_claims` por `place_id`. |
| URL da One Page | Sim | Nao | Nao | Nao | Deve entrar em `master_prospeccao.json`. |
| slug de loja app | Nao associado | Sim | Nao | Sim | Deve ser ligado ao `place_id`. |

## Conclusao

Os dados sao reconciliaveis e o claim ja atravessa One Page -> App -> backend. O proximo passo e usar a tabela de claims como fonte operacional para status, verificacao e operacao interna.

## Painel Administrativo de Claims

O ecossistema possui agora um painel administrativo simples para revisar e moderar claims:

- **URL:** `https://ci.winshubagro.cloud/admin-claims.html`
- **Protecao:** header `x-admin-token` obrigatório
- **Endpoints admin:**
  - `GET /api/admin/claims` — lista claims com filtros
  - `PATCH /api/admin/claims/{id}` — atualiza status
  - `GET /api/admin/claims/health` — health check
- **Status permitidos:** pending_verification, claimed, verified, rejected
- **Dados expostos:** apenas campos seguros (nome, segmento, telefone, endereco, status, datas)
- **Dados protegidos:** CNPJ, score, tier, prioridade, dor, reclamacoes, pitch, confidence, fontes_json

A verificação documental/manual do responsavel continua sendo um processo operacional. Claims não verificados não devem ser tratados como propriedade confirmada.
