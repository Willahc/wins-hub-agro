# Relatorio de Fluxo de Dados - Cliente Inteligente

Data da analise: 2026-07-07  
Escopo: analise somente leitura das tres camadas do Cliente Inteligente. Nao foram alterados Nginx, Docker, bancos, One Pages, dashboard ou processo V5.

Arquivos analisados:

- `/root/wins_agro_v1/ci-lojas/cliente-inteligente/data/negocios.json`
- `/root/wins_agro_v1/ci-lojas/cliente-inteligente/negocios/<slug>/index.html`
- `/root/wins_agro_v1/prospeccao-campanella/dashboard.html`
- `/root/wins_agro_v1/prospeccao-campanella/prospeccao_campanella_enriquecida_v3.csv`
- `/root/wins_agro_v1/prospeccao-campanella/campanella_prospeccao_enriquecida_v3.db`
- `/root/wins_agro_v1/ci/index.html`
- `/root/wins_agro_v1/ci-api/app.py`
- `/root/wins_agro_v1/ci-data/ci.db`
- V5 em `/root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/`

Script auxiliar criado:

```text
/root/wins_agro_v1/scripts/auditar_fluxo_dados_cliente_inteligente.py
```

O script e somente leitura: le JSON/HTML/CSV/SQLite e imprime estatisticas em JSON.

## A. Resumo executivo

**Veredito curto: Parcialmente.**

As tres camadas compartilham a mesma origem historica de dados da prospeccao Campanella: ha 813 registros nas One Pages, 813 no dashboard, 813 no CSV e 813 na tabela principal da prospeccao. A correspondencia por `place_id` extraido do `maps_url` e completa: **813 de 813**.

Mas elas **nao conversam de verdade em fluxo operacional**. Hoje os dados estao principalmente copiados/gerados em arquivos estaticos independentes:

- One Pages publicas usam `negocios.json` e HTML estatico.
- Prospecção usa SQLite/CSV/dashboard estatico, com dados internos.
- App comerciante usa estado local no navegador e `ci-api` apenas para conta, backup e publicacao de `/loja/<slug>/`.
- `ci-api` nao tem tabela de estabelecimento, Base Mestre, lead, prospeccao, status/anotacao ou associacao conta <-> lead/One Page.
- V5 esta gerando saidas, mas estas saidas ainda nao alimentam automaticamente One Pages, app ou dashboard atual.

Portanto: **os dados sao parcialmente reaproveitados, mas ainda estao duplicados e isolados em termos de produto.**

## B. Matriz de integracao

| Origem | Destino | Existe integracao? | Como funciona hoje | Problema | Correcao recomendada |
|---|---:|---|---|---|---|
| Prospecção | One Page | Parcial | Ambos derivam dos mesmos 813 leads e batem por `place_id` extraido do `maps_url`; One Page tem slug publico. | Prospecção nao mostra link da One Page; nao guarda slug publico; nao ha `publicavel_status`/`usar_onepage`. | Adicionar `slug_publico`, `url_onepage`, `publicavel_status` e botao "Abrir One Page" no dashboard. |
| One Page | App | Nao | One Page tem botoes por `mailto:` para ativar/atualizar. | Nao passa `place_id`, slug ou seed ao app; app nao sabe qual comercio originou o usuario. | Botao "Sou responsavel" deve abrir app com `?place_id=<id>&slug=<slug>` e o app deve consumir seed publico. |
| App | One Page | Parcial | `ci-api` publica HTML em `/loja/<slug>/index.html` a partir do slug da conta. | A publicacao do app e separada de `/loja/cliente-inteligente/negocios/<slug>/`; risco de duas paginas para o mesmo comercio. | Associar conta a `place_id`/lead e decidir se a loja publicada substitui, complementa ou redireciona a One Page demonstrativa. |
| Prospecção | App | Nao | Prospecção tem segmento, familia, oferta, pitch e scores em SQLite/CSV/dashboard. | App nao importa esses dados; nao ha `master_app_seed.json`; logica de seed no app e local/generica. | Gerar `master_app_seed.json` por `place_id`/segmento e app consumir no onboarding. |
| App | Prospecção | Nao | App salva localmente e no `ci-api` apenas conta/backup/loja publicada. | Prospecção nao sabe quando uma conta foi criada, loja publicada ou lead convertido. | Criar tabelas/API de status: `lead_claims`, `lead_status`, `published_stores`; dashboard consultar esses dados. |
| Base V5 | Prospecção | Parcial/pendente | V5 gera CSV/JSON em `out_v5max`; base atual da prospeccao segue V3 SQLite/CSV/dashboard. | Nenhuma referencia em producao a `out_v5max` ou `master_prospeccao.json`; dashboard atual nao consome V5. | Pos-processar V5 para Base Mestre e regenerar `master_prospeccao.json`. |
| Base V5 | One Page | Nao | One Pages atuais usam `data/negocios.json` estatico. | V5 nao alimenta publicacao; campos V5 podem conter dados internos/incertos. | Gerar `master_public.json` por whitelist e validar antes de publicar. |
| Base V5 | App | Nao | App nao le V5 nem arquivo intermediario. | Sem seed por comercio/segmento vindo do enriquecimento. | Gerar `master_app_seed.json` com modulos recomendados e templates publicaveis/confirmaveis. |

