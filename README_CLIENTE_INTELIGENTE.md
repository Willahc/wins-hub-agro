# Cliente Inteligente

Este documento resume o ecossistema Cliente Inteligente dentro da VPS do projeto WiNS Agro.

O Cliente Inteligente e composto por tres superficies que precisam compartilhar uma Base Mestre unica, mas com regras diferentes de exposicao de dados:

1. **App do comerciante**
   - URL: `https://ci.winshubagro.cloud`
   - Pasta de producao: `/root/wins_agro_v1/ci`
   - Backend auxiliar: `/root/wins_agro_v1/ci-api`
   - Dados: configuracao do comercio, PDV, estoque, caixa, delivery, CRM, fidelidade, cardapio e backup cifrado.

2. **One Pages publicas**
   - URL atual: `https://ci.winshubagro.cloud/loja/cliente-inteligente/`
   - Pasta de producao: `/root/wins_agro_v1/ci-lojas/cliente-inteligente`
   - Pasta de staging/teste: `/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2`
   - Dados: somente informacoes publicas confiaveis.

3. **Prospecção interna**
   - URL: `https://ci.winshubagro.cloud/prospec/`
   - Pasta de producao: `/root/wins_agro_v1/prospeccao-campanella`
   - Dados: informacoes internas de venda, priorizacao, score, dor, pitch, CNPJ candidato e status de campo.
   - Acesso: protegido por Nginx/Basic Auth. Nao documentar nem versionar credenciais.

## Pastas principais

| Pasta | Uso | Status |
|---|---|---|
| `/root/wins_agro_v1/ci` | App comerciante estatico/PWA | Producao |
| `/root/wins_agro_v1/ci-api` | Backend minimo do Cliente Inteligente | Producao |
| `/root/wins_agro_v1/ci-data` | SQLite e backups do `ci-api` | Producao/dados |
| `/root/wins_agro_v1/ci-lojas/cliente-inteligente` | One Pages publicas atuais | Producao |
| `/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2` | Copia/teste das One Pages | Staging/teste |
| `/root/wins_agro_v1/prospeccao-campanella` | Dashboard interno de prospeccao | Producao restrita |
| `/root/wins_agro_v1/enriquecimento_v5max_cnpj` | Enriquecimento V5 MAX CNPJ | Processo em background |
| `/root/wins_agro_v1/nginx` | Configuracao de rotas e seguranca | Producao |

## Dados publicos vs internos

### Pode ir para One Page publica

- nome comercial
- categoria/segmento publico
- endereco
- telefone publico
- WhatsApp confirmado/publico
- site oficial
- Instagram/Facebook publicos
- cardapio/delivery publico
- mapa/rota
- horario
- nota e quantidade de avaliacoes publicas
- descricao positiva e neutra

### Nao pode ir para One Page publica

- CNPJ candidato/provavel
- razao social sem revisao
- socios
- score comercial
- lead tier
- prioridade de visita
- dor/reclamacao
- pitch interno
- risco legal
- confianca interna
- qualquer campo incerto marcado como candidato/fraco/nao encontrado

## Validador de dados publicos

Antes de publicar ou regenerar One Pages, rode:

```bash
cd /root/wins_agro_v1
python3 scripts/validar_cliente_inteligente_publico.py
```

O validador falha se encontrar campos internos no JSON publico, dataset embutido ou paginas HTML publicas.

## Como verificar o V5 sem parar o processo

Use apenas comandos de leitura:

```bash
ps aux | grep enriquecer_v5_max | grep -v grep
```

Para acompanhar os arquivos de saida sem interferir:

```bash
stat /root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.csv
stat /root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.json
```

Nao matar, reiniciar ou editar arquivos do processo V5 enquanto estiver rodando.

## Ultima rodada de correcao

Backup usado:

```text
/root/wins_agro_v1/backups_codex_20260707_1155
```

Correcoes aplicadas:

- Remocao de `tier`, `prioridade` e `score` dos artefatos publicos das One Pages.
- Remocao de caixas "Score interno" das 813 paginas publicas.
- Ajuste do indice publico para nao renderizar classificacao interna.
- Regeneracao do dashboard de prospeccao pelo gerador oficial, removendo fallback emergencial anexado.
- Correcao de interpolacao JavaScript no gerador da prospeccao.
- Criacao do validador `scripts/validar_cliente_inteligente_publico.py`.

## Trabalho pendente conhecido

1. Construir a Base Mestre Cliente Inteligente.
2. Gerar `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
3. Persistir anotacoes/status da prospeccao fora de `localStorage`.
4. Regerar One Pages a partir de whitelist publica.
5. Aplicar design system com seguranca, sem CSS global destrutivo.

## Veredito atual de integracao

Classificacao: **parcialmente integrado**.

As One Pages, o App do comerciante e a Prospecção compartilham a mesma base historica de 813 estabelecimentos. A chave tecnica mais confiavel hoje e o `place_id` extraido do `maps_url`, com correspondencia completa entre One Pages e Prospecção: **813/813**.

Ainda assim, as camadas nao conversam operacionalmente. Hoje nao existe Base Mestre publicada para as tres superficies, nem associacao conta <-> estabelecimento, nem seed de onboarding vindo da prospeccao, nem status centralizado de lead convertido.

Documentos detalhados:

- `docs/FLUXO_DADOS_3_CAMADAS.md`
- `docs/CONTRATO_BASE_MESTRE.md`
- `docs/PLANO_INTEGRACAO_CAMADAS.md`

## Auditoria de fluxo de dados

Rodar a auditoria somente leitura:

```bash
cd /root/wins_agro_v1
python3 scripts/auditar_fluxo_dados_cliente_inteligente.py
```

Resultado esperado da auditoria atual:

- 813 registros nas One Pages publicas.
- 813 registros na base principal de prospeccao.
- 813/813 correspondentes por `place_id` extraido de `maps_url`.
- 0 duplicados por `place_id` na comparacao auditada.
- Integracao operacional ainda pendente.

## Proximo passo arquitetural

Construir a Base Mestre Cliente Inteligente e gerar tres visoes:

```text
master_public.json       -> One Pages publicas
master_app_seed.json     -> App comerciante
master_prospeccao.json   -> Prospecção interna
```

`master_public.json` deve nascer de whitelist e nunca conter CNPJ, score, tier, prioridade, dor, reclamacoes, pitch ou confianca interna.
