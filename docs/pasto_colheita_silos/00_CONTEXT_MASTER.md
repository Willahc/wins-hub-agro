# Contexto mestre

## Estado analisado

- **CONFIRMADO NO CÓDIGO** — branch `master`, commit `84fcf70e15567ddc6c812d638c816204e5ae9035`.
- **CONFIRMADO NO CÓDIGO** — o working tree estava limpo no início da análise.
- **CONFIRMADO NO CÓDIGO** — aplicação Agro em FastAPI/Jinja/Alpine.js, PostgreSQL, Nginx e Docker Compose; o Cliente Inteligente é serviço e aplicação separados no mesmo repositório (`docker-compose.yml`, linhas aproximadas 14–105).
- **CONFIRMADO NO CÓDIGO** — a API Agro é predominantemente um monólito em `app/main.py`; apenas o simulador foi extraído para `app/routers/simulador.py` (`app/main.py`, linhas 1–5.323).
- **CONFIRMADO NO CÓDIGO** — a autenticação atual representa uma única identidade configurada por ambiente, JWT em cookie, senha bcrypt, MFA opcional e passkey (`app/auth.py`, linhas 8–75; `app/main.py`, linhas 81–109 e 221–501).

## Diagnóstico central

O projeto já oferece ativos valiosos para o plano: shell visual comum, mapa Leaflet, dados municipais de rebanho/lavoura/pasto, geometrias CAR processadas, PDF, rebanho e lotes do Campo, fila offline e algumas operações idempotentes. Esses ativos reduzem esforço de integração, mas não formam ainda um sistema operacional de pasto, estoque ou armazenagem.

O bloqueio arquitetural é o isolamento: hoje a autenticação protege `/api/*` de visitantes, porém os endpoints do Campo recebem `cliente_id`, `animal_id`, `estacao_id` e outros IDs sem um escopo de organização derivado da sessão. O próprio código descreve o app como single-tenant (`app/main.py`, linhas 27–30). Criar novos módulos nesse padrão perpetuaria risco de IDOR assim que houver mais usuários.

**DECISÃO RECOMENDADA** — executar a Fase 0 antes do MVP: organização/membership, vínculo usuário–fazenda, autorização central, auditoria transacional, parâmetros e unidades. Não é reescrita; é uma camada incremental ao monólito.

## Visão futura

O ecossistema deve responder a cinco perguntas, sempre explicando fonte, data, unidade e confiança:

1. Quanto alimento existe e por quantos dias atende o rebanho?
2. Onde o pasto mostra sinal de queda ou recuperação e o que deve ser verificado em campo?
3. Quando colher, quantas horas/viagens serão necessárias e onde está o gargalo?
4. Quanto existe em cada silo, quais perdas são prováveis e quando o estoque termina?
5. Qual é a pressão regional de armazenagem e qual alternativa logística é plausível?

Satélite, clima e benchmark municipal são evidência auxiliar. A interface nunca os apresentará como diagnóstico, produção comprovada ou disponibilidade real de armazém.

## Prioridade e sequência

1. **Fase 0 — fundações (L):** identidade organizacional, autorização, auditoria, unidade/fonte/parâmetro e modularização mínima.
2. **Fase 1 — autonomia alimentar + estoque de silagem (L):** manual, útil sem satélite/sensor, integrado a animais/lotes.
3. **Fase 2 — clima (M):** histórico e alertas, com medição diferenciada de estimativa.
4. **Fase 3 — piquetes e Pasto Vivo (XL):** polígonos, observação de campo e séries de satélite.
5. **Fase 4 — colheita e silo de silagem (L):** janela, máquinas, transporte, capacidade e consumo.
6. **Fase 5 — silos de grãos (XL):** lote, movimentação, inspeção, custo e rastreabilidade.
7. **Fase 6 — armazenagem regional (L):** armazéns cadastrados, produção municipal e déficit teórico.
8. **Fase 7 — WiNS Hub Log (XL):** contrato de API, rotas, viagens e oportunidades, sem banco compartilhado.

