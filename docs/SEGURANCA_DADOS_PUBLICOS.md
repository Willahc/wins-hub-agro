# Seguranca de Dados Publicos - Cliente Inteligente

Este documento define a fronteira entre dados publicos e dados internos no Cliente Inteligente.

## Principio

Toda pagina publica deve partir de whitelist, nao de blacklist.

Se um campo nao estiver explicitamente liberado para publicacao, ele deve ficar fora das One Pages.

## Dados permitidos em One Pages

Campos publicaveis quando confiaveis:

- `nome_comercial`
- `categoria`
- `segmento`
- `familia_segmento`, se for uma classificacao publica neutra
- `endereco`
- `latitude`
- `longitude`
- `telefone`
- `whatsapp_confirmado`
- `site_oficial`
- `instagram`
- `facebook`
- `cardapio_url`
- `delivery_url`
- `maps_url`
- `horario`
- `nota`
- `num_avaliacoes`
- `descricao_publica`

## Campos proibidos em One Pages publicas

Nunca publicar:

- `cnpj`
- `cnpj_status`
- `cnpj_conf`
- `cnpj_confidence`
- `razao_social` sem revisao
- socios
- `score`
- `score_digital`
- `score_dor`
- `score_comercial`
- `lead_tier`
- `tier`
- `prioridade`
- `dor`
- `dor_dominante`
- reclamacoes
- exemplos de dor
- `gancho`
- `pitch`
- `pitch_presencial`
- `pitch_v3`
- `mensagem_whatsapp` interna
- `acao_recomendada`
- `risco`
- `legal_risk_flag`
- `nivel_confianca_interno`
- dados com status `CANDIDATO`, `FRACO`, `NAO_ENCONTRADO` ou equivalente

## Dados internos permitidos somente na prospeccao

A prospeccao interna pode usar:

- CNPJ candidato/provavel/confirmado;
- confianca por campo;
- score comercial;
- lead tier;
- dor dominante;
- reclamacoes;
- pitch;
- mensagem de abordagem;
- rota;
- status de visita;
- anotacoes de campo.

Mesmo na prospeccao, dados incertos devem aparecer com nivel de confianca.

## App comerciante

O app do comerciante pode usar dados de segmento para pre-configuracao, mas nao deve expor a origem interna como se fosse fato confirmado.

Permitido:

- segmento;
- categoria;
- familia de segmento;
- modulos recomendados;
- produtos/modelos sugeridos;
- configuracoes iniciais.

Evitar:

- mostrar dor/reclamacao sem contexto;
- mostrar score comercial;
- preencher CNPJ candidato como oficial.

## Validador publico

Rodar:

```bash
cd /root/wins_agro_v1
python3 scripts/validar_cliente_inteligente_publico.py
```

O validador verifica:

- JSON publico;
- dataset embutido no indice;
- HTML das paginas individuais.

Ele deve ser executado:

- antes de publicar One Pages;
- depois de regenerar paginas;
- depois de integrar qualquer saida da Base Mestre;
- antes de alterar rotas publicas.

## Ultima correcao registrada

Na ultima rodada de correcao, foram removidos dos artefatos publicos:

- `tier`;
- `prioridade`;
- `score`;
- caixas "Score interno".

Backup antes da correcao:

```text
/root/wins_agro_v1/backups_codex_20260707_1155
```

## Regras para a Base Mestre

A Base Mestre deve gerar tres visoes separadas:

1. `master_public.json`
   - somente campos publicos;
   - sem CNPJ, dor, score, pitch ou tier;
   - validado antes de publicar.

2. `master_app_seed.json`
   - configuracao inicial por segmento;
   - sem dor/reclamacao como fato publico;
   - dados confirmaveis pelo comerciante.

3. `master_prospeccao.json`
   - visao interna completa;
   - inclui confianca, score, CNPJ, pitch, dor, status e rota.

## Regras por view

`master_public.json`:

- deve ser gerado por whitelist;
- nao pode conter CNPJ, score, tier, prioridade, dor, reclamacoes, pitch ou confianca interna;
- deve conter somente dados publicos confiaveis e neutros;
- deve ser validado por `scripts/validar_cliente_inteligente_publico.py` antes de publicar.

`master_app_seed.json`:

- pode conter segmento, familia de segmento, modulos recomendados e configuracao inicial;
- nao deve expor dor/reclamacao como texto bruto para o comerciante;
- nao deve preencher CNPJ candidato como dado oficial;
- deve tratar recomendacoes como seed confirmavel no onboarding.

`master_prospeccao.json`:

- pode conter dados internos;
- deve manter nivel de confianca por campo sensivel;
- deve separar CNPJ confirmado, provavel, candidato, fraco e nao encontrado;
- deve ser restrito a ferramenta interna protegida.

## Separacao validada na auditoria

A auditoria de fluxo registrou que a camada publica foi validada com:

```bash
python3 /root/wins_agro_v1/scripts/validar_cliente_inteligente_publico.py
```

Resultado atual esperado:

- JSON publico validado com 813 registros;
- dataset embutido validado com 813 registros;
- 813 paginas publicas validadas;
- sem exposicao de campos internos proibidos na camada publica auditada.

## Checklist antes de publicar

- [ ] O V5 terminou ou a base usada esta congelada.
- [ ] A Base Mestre foi gerada.
- [ ] `master_public.json` foi derivado por whitelist.
- [ ] O validador publico passou.
- [ ] Amostras de paginas foram revisadas manualmente.
- [ ] Nenhum material sensivel, CNPJ candidato, score ou dor apareceu na camada publica.