## C. Matriz de campos

| Campo | One Page publica | App comerciante | Prospecção interna | ci-api/backend | Observacao |
|---|---:|---:|---:|---:|---|
| `id` | Nao explicito | Local interno do app | Sim no dashboard como `id` = `place_id` | `contas.id`, sem relacao com lead | Ha IDs diferentes por camada. |
| `place_id` | Nao como campo; extraivel de `maps_url` | Nao | Sim | Nao | Melhor chave tecnica atual para leads. |
| `slug` | Sim via `url`/diretorio | Sim como slug de conta/loja | Nao | Sim em `contas.slug` | Slug publico e slug da conta nao sao associados. |
| `nome` | Sim | Sim como dado local do app | Sim | Nao | Duplicados por nome existem; nao usar como chave. |
| `segmento` | Sim | Ha logica local/generica | Sim | Nao | Nao ha seed compartilhado. |
| familia de segmento | Nao no publico atual | Nao estruturado | Sim (`macrosegmento`/`fam`) | Nao | Deve alimentar app seed, nao One Page sem revisao. |
| endereco | Sim | Local no app | Sim | Nao | Compartilhado por copia, nao por API. |
| telefone | Sim | Local no app | Sim | Nao | Sem associacao central. |
| WhatsApp | Publico quando link gerado por telefone | Local no app | Sim/candidato | Nao | Confianca nao modelada no backend. |
| site | Sim (`tem_site`, alguns links em pagina) | Local no app | Sim | Nao | Dados divergentes possiveis. |
| Instagram | Algumas paginas podem linkar site atual; JSON publico nao tem campo dedicado | Nao | Sim | Nao | Faltando visao publica normalizada. |
| `maps_url` | Sim | Nao | Sim | Nao | Usado indiretamente para extrair `place_id`. |
| nota | Sim | Nao | Sim | Nao | Publico confiavel, mas estatico. |
| avaliacoes | Sim | Nao | Sim | Nao | Publico confiavel, mas estatico. |
| score | Nao no publico validado | Nao | Sim | Nao | Removido da camada publica. |
| tier | Nao no publico validado | Nao | Sim | Nao | Removido da camada publica. |
| prioridade | Nao no publico validado | Nao | Sim | Nao | Removido da camada publica. |
| CNPJ | Nao | Nao | Sim | Nao | Interno/candidato; nao publicar. |
| CNPJ confidence | Nao | Nao | Sim | Nao | Interno. |
| dor dominante | Nao | Nao | Sim | Nao | Interno. |
| reclamacoes | Nao | Nao | Sim | Nao | Interno. |
| oferta recomendada | Nao | Nao estruturado | Sim | Nao | Deve virar seed/abordagem por visao. |
| modulos recomendados | Nao | Parcial/generico no app | Sim como fits/oferta/secundarias | Nao | Isolado no CSV/SQLite. |
| pitch | Nao | Nao | Sim | Nao | Interno. |
| mensagem WhatsApp | Nao | App gera mensagens operacionais | Parcial no V5/CSV | Nao | Sem fluxo compartilhado. |
| status funil | Nao | Nao | Sim no CSV/SQLite, mas sem backend vivo | Nao | Status/anotacao atual do dashboard e localStorage. |
| anotacao de campo | Nao | Nao | LocalStorage no dashboard | Nao | Nao persistida centralmente. |
| URL da One Page | Sim no JSON como `url` relativa | Nao | Nao | Nao | Prospecção nao mostra link publico. |
| slug de loja publicada no app | Nao relacionado | Sim em `N.conta.slug` | Nao | Sim em `contas.slug` | Publica em `/loja/<slug>/`, separado da One Page demo. |

## D. Analise de chave unica

### Chaves encontradas hoje

- **`place_id`**:
  - existe explicitamente na prospeccao SQLite/CSV/dashboard;
  - nao existe como campo no JSON publico, mas e extraivel de `maps_url`;
  - nao existe no app nem no `ci-api`.

