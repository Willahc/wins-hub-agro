# Plano de Integracao das Camadas - Cliente Inteligente

## Objetivo

Transformar a base historica compartilhada de 813 estabelecimentos em integracao operacional entre One Pages, App comerciante e Prospecção interna.

## Fase 1 - Base Mestre

Criar `ci_master_build.py`.

Responsabilidades:

- ler fontes atuais de One Pages, Prospecção e saidas V5;
- consolidar por `place_id`;
- manter `slug_publico` e `slug_app` separados;
- classificar confianca por campo;
- gerar views separadas.

Saidas obrigatorias:

```text
master_public.json
master_app_seed.json
master_prospeccao.json
```

## Fase 2 - Prospecção

Atualizar Prospecção para consumir `master_prospeccao.json`.

Entregas:

- incluir `onepage_url` na ficha;
- adicionar botao "Abrir pagina publica";
- adicionar botao para abrir app com `place_id` e `slug`;
- persistir status e anotacoes fora de `localStorage`;
- registrar estados como cadastrado, reivindicado, convertido e cliente ativo.

## Fase 3 - One Pages publicas

Atualizar One Pages a partir de `master_public.json`.

Entregas:

- gerar paginas somente por whitelist publica;
- incluir botao "Sou o responsavel por este comercio";
- passar `place_id` e `slug` para o App;
- manter validacao publica antes de publicar;
- nao publicar campos internos.

## Fase 4 - App comerciante

Atualizar App para aceitar contexto de reivindicacao.

Entregas:

- ler `place_id` e `slug` na URL;
- buscar seed em `master_app_seed.json` ou rota equivalente;
- pre-configurar onboarding por segmento;
- sugerir modulos, produtos/servicos e configuracoes iniciais;
- salvar claim localmente ate o usuario autenticar;
- criar vinculo conta <-> estabelecimento somente com conta/sessao valida;
- registrar a origem da reivindicacao.

## Fase 5 - ci-api

Persistencia operacional do claim ja iniciada.

Tabelas:

- `estabelecimento_claims` para vinculo conta <-> estabelecimento.

Responsabilidades:

- associar conta a `place_id`;
- registrar quando o responsavel autentica e reivindica o comercio;
- expor somente payload seguro em `claim-seed`;
- manter trilha minima sem expor CNPJ, score ou texto interno.

Limite atual:

- existe verificacao manual/documental do responsavel via painel admin;
- o painel admin esta disponivel em `https://ci.winshubagro.cloud/admin-claims.html`;
- endpoints admin protegidos por token (`x-admin-token`);
- a prospeccao ainda nao consome a tabela de claims.

## Comandos de auditoria

Validar camada publica:

```bash
python3 /root/wins_agro_v1/scripts/validar_cliente_inteligente_publico.py
```

Auditar fluxo entre camadas:

```bash
python3 /root/wins_agro_v1/scripts/auditar_fluxo_dados_cliente_inteligente.py
```

## Ordem recomendada

1. Base Mestre e views.
2. Prospecção lendo view interna.
3. One Pages lendo view publica.
4. App lendo seed e reivindicacao.
5. Backend persistindo vinculos e status.

Nao alterar Nginx, Docker ou rotas publicas antes de a Base Mestre e os validadores estarem prontos.