Tamanhos são relativos e não representam prazo.

## MVP prioritário

**PROPOSTA** — “Autonomia Alimentar + Estoque de Silagem”, inicialmente manual:

- importa contagem/peso/categoria dos animais e lotes existentes, permitindo correção explícita;
- registra oferta de pasto, silagem, feno e suplemento por fazenda;
- calcula demanda de matéria seca (MS), oferta útil, déficit/superávit, autonomia e data de ruptura;
- mantém parâmetros por organização/fazenda, versão da fórmula, fonte técnica e intervalo de confiança;
- compara cenário-base com alterações sem alterar o estoque operacional;
- gera alertas explicáveis e PDF com snapshot imutável dos insumos;
- permite capturas de estoque/retirada no App de Campo usando UUID e sincronização segura.

Satélite, previsão e sensor ficam fora do primeiro corte. Isso permite validar valor, unidades e fluxo de decisão antes de adicionar incerteza externa.

## Princípios e decisões

- Tenant e fazenda são derivados/validados no servidor; nenhum ID enviado pelo navegador concede acesso.
- Quantidade usa `numeric`, unidade explícita e conversão controlada; dinheiro usa moeda e precisão definida.
- Estoque é razão de movimentações imutáveis; ajustes são novas movimentações, não edição silenciosa de saldo.
- Fórmula e parâmetro têm versão; resultado guarda snapshot de entradas, unidade, fonte e versão.
- Dado carrega classe: informado, observado, importado oficial, previsto, estimado ou derivado.
- Alertas são reprodutíveis e explicáveis; recomendações usam “avaliar”, “considerar” e “validar em campo”.
- Clima/satélite são processados por polígono ativo, incrementalmente, fora da requisição web.
- PostGIS só entra após prova com polígonos/piquetes; GeoJSON + cálculo na aplicação pode atender o piloto.
- Cliente Inteligente e WiNS Hub Log permanecem serviços independentes. Integração é por contrato versionado.

## Fontes e posicionamento

- **A, automação direta:** IBGE SIDRA; NASA POWER (fallback climático de grade, não estação).
- **B, conta/token:** Copernicus Data Space/openEO; ANA HidroWebservice.
- **C/D, lote/manual ou automação incerta:** INMET, ZARC, Conab/SICARM, MapBiomas, Embrapa GeoInfo.
- **A/C com cautela operacional:** INPE Queimadas; SoilGrids por WCS/WebDAV; OSM para dados, não para tiles em massa/offline.

Licenças, limites e termos devem ser registrados por dataset/versão antes de uso comercial. Ver [fontes](03_FONTES_DADOS_GRATUITAS.md).

## Riscos críticos

1. Single-tenant e falta de autorização por objeto.
2. Confundir cadastro/capacidade estática com ocupação/disponibilidade em tempo real.
3. Misturar massa verde, matéria seca e diferentes bases de umidade.
4. Transformar NDVI/MapBiomas em diagnóstico agronômico definitivo.
5. Processar rasters nacionais na VPS e comprometer API/DB.
6. Fila offline atual em `localStorage`, não cifrada nem particionada por usuário/fazenda.
7. Monólito, acesso SQL direto e auditoria best-effort dificultam domínio e rastreabilidade.
8. Qualidade/licença/estabilidade heterogêneas nas fontes.

## Pontos pendentes

- Definir organização, papéis e migração dos clientes/fazendas atuais.
- Validar com zootecnista/agronômo parâmetros, faixas e cenários do MVP.
- Validar jurídicamente licenças/redistribuição de MapBiomas, Conab, INMET, Embrapa e ZARC.
- Medir CPU, memória, disco, latência e crescimento da VPS antes dos jobs.
- Decidir PostGIS após spike com geometrias reais simplificadas.
- Especificar contrato do WiNS Hub Log e titularidade dos dados.

Antes de implementar, ler `01`, `04`, `05`, `06`, `09`, `14`, `16` e o checkpoint `18`.
