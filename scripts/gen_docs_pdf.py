#!/usr/bin/env python3
"""Gera dois PDFs com a identidade visual WiNS (verde/cards/DejaVu):
  - WiNS_NDA_minuta.pdf  : minuta de NDA mútuo (p/ revisão do advogado)
  - WiNS_Roteiro_TI.pdf  : roteiro interno da reunião com o time de TI
Sem emojis (DejaVu não os tem) — usa badges coloridos. Roda na imagem da API
(WeasyPrint 62.3 + pydyf 0.10 + fonts-dejavu)."""
import os
from datetime import datetime, timedelta
from weasyprint import HTML

HOJE = datetime.now()
AMANHA = HOJE + timedelta(days=1)
os.makedirs("/tmp/out", exist_ok=True)

CSS = """
  @page { size: A4; margin: 0 0 20mm 0;
    @bottom-center { content: "WiNS Hub Agro  ·  " string(doclabel) "  ·  pág. " counter(page) " de " counter(pages);
      font: 8pt 'DejaVu Sans', sans-serif; color: #8a978a; } }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: 'DejaVu Sans', Arial, sans-serif; color: #20291f; font-size: 10pt; line-height: 1.5; }
  .doclabel { string-set: doclabel content(); position: absolute; left: -9999px; }
  .wrap { padding: 4mm 18mm 0; }
  .cover { background: #1a3a1a; color: #fff; padding: 18mm 18mm 11mm; }
  .brand { font-size: 21pt; font-weight: 700; letter-spacing: .5px; }
  .brand .a { color: #7fc77f; }
  .doc-title { margin-top: 12px; font-size: 13pt; color: #cfe6cf; text-transform: uppercase; letter-spacing: 2px; }
  .doc-sub { margin-top: 4px; font-size: 9.5pt; color: #9fc59f; }
  h2 { font-size: 11.5pt; color: #1a3a1a; margin: 16px 0 3px; }
  .rule { height: 3px; background: #4a9e4a; border-radius: 2px; width: 42px; margin-bottom: 9px; }
  p { margin: 5px 0; }
  b { color: #14260f; }
  /* avisos */
  .banner { border-radius: 9px; padding: 9px 13px; font-size: 9pt; margin-top: 10px; }
  .bn-draft { background: #fdf6e8; border: 1px solid #c79a2a; color: #7a5a12; }
  .bn-internal { background: #fbeaea; border: 1px solid #bb3344; color: #8a2222; }
  /* NDA */
  .parties { display: flex; gap: 12px; margin-top: 10px; }
  .party { flex: 1; background: #f5f8f4; border: 1px solid #e6ece6; border-radius: 9px; padding: 9px 11px; font-size: 9pt; }
  .party .pl { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .5px; color: #6b7a6b; }
  .party .pv { font-weight: 700; color: #1a3a1a; margin-top: 1px; }
  .clause { margin: 7px 0; }
  .clause .n { font-weight: 700; color: #1a3a1a; }
  .sign { margin-top: 16px; display: flex; gap: 30px; }
  .sign > div { flex: 1; border-top: 1px solid #333; padding-top: 4px; font-size: 8.5pt; color: #555; text-align: center; }
  .meta { font-size: 8.5pt; color: #7a857a; margin-top: 6px; }
  /* Roteiro */
  .goal { background: #eef5ee; border-left: 4px solid #2d5a2d; border-radius: 6px; padding: 9px 12px; margin-top: 10px; font-size: 9.5pt; }
  .block { border-left: 4px solid #ccc; border-radius: 6px; padding: 7px 12px; margin: 9px 0; background: #fafcf9; }
  .block.show { border-left-color: #2d7d2d; background: #f1f8ef; }
  .block.protect { border-left-color: #c0392b; background: #fdf2f1; }
  .block.alert { border-left-color: #c79a2a; background: #fdf8ec; }
  .badge { display: inline-block; color: #fff; font-size: 8pt; font-weight: 700; padding: 2px 9px;
    border-radius: 11px; text-transform: uppercase; letter-spacing: .4px; }
  .b-show { background: #2d7d2d; } .b-protect { background: #c0392b; } .b-alert { background: #b8860b; }
  ul { margin: 5px 0; padding-left: 17px; } li { margin: 3px 0; }
  .qa { margin: 5px 0; font-size: 9.5pt; } .qa .q { color: #555; } .qa .a { color: #14260f; font-weight: 600; }
  .pill { background:#1a3a1a; color:#fff; font-size:8pt; font-weight:700; padding:1px 7px; border-radius:10px; }
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


# ===================== NDA =====================
nda = f"""
  <div class="banner bn-draft"><b>MINUTA — para revisão do seu advogado.</b> Não é peça jurídica final
  nem aconselhamento. Campos entre [colchetes] a preencher. Eles têm advogados próprios — ajuste antes de assinar.</div>

  <h2>Partes</h2><div class="rule"></div>
  <div class="parties">
    <div class="party"><div class="pl">Parte A — "WiNS"</div>
      <div class="pv">[William — nome / razão social PJ]</div>
      [CPF/CNPJ] · [endereço]</div>
    <div class="party"><div class="pl">Parte B — "Monte Sião"</div>
      <div class="pv">[razão social da entidade do Grupo]</div>
      [CNPJ] · [endereço]</div>
  </div>
  <p class="meta">Em conjunto, "Partes"; cada uma podendo ser Reveladora e/ou Receptora (acordo mútuo).</p>

  <h2>Considerandos</h2><div class="rule"></div>
  <p>As Partes desejam avaliar uma potencial parceria e/ou <b>licenciamento</b> da plataforma de inteligência
  genética <b>WiNS Hub Agro</b> (a "Finalidade"), para o que trocarão informações sigilosas, inclusive
  demonstrações e <b>gravações já realizadas</b>.</p>

  <h2>Cláusulas</h2><div class="rule"></div>
  <div class="clause"><span class="n">1. Finalidade.</span> As informações destinam-se exclusivamente à avaliação da Finalidade. Qualquer outro uso exige acordo escrito específico.</div>
  <div class="clause"><span class="n">2. Informações Confidenciais.</span> Toda informação, em qualquer forma (oral, escrita, visual, digital, demonstrações, telas e gravações de tela/áudio/vídeo), divulgada entre as Partes, incluindo sem limitar: software, código-fonte, arquitetura, algoritmos, modelos e fontes de dados, metodologias e telas da plataforma WiNS Hub Agro; planos de negócio, preços, clientes e leads; e <b>as gravações já feitas (inclusive a gravação de tela da demonstração anterior)</b>.</div>
  <div class="clause"><span class="n">3. Obrigações da Receptora.</span> (a) manter sigilo; (b) usar a informação só para a Finalidade; (c) não reproduzir nem dar acesso a terceiros, salvo a colaboradores com necessidade real e vinculados a sigilo; (d) <b>não realizar engenharia reversa</b> ou tentar recriar a plataforma; (e) <b>não usar a informação para desenvolver, encomendar ou viabilizar produto/serviço concorrente</b>.</div>
  <div class="clause"><span class="n">4. Propriedade Intelectual.</span> Este Acordo <b>NÃO transfere</b> qualquer direito, licença ou titularidade sobre a plataforma WiNS Hub Agro, que permanece <b>de titularidade exclusiva da WiNS</b> (Lei nº 9.609/1998 e Lei nº 9.279/1996). A avaliação ou eventual acesso <b>não geram cessão de IP</b>, presumida ou tácita. Desenvolvimento futuro será objeto de contrato próprio, com cláusula expressa de titularidade.</div>
  <div class="clause"><span class="n">5. Gravações.</span> As gravações de demonstrações e reuniões são Informação Confidencial; não serão compartilhadas fora das pessoas autorizadas nem usadas para fim diverso. A pedido da Reveladora, serão entregues cópias e/ou comprovada a destruição.</div>
  <div class="clause"><span class="n">6. Exceções.</span> Não é confidencial a informação: (a) já pública sem violação deste Acordo; (b) já detida licitamente pela Receptora; (c) desenvolvida de forma <b>independente</b>, sem uso da informação; (d) exigida por lei/ordem judicial (com aviso prévio, quando possível).</div>
  <div class="clause"><span class="n">7. Prazo.</span> Vigora desde a <b>primeira troca de informações (inclusive a demo já realizada)</b> e sobrevive por <b>[5] anos</b> após o fim das tratativas; código-fonte e segredos de negócio permanecem protegidos enquanto mantiverem tal natureza.</div>
  <div class="clause"><span class="n">8. Devolução/Destruição.</span> Encerradas as tratativas, a Receptora devolve ou destrói a informação (inclusive gravações) em até <b>[10] dias</b>, mediante solicitação.</div>
  <div class="clause"><span class="n">9. Sem obrigação de contratar.</span> Este Acordo não obriga nenhuma das Partes a fechar qualquer negócio.</div>
  <div class="clause"><span class="n">10. Penalidades.</span> O descumprimento sujeita o infrator a perdas e danos, tutela específica e <b>[multa de R$ ____]</b>, nos termos da lei.</div>
  <div class="clause"><span class="n">11. Lei e Foro.</span> Lei brasileira; Foro da Comarca de <b>[____]</b>.</div>

  <div class="sign">
    <div>WiNS — [nome / assinatura]</div>
    <div>Monte Sião — [nome / assinatura]</div>
  </div>
  <p class="meta">[Local], {HOJE.strftime('%d/%m/%Y')} · Minuta gerada pela plataforma WiNS Hub Agro para fins de negociação.</p>