- **`slug`**:
  - existe no JSON publico como parte do caminho `url`;
  - existe como diretorio nas One Pages;
  - existe no `ci-api` como slug escolhido/criado pela conta;
  - nao existe na prospeccao.

- **`nome`**:
  - existe em todas as bases de lead;
  - possui duplicados.

### Resultado da auditoria de identidade

| Item | Resultado |
|---|---:|
| Registros no JSON publico | 813 |
| Diretorios de paginas publicas | 813 |
| Registros no dashboard | 813 |
| Registros na tabela `estabelecimentos_enriquecidos_v3` | 813 |
| Linhas no CSV V3 | 813 |
| `place_id` publicos extraidos de `maps_url` | 813 |
| `place_id` na prospeccao | 813 |
| `place_id` em ambas as camadas | 813 |
| Slugs publicos unicos | 813 |
| Slugs com pagina correspondente | 813 |
| Duplicados por `place_id` | 0 |
| Duplicados por slug publico | 0 |
| Nomes unicos | 807 |
| Nomes duplicados | 5 grupos |

Duplicados por nome encontrados nas duas camadas:

- `irmãos andrade` = 3
- `orvalhus moda masculina` = 2
- `loja vivo` = 2
- `batata dipz` = 2
- `açougue coração valente` = 2

### Qual chave deveria ser usada

Recomendacao:

1. **Chave canonica de lead/estabelecimento: `place_id`**
   - Ja e unica na prospeccao.
   - Bate 813/813 com as One Pages quando extraida de `maps_url`.
   - Evita colisao por nome.

2. **Slug publico: campo derivado e versionado**
   - Usar para URL amigavel.
   - Deve ser armazenado junto ao `place_id`.
   - Nao deve ser a unica chave porque pode mudar por SEO, correcao de nome ou colisao.

3. **ID interno da Base Mestre**
   - Criar `ci_master_id` estavel.
   - Guardar `place_id`, `slug_publico`, `slug_app`, fontes e historico.

Risco de usar nome como chave: alto. Ha nomes duplicados e nomes podem mudar por acento, grafia, unidade, shopping, franquia ou normalizacao.

## E. Achados criticos

### 1. As camadas compartilham origem, nao fluxo

Apesar do match 813/813 por `place_id`, nao existe fluxo vivo entre:

- One Page -> App
- App -> Prospecção
- Prospecção -> App
- V5 -> camadas atuais

### 2. `ci-api` nao tem modelo de estabelecimento

Banco `ci-data/ci.db`:

| Tabela | Linhas | Colunas |
|---|---:|---|
| `contas` | 0 | `id`, `fone`, `slug`, campos sensiveis redigidos, `criado`, `backup_ver` |
| `sessions` | 0 | identificador de sessao redigido, `conta_id`, `criado`, `expira` |

Nao existem:

- tabela de estabelecimentos;
- tabela de Base Mestre;
- tabela de prospeccao;
- tabela de status/anotacoes;
- associacao conta <-> estabelecimento;
- associacao loja publicada <-> lead/prospecção.

### 3. One Page -> App esta quebrado

One Pages possuem:

- indice com link `mailto:` para ativar pagina;
- paginas individuais com `ownerForm(nome)`, tambem `mailto:`;
- botao "Sou o dono, quero atualizar".

Nao possuem:

- link para app com `place_id`;
- link para app com `slug`;
- rota de reivindicacao;
- parametro de origem;
- seed de onboarding.

### 4. App -> One Page cria pagina separada

O app publica via `PUT /api/loja` em:

```text
/data/lojas/<slug>/index.html
```

No host isso e montado sob `ci-lojas`, ficando publico como:

```text
/loja/<slug>/
```

Isso nao atualiza:

```text
/loja/cliente-inteligente/negocios/<slug>/
```

Conclusao: ha risco real de duas paginas para o mesmo comercio: uma demonstrativa e outra publicada pelo comerciante.

### 5. Prospecção nao aponta para a One Page

O dashboard interno contem score, tier, CNPJ, pitch e ficha local, mas a auditoria nao encontrou referencias a:

- `/loja/cliente-inteligente`
- `One Page`
- slug publico
- `place_id` como texto de integracao

Ele nao oferece botao "Abrir One Page publica".

### 6. Status/anotacoes nao sao persistidos centralmente

No dashboard atual:

- `localStorage` aparece para `ci_prospec_note_`;
- anotacoes ficam no navegador;
- nao ha API/tabela para status de campo.

Isso impede equipe, historico central, conciliacao com app e marcacao de convertido.

### 7. V5 esta isolado

Status observado:

