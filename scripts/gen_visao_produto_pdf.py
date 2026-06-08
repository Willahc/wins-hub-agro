#!/usr/bin/env python3
"""Gera o PDF de VISÃO DE PRODUTO (identidade WiNS verde/cards/DejaVu, sem emojis):
  - WiNS_Visao_App_Campo.pdf : App de Campo + Fazenda Conectada (roadmap + munição de parceria)
Consolida: documento de expansão + análise técnica (schema/ingestão) + funcionalidades de campo
+ catálogo a fundo (benchmark de concorrentes). Roda na imagem da API (WeasyPrint 62.3 + DejaVu)."""
import os
from datetime import datetime
from weasyprint import HTML

HOJE = datetime.now()
os.makedirs("/tmp/out", exist_ok=True)

CSS = """
  @page { size: A4; margin: 0 0 18mm 0;
    @bottom-center { content: "WiNS Hub Agro  ·  " string(doclabel) "  ·  pag. " counter(page) " de " counter(pages);
      font: 8pt 'DejaVu Sans', sans-serif; color: #8a978a; } }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: 'DejaVu Sans', Arial, sans-serif; color: #20291f; font-size: 9.6pt; line-height: 1.48; }
  .doclabel { string-set: doclabel content(); position: absolute; left: -9999px; }
  .wrap { padding: 5mm 16mm 0; }
  .cover { background: #1a3a1a; color: #fff; padding: 20mm 16mm 13mm; }
  .brand { font-size: 22pt; font-weight: 700; letter-spacing: .5px; }
  .brand .a { color: #7fc77f; }
  .doc-title { margin-top: 13px; font-size: 14pt; color: #cfe6cf; text-transform: uppercase; letter-spacing: 2px; }
  .doc-sub { margin-top: 5px; font-size: 9.5pt; color: #9fc59f; }
  h2 { font-size: 12pt; color: #1a3a1a; margin: 17px 0 3px; }
  h3 { font-size: 10pt; color: #2d5a2d; margin: 11px 0 2px; }
  .rule { height: 3px; background: #4a9e4a; border-radius: 2px; width: 42px; margin-bottom: 9px; }
  p { margin: 5px 0; }
  b { color: #14260f; }
  ul { margin: 5px 0; padding-left: 17px; } li { margin: 3px 0; }
  /* destaque / tese */
  .lead { background: #eef5ee; border-left: 4px solid #2d5a2d; border-radius: 6px; padding: 10px 13px; margin-top: 10px; font-size: 9.6pt; }
  .quote { background: #f1f8ef; border-left: 4px solid #2d7d2d; border-radius: 6px; padding: 9px 13px; margin: 9px 0; font-style: italic; color: #14380f; }
  /* cards de numeros */
  .stats { display: flex; gap: 10px; margin-top: 10px; }
  .stat { flex: 1; background: #f5f8f4; border: 1px solid #e6ece6; border-radius: 9px; padding: 9px 11px; text-align: center; }
  .stat .v { font-size: 15pt; font-weight: 700; color: #1a3a1a; }
  .stat .l { font-size: 7.6pt; text-transform: uppercase; letter-spacing: .4px; color: #6b7a6b; margin-top: 2px; }
  /* tabelas */
  table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 8.7pt; }
  th { background: #1a3a1a; color: #fff; text-align: left; padding: 5px 7px; font-size: 8pt; text-transform: uppercase; letter-spacing: .3px; }
  td { padding: 5px 7px; border-bottom: 1px solid #e6ece6; vertical-align: top; }
  tr:nth-child(even) td { background: #fafcf9; }
  /* tags de esforco */
  .tag { display: inline-block; color: #fff; font-size: 7pt; font-weight: 700; padding: 1px 6px; border-radius: 9px; white-space: nowrap; }
  .t-hoje { background: #2d7d2d; } .t-cap { background: #b8860b; } .t-rd { background: #4a6fa5; }
  .legend { font-size: 8pt; color: #6b7a6b; margin: 6px 0 0; }
  /* blocos de camada */
  .layer { border-left: 4px solid #2d5a2d; border-radius: 6px; padding: 8px 13px; margin: 9px 0; background: #fafcf9; }
  .layer.moat { border-left-color: #2d7d2d; background: #f1f8ef; }
  .layer.tech { border-left-color: #4a6fa5; background: #f3f6fb; }
  .layer .lt { font-weight: 700; color: #1a3a1a; font-size: 10pt; }
  .layer .ls { font-size: 8.4pt; color: #6b7a6b; }
  .pill { background:#1a3a1a; color:#fff; font-size:8pt; font-weight:700; padding:1px 8px; border-radius:10px; }
  .meta { font-size: 8.5pt; color: #7a857a; margin-top: 8px; }
  .pagebreak { page-break-before: always; }
"""