"""

# ===================== ROTEIRO =====================
roteiro = f"""
  <div class="banner bn-internal"><b>USO INTERNO — NÃO COMPARTILHAR.</b> Documento de preparação do William.
  Não entregar ao Grupo Monte Sião.</div>

  <div class="goal"><b>Seu objetivo:</b> que a TI conclua "é mais rápido e barato licenciar do que construir".<br>
  <b>Objetivo provável deles:</b> entender o que é + avaliar integração — e, no limite, "dá pra fazer internamente?".
  Você não controla a intenção; controla <b>o que revela</b>.</div>

  <h2>Abertura (2 min)</h2><div class="rule"></div>
  <ul>
    <li><b>Antes do técnico, ponha o NDA mútuo na mesa:</b> "proponho assinarmos este NDA antes de entrar no detalhe — protege os dois lados". (Se travarem, é um sinal.)</li>
    <li><b>Avise que vai gravar:</b> "vou gravar pro registro e pra alinhar com meu time". (No Brasil, gravar a própria reunião é lícito.)</li>
  </ul>

  <h2><span class="badge b-show">Mostre</span> &nbsp;valor e capacidade (o "o quê")</h2><div class="rule"></div>
  <div class="block show"><ul>
    <li><b>Deserto Vet / Território:</b> o mapa, os municípios sem assistência, os leads qualificados — onde estão os clientes (foi o que mais empolgou o RH: abra por aqui).</li>
    <li><b>Matching + ROI:</b> touro recomendado + justificativa de preço (dose → +R$/cria → ROI).</li>
    <li><b>Canal-aware:</b> "qual produto vender — dose / embrião / cota / animal vivo" (o wow — conecta com o haras de Quarto de Milha deles).</li>
    <li><b>Parecer PDF:</b> o documento de fechamento, pronto.</li>
    <li><b>Visão multi-espécie:</b> "roda no gado e se estende ao haras de vocês" — a plataforma enxerga o negócio inteiro.</li>
  </ul></div>

  <h2><span class="badge b-protect">Proteja</span> &nbsp;não revele (o "como")</h2><div class="rule"></div>
  <div class="block protect"><ul>
    <li>De onde vem o dado e como é ingerido/reconciliado.</li>
    <li>O schema / estrutura do banco.</li>
    <li>As fórmulas de score / os algoritmos.</li>
    <li>Stack, infraestrutura, hospedagem.</li>
    <li>Como o catálogo é montado; credenciais; qualquer "como fizemos".</li>
  </ul></div>

  <h2>Como responder quando o TI sondar o "como"</h2><div class="rule"></div>
  <div class="block">
    <div class="qa"><span class="q">"Qual o stack / onde roda?"</span> → <span class="a">"É nosso motor proprietário, coberto pelo NDA. Posso falar dos pontos de integração, não dos internos."</span></div>
    <div class="qa"><span class="q">"De onde vem o dado?"</span> → <span class="a">"Fontes oficiais + o dado de vocês. A curadoria e a normalização são o nosso núcleo de IP."</span></div>
    <div class="qa"><span class="q">"Como o matching calcula?"</span> → <span class="a">"O resultado é este [mostra]. A metodologia é o ativo licenciado."</span></div>
    <div class="qa" style="margin-top:6px"><b>Regra de ouro:</b> toda pergunta de implementação volta para <b>valor</b> ou para <b>integração</b> (inputs/outputs/APIs).</div>
  </div>

  <h2><span class="badge b-alert">Alerta</span> &nbsp;sinais a anotar</h2><div class="rule"></div>
  <div class="block alert"><ul>
    <li>Insistência em arquitetura / algoritmo / fonte de dado.</li>
    <li>"Temos um time que poderia fazer isso" / "quanto tempo levaria pra refazer?".</li>
    <li>Pedido de acesso ao código, ao banco, ou export do dado.</li>
  </ul>
  <p style="margin-top:4px">Resposta educada e firme: <b>"Isso é o núcleo licenciado, fora do escopo desta avaliação."</b></p></div>

  <h2>Fechamento &amp; postura</h2><div class="rule"></div>
  <ul>
    <li><b>Não fale preço</b> — é a próxima reunião, com os diretores. Mantenha o frame de 3 linhas: <span class="pill">Mari CLT</span> + <span class="pill">licença da ferramenta</span> + <span class="pill">você PJ</span>.</li>
    <li>Reforce: <b>"a ferramenta é licenciada, não vendida; o valor está no motor + dado curado + atualização contínua".</b></li>
    <li>Defina o próximo passo: reunião com diretores para valores.</li>
    <li><b>Postura:</b> confiante e colaborativo, com linha nítida entre <i>o que ela faz</i> (aberto) e <i>como ela faz</i> (fechado). Você não pede emprego — licencia um ativo que já funciona e que eles não têm.</li>
  </ul>
"""

render("/tmp/out/WiNS_NDA_minuta.pdf",
       "Acordo de Confidencialidade (Mútuo)",
       f"Minuta para revisão jurídica · WiNS Hub Agro × Grupo Monte Sião · {HOJE.strftime('%d/%m/%Y')}",
       nda, "NDA (minuta)")

render("/tmp/out/WiNS_Roteiro_TI.pdf",
       "Roteiro — Reunião com o Time de TI",
       f"Uso interno · Preparação · Reunião em {AMANHA.strftime('%d/%m/%Y')} 17h",
       roteiro, "Roteiro TI — uso interno")
