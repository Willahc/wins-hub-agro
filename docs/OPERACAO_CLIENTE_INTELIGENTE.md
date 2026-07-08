# Operacao Cliente Inteligente

Este guia descreve como operar e verificar o Cliente Inteligente sem expor dados internos nem interromper processos em andamento.

## Regras operacionais

- Nao parar o processo V5 MAX enquanto estiver rodando.
- Nao alterar Nginx sem backup e confirmacao.
- Nao publicar One Pages sem validar que nao ha dados internos.
- Nao copiar credenciais, material de autenticacao ou chaves para documentacao.
- Antes de alteracoes funcionais, fazer backup timestampado das pastas afetadas.

## URLs atuais

| URL | Finalidade |
|---|---|
| `https://ci.winshubagro.cloud` | App do comerciante |
| `https://ci.winshubagro.cloud/loja/cliente-inteligente/` | One Pages publicas atuais |
| `https://ci.winshubagro.cloud/prospec/` | Prospecção interna restrita |

## Pastas de producao

| Pasta | Finalidade |
|---|---|
| `/root/wins_agro_v1/ci` | App comerciante |
| `/root/wins_agro_v1/ci-api` | Backend Cliente Inteligente |
| `/root/wins_agro_v1/ci-data` | Dados do `ci-api` |
| `/root/wins_agro_v1/ci-lojas/cliente-inteligente` | One Pages publicas atuais |
| `/root/wins_agro_v1/prospeccao-campanella` | Prospecção interna |
| `/root/wins_agro_v1/nginx` | Configuracao Nginx |

## Pastas de staging/teste

| Pasta | Finalidade |
|---|---|
| `/root/wins_agro_v1/ci-lojas/cliente-inteligente-v2` | Copia/teste das One Pages |
| `/root/wins_agro_v1/backups_codex_20260707_1155` | Backup da ultima rodada de correcao |
| `/root/wins_agro_v1/prospeccao-campanella/backups` | Backups historicos de bancos da prospeccao |
| `/root/wins_agro_v1/backups_tema_20260703_120216` | Backup historico de tema |

## Verificar containers

Leitura segura:

```bash
cd /root/wins_agro_v1
docker ps
docker compose ps
```

Nao reiniciar containers sem janela de manutencao e backup.

## Verificar V5 MAX

Comando seguro:

```bash
ps aux | grep enriquecer_v5_max | grep -v grep
```

Saidas esperadas:

```text
/root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.csv
/root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.json
/root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/relatorio_v5max.html
```

Checagens nao destrutivas:

```bash
stat /root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.csv
stat /root/wins_agro_v1/enriquecimento_v5max_cnpj/cliente_inteligente_enriquecimento_v5_max_cnpj/out_v5max/prospectos_v5max_externos.json
```

## Validar One Pages publicas

Sempre rodar antes de publicar:

```bash
cd /root/wins_agro_v1
python3 scripts/validar_cliente_inteligente_publico.py
```

O validador verifica:

- `ci-lojas/cliente-inteligente/data/negocios.json`
- dataset embutido no indice publico
- paginas individuais em `ci-lojas/cliente-inteligente/negocios/*/index.html`

Ele deve falhar se encontrar CNPJ, score, tier, prioridade, dor, reclamacao, pitch ou fallback interno.

## Auditar fluxo entre as tres camadas

Rodar somente em modo leitura:

```bash
cd /root/wins_agro_v1
python3 scripts/auditar_fluxo_dados_cliente_inteligente.py
```

O script compara One Pages, Prospecção, dashboard, CSV, SQLite e `ci-api` sem alterar arquivos. O resultado atual documentado e:

- veredito: parcialmente integrado;
- One Pages e Prospecção compartilham 813 estabelecimentos;
- correspondencia 813/813 por `place_id` extraido de `maps_url`;
- sem integracao operacional entre One Page, App e Prospecção.

## Operacao esperada apos Base Mestre

1. Gerar a Base Mestre a partir das fontes atuais e V5.
2. Emitir `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
3. Validar `master_public.json` antes de qualquer publicacao.
4. Atualizar Prospecção para consumir `master_prospeccao.json`.
5. Atualizar One Pages para usar apenas `master_public.json`.
6. Atualizar App para receber `place_id`/`slug` e consumir `master_app_seed.json`.
7. Persistir status e anotacoes no backend, nao apenas no navegador.

## Ultima correcao operacional registrada

Backup:

```text
/root/wins_agro_v1/backups_codex_20260707_1155
```

Resumo:

- dados internos removidos das One Pages publicas;
- dashboard de prospeccao regenerado pelo gerador oficial;
- fallback emergencial removido do HTML gerado;
- validador publico criado.

## Pendencias operacionais

1. Base Mestre.
2. Arquivos derivados `master_public.json`, `master_app_seed.json` e `master_prospeccao.json`.
3. Persistencia central de status/anotacoes da prospeccao.
4. Rebuild das One Pages por whitelist publica.
5. Design system aplicado sem quebrar telas existentes.