def render(path, doc_title, doc_sub, body, footer_label):
    html = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>'
        + CSS + '</style></head><body>'
        f'<span class="doclabel">{footer_label}</span>'
        '<div class="cover"><div class="brand">WiNS Hub <span class="a">Agro</span></div>'
        f'<div class="doc-title">{doc_title}</div><div class="doc-sub">{doc_sub}</div></div>'
        f'<div class="wrap">{body}</div></body></html>'
    )
    HTML(string=html).write_pdf(path)
    print("OK ->", path)


LEG = ('<p class="legend"><span class="tag t-hoje">HOJE</span> roda no PWA com a Starlink dela &nbsp; '
       '<span class="tag t-cap">CAPACITOR</span> precisa de nativo (Bluetooth/câmera/offline) &nbsp; '
       '<span class="tag t-rd">R&amp;D</span> modelo/pesquisa</p>')

body = f"""
  <div class="lead"><b>Tese.</b> A Starlink no campo elimina a barreira de conectividade e transforma o
  celular/tablet de "ferramenta offline de captura" em <b>terminal de tempo real ligado a toda a inteligência
  da plataforma</b>. O salto estratégico: deixar de só consumir dado público e passar a <b>capturar fenótipo
  proprietário de rebanho real</b> (peso, consumo, reprodução, conformação) — a matéria-prima dos próprios
  sumários genéticos, que nenhum concorrente tem.</div>

  <h2>1. O que já está pronto (e muda o enquadramento)</h2><div class="rule"></div>
  <p>A fundação que costuma ser tratada como "a construir" <b>já existe no schema</b> — só está sem dados. O
  esquema <b>fazenda.*</b> está modelado e ligado ao catálogo genético:</p>
  <div class="stats">
    <div class="stat"><div class="v">104.763</div><div class="l">reprodutores no catálogo</div></div>
    <div class="stat"><div class="v">985.307</div><div class="l">avaliações genéticas</div></div>
    <div class="stat"><div class="v">4 tabelas</div><div class="l">fazenda.* prontas (0 linhas)</div></div>
  </div>
  <table>
    <tr><th>Tabela</th><th>O que já modela</th><th>Relevância para o app de campo</th></tr>
    <tr><td><b>fazenda.cliente</b></td><td>produtor, ligado a imóvel rural e CNPJ</td><td>a fazenda como entidade já existe</td></tr>
    <tr><td><b>fazenda.animal</b></td><td>rebanho real, com <b>pai_reprodutor_id &rarr; catálogo</b> e mae_id (grafo genealógico)</td><td>a espinha do RFID já tem onde se ancorar</td></tr>
    <tr><td><b>fazenda.medicao</b></td><td>peso, altura, AOL, EGS, escore por (animal, data)</td><td><b>é a tabela de fenótipo</b> que alimenta genética</td></tr>
    <tr><td><b>fazenda.evento_reprodutivo</b></td><td>IATF: matriz / reprodutor / bezerro / tipo / sucesso</td><td>os eventos reprodutivos já têm casa</td></tr>
  </table>
  <p class="meta">Implicação: o salto "consumir dado público &rarr; capturar fenótipo próprio" não exige re-arquitetura.
  Exige <b>dados entrando</b> e decidir onde mora a telemetria contínua.</p>

  <h2>2. A visita tem dois modos — e o app serve os dois</h2><div class="rule"></div>
  <p>Sutileza que organiza o produto: <b>a Starlink é dela, é móvel — vai embora junto com ela.</b></p>
  <div class="layer moat"><span class="lt">Modo conectado</span> <span class="ls">(enquanto a Mari está lá)</span>
  <p style="margin:4px 0 0">O tablet vira terminal do cérebro inteiro: 104k reprodutores, motor de acasalamento,
  preço real de sêmen, território — tudo em tempo real, na frente do animal.</p></div>
  <div class="layer"><span class="lt">O que sobra depois</span> <span class="ls">(a fazenda volta a ser deserto vet)</span>
  <p style="margin:4px 0 0">O valor da visita não pode evaporar com o link. Resposta barata e brasileira:
  <b>PDF + WhatsApp</b> (lembrete de janela de IATF, plano, alertas funcionam em 2G), e sensores que usam a
  <b>próxima visita da Mari como evento de sincronização</b> ("mula de dados" móvel). Isso derruba a barreira
  de exigir Starlink fixa na fazenda para começar a acumular fenótipo.</p></div>

  <h2 class="pagebreak">3. Catálogo de funcionalidades</h2><div class="rule"></div>
  <p>Os concorrentes de campo (JetBov, Bovitech/Ideagri, Farmin, iRancho) são, no fundo, <b>livros-caixa de
  curral</b>: registram bem o que aconteceu. Nós já temos a camada de <b>decisão</b>. Precisamos
  <b>alcançar</b> a captura (sem ela ninguém confia no app no curral) e <b>explorar</b> a inteligência (que
  ninguém tem).</p>
  {LEG}

  <div class="layer"><span class="lt">Camada A — Captura no curral</span> <span class="ls">(table stakes; piso JetBov: &lt;12s/animal, offline)</span></div>
  <table>
    <tr><th>Funcionalidade</th><th>Nosso schema</th><th>Esforço</th></tr>
    <tr><td><b>Modo Curral rápido</b> — 1 animal por toque, sem digitar</td><td>UI nova</td><td><span class="tag t-cap">CAPACITOR</span></td></tr>
    <tr><td><b>Bastão RFID Bluetooth</b> lê EID &rarr; puxa/cria animal</td><td>falta coluna <b>eid</b> ISO (≠ brinco visual)</td><td><span class="tag t-cap">CAPACITOR</span></td></tr>
    <tr><td><b>Balança Bluetooth</b> &rarr; peso direto em medicao</td><td>medicao existe; hoje peso só vai pra animal</td><td><span class="tag t-cap">CAPACITOR</span></td></tr>
    <tr><td><b>Calendário sanitário</b> (vacina, vermífugo, alertas)</td><td>não existe tabela sanitária</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Estoque de insumos/medicamentos</b> com baixa no manejo</td><td>não existe</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Rastreabilidade SISBOV + GTA / movimentação</b></td><td>sisbov no animal; falta movimentação</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Reprodução / IATF por lote</b> + diagnóstico de gestação</td><td><b>evento_reprodutivo já existe</b></td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Índices zootécnicos</b> — prenhez, desmame, GMD, IEP</td><td>derivável; falta <b>grupo de manejo/lote</b></td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Grupo de contemporâneos / lote</b></td><td><b>não existe — pré-requisito de tudo</b></td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Estimativa de peso por foto/fita</b> (sem balança)</td><td>—</td><td><span class="tag t-rd">R&amp;D</span></td></tr>
  </table>
  <p class="meta">Ponto cego de todos (e nosso): sem <b>lote/grupo de contemporâneos</b>, GMD e taxa de prenhez não
  comparam nada. Barato, e destrava índices E o fosso genético.</p>

  <div class="layer moat"><span class="lt">Camada B — Inteligência de decisão</span> <span class="ls">(nosso fosso; nenhum concorrente tem)</span></div>
  <table>
    <tr><th>Funcionalidade</th><th>Por que é só nosso</th><th>Esforço</th></tr>
    <tr><td><b>Acasalamento dirigido ao vivo</b> com a vaca na frente dela</td><td>concorrente registra a cobertura; nós <b>recomendamos</b> o touro por R$/bezerro</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Consanguinidade em tempo real</b> na cruza proposta</td><td>grafo mae_id/pai_id já existe — veta cruza que sobe endogamia</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Auditoria genética do rebanho</b> vs. mediana da região</td><td>só nós temos o benchmark de 985k avaliações</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>IATF que fecha o ciclo</b>: prenhez por touro JÁ sabendo genética/preço</td><td>Bovitech compara prenhez por touro, mas é cego à genética</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Lista de descarte + candidatas a doadora (FIV)</b></td><td>gancho direto com o laboratório do Monte Sião</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Cotação de sêmen na hora</b> (preço real CRV/ABS) &rarr; PDF/WhatsApp</td><td>fecha venda na visita; concorrente não vende sêmen</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Progênie medida enriquece o touro catalogado</b></td><td>início do dado proprietário, sem esperar "sumário próprio"</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Benchmark anônimo entre fazendas</b> (percentil da região)</td><td>dado que só a Mari coleta — efeito de rede</td><td><span class="tag t-hoje">HOJE</span></td></tr>
    <tr><td><b>Biometria de focinho (muzzle ID)</b> — identidade por foto (~99%)</td><td>backup de RFID onde o brinco cai (realidade do deserto vet)</td><td><span class="tag t-rd">R&amp;D</span></td></tr>
  </table>

  <div class="layer tech"><span class="lt">Camada C — Pasto e ambiente</span></div>
  <ul>
    <li><b>Mapa de piquetes + lotação atual/máxima</b> com alerta de troca de área (pastejo rotacionado); conecta ao <b>pasto ocioso do MapBiomas que já usamos</b>. <span class="tag t-hoje">HOJE</span>/<span class="tag t-cap">CAPACITOR</span></li>
    <li><b>NDVI por talhão</b> (satélite/drone) &rarr; massa de forragem &rarr; entrada/saída do gado. <span class="tag t-rd">R&amp;D</span></li>
    <li><b>Estação meteo / estresse térmico × fertilidade</b> — baixa frequência, fácil de ingerir. <span class="tag t-hoje">HOJE</span></li>
  </ul>

  <div class="layer"><span class="lt">Camada D — O que faz a atividade ser rápida e à prova de campo</span></div>
  <ul>
    <li><b>Offline-first de verdade</b> — captura nunca trava em conexão (Starlink tem rain-fade; curral é poeira e pressa). Outbox local + sync idempotente por UUID. <span class="tag t-cap">CAPACITOR</span></li>
    <li><b>Notas de voz no curral</b> (mãos no animal) &rarr; campo estruturado, transcrição em tempo real. <span class="tag t-cap">CAPACITOR</span></li>
    <li><b>OCR de brinco</b> pela câmera; <b>foto anexada à ficha</b> (histórico visual). <span class="tag t-cap">CAPACITOR</span></li>
    <li><b>A próxima visita já vem pronta</b> — app marca quem precisa de atenção (perdeu peso, cio atrasado, protocolo vencido). <span class="tag t-hoje">HOJE</span></li>
  </ul>

  <h2 class="pagebreak">4. Arquitetura técnica</h2><div class="rule"></div>
  <p>Telemetria contínua é uma fera diferente da medição curada. <b>Duas camadas</b> que respeitam o schema atual:</p>
  <div class="quote">fazenda.leitura_sensor (RAW, append-only, timestamptz, particionada) &nbsp;—rollup diário&rarr;&nbsp; fazenda.medicao (CURADA, grão de dia, alimenta genética/acasalamento)</div>
  <ul>
    <li><b>medicao</b> permanece a verdade canônica que o app já sabe ler — sumário genético usa o peso ajustado do dia (P120/P210/P450), não 40 mil pings de balança.</li>
    <li><b>leitura_sensor</b> é nova e isolada: o firehose bruto (balança de passagem, acelerômetro, bolus, cocho).</li>
  </ul>
  <h3>PostgreSQL aguenta ou precisa de TimescaleDB?</h3>
  <p>Verificado no banco em produção: <b>TimescaleDB NÃO está instalado nem disponível</b> (imagem postgres:16-alpine;
  extensões: plpgsql, pg_trgm, unaccent, uuid-ossp). <b>Recomendação: não trocar ainda.</b> Para 1 fazenda elite e
  mesmo dezenas, o Postgres 16 nativo resolve com <b>partição por mês + índice BRIN</b>. A decisão Timescale é
  guiada pelo <b>sensor de cio (alta frequência)</b>, não pela balança — adote quando o acelerômetro entrar em
  volume, não antes.</p>
  <h3>Ingestão</h3>
  <ul>
    <li><b>Sensores fixos</b>: gateway na fazenda &rarr; MQTT (1 container) &rarr; consumidor &rarr; insert em lote.</li>
    <li><b>App de campo</b>: vai pela API (o Postgres é 127.0.0.1-only — sensor não fala com o banco direto, e é correto). Idempotência por UUID (Starlink cai &rarr; retry não duplica).</li>
    <li><b>Começar batch</b> (device acumula e envia pacotes). Offline-first + outbox é obrigatório, não luxo.</li>
  </ul>
  <h3>Segurança</h3>
  <p>A captura de campo é o <b>primeiro WRITE de fora da sessão da Mari</b> — nova superfície. O tablet precisa de
  <b>token de dispositivo escopado ao cliente_id</b> (não a senha-mestra), rate-limit e validação de payload.
  Sem isso, tablet perdido = vazamento do rebanho de todos os clientes.</p>
  <p class="meta">O <b>load_rebanho_cliente.py</b> é o embrião do <b>bulk import</b> de cadastro (com seu DRY-RUN e o
  truque de espelhar a fêmea no catálogo), não do pipeline de campo — que precisa de endpoints de escrita
  (hoje inexistentes para fazenda.*), idempotência e outbox no device.</p>

  <h2>5. O fosso genético — o ciclo que fecha</h2><div class="rule"></div>
  <p>O elo de ouro <b>já está soldado</b>: fazenda.animal.pai_reprodutor_id aponta para o catálogo. Logo, todo
  bezerro nascido na fazenda com peso medido <b>liga fenótipo real de progênie a um touro catalogado</b> —
  enriquecendo a avaliação daquele touro na base de 985 mil avaliações.</p>
  <div class="quote">O ganho dos próximos 12-18 meses não é "sumário WiNS próprio" (precisa de volume + grupo de
  contemporâneos + geneticista). É "fenótipo proprietário que torna o acasalamento dirigido melhor que o do
  concorrente" — e isso já roda hoje: telemetria &rarr; medicao &rarr; recalcula o mérito próprio da vaca &rarr;
  muda o ranking do acasalamento que o Monte Sião vê.</div>

  <h2>6. Escada de implementação — prioridades</h2><div class="rule"></div>
  <table>
    <tr><th>#</th><th>Passo</th><th>Por que primeiro</th></tr>
    <tr><td>1</td><td><b>grupo_manejo/lote + gravar peso em medicao</b></td><td>destrava índices zootécnicos E genética; barato, fundacional</td></tr>
    <tr><td>2</td><td><b>Modo Curral + bastão RFID + balança Bluetooth</b></td><td>sem isso não somos críveis no curral (piso JetBov)</td></tr>
    <tr><td>3</td><td><b>Calendário sanitário + GTA/SISBOV</b></td><td>table stakes que todo produtor cobra</td></tr>
    <tr><td>4</td><td><b>Acasalamento ao vivo + consanguinidade + cotação</b></td><td>já roda hoje; é o que nenhum concorrente faz e justifica a visita</td></tr>
  </table>
  <div class="lead"><b>Síntese.</b> Os concorrentes ensinam o <b>piso de captura</b> que precisamos igualar pra entrar
  no curral; o nosso catálogo genético e de mercado é o <b>teto de inteligência</b> que eles nunca vão alcançar.
  A oportunidade é ser o único app que faz as duas coisas no mesmo tablet, na frente do animal.</div>

  <p class="meta">Documento de visão de produto gerado pela plataforma WiNS Hub Agro · {HOJE.strftime('%d/%m/%Y')} ·
  Benchmark de concorrentes: JetBov, Ideagri/Bovitech, Farmin, iRancho, Herdwatch, iLivestock. Fontes regulatórias:
  SISBOV/GTA (MAPA). Tecnologias: biometria de focinho (pesquisa ~99%), NDVI de pasto, IATF por lote.</p>
"""

render("/tmp/out/WiNS_Visao_App_Campo.pdf",
       "App de Campo + Fazenda Conectada",
       f"Visão de produto · Roadmap e munição de parceria · {HOJE.strftime('%d/%m/%Y')}",
       body, "Visão de Produto — App de Campo")