- Processo `enriquecer_v5_max.py` segue rodando.
- `out_v5max/prospectos_v5max_externos.csv`: 723 linhas, atualizado em 2026-07-07 20:31:30.
- `out_v5max/prospectos_v5max_externos.json`: 723 registros, atualizado em 2026-07-07 20:31:30.

Busca em producao nao encontrou referencias a:

- `prospectos_v5max`
- `out_v5max`
- `v5max`
- `master_public`
- `master_app_seed`
- `master_prospeccao`

Logo, V5 ainda nao alimenta as camadas atuais.

### 8. Separacao publico vs interno esta segura no estado validado

Validador executado:

```bash
python3 /root/wins_agro_v1/scripts/validar_cliente_inteligente_publico.py
```

Resultado:

```text
OK JSON publico: 813 registros
OK dataset embutido: 813 registros
OK paginas publicas: 813 paginas
```

Grep complementar nao encontrou no diretorio publico validado os padroes proibidos:

- `Score interno`
- `"score"`
- `"tier"`
- `"prioridade"`
- `CNPJ`
- `cnpj`
- `CI_FALLBACK_RENDER_PROSPEC`

## F. Plano de correcao para as camadas conversarem

### Fase 1 - Criar Base Mestre

Criar uma tabela/arquivo canonico com:

- `ci_master_id`
- `place_id`
- `slug_publico`
- `nome_comercial`
- dados publicos
- dados internos
- confianca por campo
- origem/fonte
- timestamps

Manter `place_id` como chave de reconciliacao de lead.

### Fase 2 - Criar views derivadas

Gerar tres saidas separadas:

```text
master_public.json
master_app_seed.json
master_prospeccao.json
```

Regras:

- `master_public.json`: whitelist publica, sem CNPJ/score/tier/dor/pitch.
- `master_app_seed.json`: segmento, familia, modulos, templates e onboarding.
- `master_prospeccao.json`: visao interna completa.

### Fase 3 - Adicionar chave unica consistente

Adicionar em todas as camadas:

- `place_id`
- `slug_publico`
- `ci_master_id`

No app/ci-api:

- adicionar `place_id` opcional na conta/loja;
- associar conta a lead;
- impedir slug duplicado para mesmo estabelecimento.

### Fase 4 - Atualizar prospecção

No dashboard interno:

- mostrar URL da One Page publica;
- botao "Abrir One Page";
- botao "Abrir app como seed";
- exibir `publicavel_status`;
- exibir se lead ja foi reivindicado/cadastrado/publicado.

### Fase 5 - Atualizar One Page

Trocar `mailto:` isolado por fluxo rastreavel:

```text
https://ci.winshubagro.cloud/?claim=<place_id>&slug=<slug_publico>
```

ou rota equivalente.

Botao sugerido:

```text
Sou o responsavel por este comercio
```

Esse fluxo deve preservar `place_id`, slug, segmento e origem.

### Fase 6 - Atualizar app para receber seed

O app deve:

- ler `claim/place_id/slug` da URL;
- buscar seed publico/app em arquivo/API;
- pre-configurar onboarding por segmento;
- pedir confirmacao do comerciante;
- nunca mostrar score, dor ou CNPJ candidato.

### Fase 7 - Persistir status/anotacao no backend

Criar em `ci-api` ou backend dedicado:

- `leads`
- `lead_status`
- `lead_notes`
- `lead_claims`
- `published_stores`

Substituir `localStorage` da prospeccao por persistencia central autenticada.

### Fase 8 - Marcar lead como convertido

Ao criar conta/publicar loja:

- associar `conta_id` a `place_id`;
- marcar status como `reivindicado`, `cadastrado`, `publicado` ou `cliente_ativo`;
- refletir no dashboard de prospeccao;
- opcionalmente redirecionar One Page demonstrativa para loja oficial.

## G. Veredito final

| Classificacao | Estado |
|---|---|
| Dados conversando de verdade | Nao |
| Dados parcialmente reaproveitados | Sim |
| Dados apenas copiados/duplicados | Sim, em grande parte |
| Dados isolados | Sim, especialmente app/ci-api e V5 |

Conclusao final:

**As camadas ainda nao conversam como sistema integrado.** Elas compartilham uma base historica coerente e reconciliavel por `place_id`, mas o fluxo operacional entre One Page, app e prospeccao ainda nao existe. O ponto mais forte e a identidade: 813/813 batem por `place_id` extraido do `maps_url`. O ponto mais fraco e a falta de backend comum: nao ha Base Mestre, associacao conta-lead, status central ou seed de onboarding.

O proximo passo correto e construir a Base Mestre e gerar as tres views: `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
