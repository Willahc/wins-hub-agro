# Arquitetura Cliente Inteligente

## Componentes

```text
ci.winshubagro.cloud
├── /                         -> App comerciante em /root/wins_agro_v1/ci
├── /api/*                    -> ci-api em /root/wins_agro_v1/ci-api
├── /loja/cliente-inteligente -> One Pages publicas atuais
├── /loja/<slug>/             -> lojas/cardapios publicados pelo app
└── /prospec/                 -> prospeccao interna restrita
```

## App comerciante

Pasta:

```text
/root/wins_agro_v1/ci
```

Caracteristicas:

- app estatico single-file;
- PWA/offline-first;
- persistencia local em IndexedDB via Dexie;
- `localStorage` como espelho/fallback;
- bibliotecas self-hosted em `ci/libs`;
- usa `ci-api` para conta, backup cifrado e publicacao de loja/cardapio.

Dados usados:

- dados operacionais confirmados pelo comerciante;
- configuracoes de PDV, estoque, caixa, delivery, CRM e fidelidade;
- no futuro, seed por segmento vindo de `master_app_seed.json`.

## ci-api

Pasta:

```text
/root/wins_agro_v1/ci-api
```

Banco:

```text
/root/wins_agro_v1/ci-data/ci.db
```

Responsabilidades atuais:

- cadastro/login por telefone e senha;
- sessoes;
- backup cifrado no cliente;
- recuperacao;
- publicacao de loja via HTML estatico.

Rotas principais:

- `GET /api/health`
- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`
- `PUT /api/backup`
- `GET /api/backup`
- `PUT /api/loja`
- `GET /api/me`
- `PUT /api/recovery`
- `GET /api/recovery/info`
- `POST /api/recovery/reset`

Limites atuais:

- ainda nao guarda Base Mestre;
- ainda nao persiste status/anotacao da prospeccao;
- ainda nao e multi-tenant completo.

## One Pages publicas

Producao:

```text
/root/wins_agro_v1/ci-lojas/cliente-inteligente
```

Staging/teste:

```text
/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2
```

Conteudo:

- indice publico;
- `data/negocios.json`;
- assets publicos;
- paginas individuais `negocios/<slug>/index.html`.

Regra arquitetural:

- One Page publica deve ser alimentada apenas por uma visao publica da Base Mestre.
- Campos internos devem ser removidos por whitelist antes da geracao.
- Nunca reaproveitar diretamente `master_prospeccao.json` em paginas publicas.

## Prospecção interna

Pasta:

```text
/root/wins_agro_v1/prospeccao-campanella
```

Arquivos relevantes:

- `dashboard.html`
- `gerar_dashboard.py`
- `classificar.py`
- `campanella_prospeccao.db`
- `campanella_prospeccao_enriquecida.db`
- `campanella_prospeccao_enriquecida_v3.db`

Uso:

- mapa de leads;
- filtros;
- tier/score;
- CNPJ candidato;
- dor e reclamacoes;
- pitch e oferta;
- status e anotacoes de campo.

Estado atual:

- o dashboard e estatico e gerado por `gerar_dashboard.py`;
- anotacoes locais ainda dependem de `localStorage`;
- a persistencia central de status/anotacoes e trabalho pendente.

## Nginx

Pasta:

```text
/root/wins_agro_v1/nginx
```

Responsabilidades:

- HTTPS;
- roteamento de `ci.winshubagro.cloud`;
- proxy para `ci-api`;
- servico estatico do app e One Pages;
- protecao da prospeccao por Basic Auth;
- CSP e headers de seguranca.

Nao documentar:

- conteudo de arquivos de autenticacao;
- credenciais;
- chaves privadas;
- qualquer valor sensivel de acesso.

## Docker

Compose:

```text
/root/wins_agro_v1/docker-compose.yml
```

Servicos esperados:

- `nginx`
- `ci-api`
- `api`
- `db`
- `certbot`

O `ci-api` e separado da API principal do WiNS Agro. A API principal fica em `/root/wins_agro_v1/app` e atende o produto Agro, nao deve receber a nova Base Mestre do Cliente Inteligente sem decisao arquitetural explicita.

## Fluxo futuro de dados

```text
V5 MAX + bases atuais
        |
        v
Base Mestre Cliente Inteligente
        |
        +--> master_public.json      -> One Pages
        +--> master_app_seed.json    -> App comerciante
        +--> master_prospeccao.json  -> Prospecção interna
```

## Estado atual da integracao

Veredito: **parcialmente integrado**.

As tres camadas compartilham a base historica Campanella com 813 estabelecimentos. A correspondencia entre One Pages e Prospecção fecha **813/813** usando `place_id` extraido do `maps_url`.

O ponto importante: essa correspondencia e uma reconciliacao de dados, nao uma integracao operacional. As camadas ainda usam arquivos, bancos e estados separados:

- One Pages usam `ci-lojas/cliente-inteligente/data/negocios.json` e paginas estaticas em `negocios/<slug>/index.html`.
- Prospecção usa dashboard estatico, CSV e SQLite proprios.
- App comerciante usa IndexedDB/localStorage e `ci-api` para conta, backup e publicacao de loja.
- `ci-api` ainda nao possui tabela de estabelecimento, Base Mestre, claims, status de prospeccao ou associacao conta <-> lead.

## Matriz de fluxo atual

| Fluxo | Hoje | Necessario |
|---|---|---|
| Prospecção -> One Page | Nao mostra link da One Page correspondente. | Incluir `onepage_url` e botao "Abrir pagina publica". |
| One Page -> App | Usa `mailto:` ou contato generico. | Botao "Sou o responsavel por este comercio" passando `place_id` e `slug`. |
| App -> One Page | Publica em `/loja/<slug>/`, separado de `/loja/cliente-inteligente/negocios/<slug>/`. | Definir se a pagina do app substitui, complementa ou reivindica a One Page inicial. |
| Prospecção -> App | Nao alimenta onboarding nem seed. | Gerar `app_seed` por segmento e `place_id`. |
| App -> Prospecção | Nao marca lead como cadastrado, reivindicado ou convertido. | Status centralizado no backend. |
| V5 -> camadas | V5 gera saidas, mas ainda nao alimenta One Pages, App ou Prospecção. | Base Mestre e views separadas por finalidade. |

## Chave canonica recomendada

Usar `place_id` como chave tecnica de reconciliacao dos estabelecimentos, porque:

- e extraivel do `maps_url` das One Pages;
- existe na Prospecção;
- bate 813/813 na auditoria atual;
- evita usar nome comercial como chave, que e fragil por acento, abreviacao, matriz/filial e mudanca de marca.

`slug_publico` deve continuar existindo para URL publica. `slug_app` deve representar a loja publicada/reivindicada no app. A Base Mestre deve armazenar ambos, associados ao mesmo `place_id`.

## Trabalho pendente

1. Construir Base Mestre.
2. Gerar `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
3. Persistir anotacoes/status fora de `localStorage`.
4. Rebuild das One Pages por whitelist publica.
5. Design system seguro e incremental.
