#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o PDF de Valoração & Modelo de Negócio do WiNS Hub Agro (identidade verde).
Roda dentro do container api (WeasyPrint). Saída: /tmp/WiNS_Valoracao.pdf"""
from weasyprint import HTML
from datetime import date

HOJE = date(2026, 6, 14).strftime("%d/%m/%Y")

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI','Helvetica Neue',Arial,sans-serif; color:#1f2a20; font-size:10.5px; line-height:1.5; }
h1 { color:#13301a; font-size:21px; margin:0 0 2px; }
h2 { color:#235c2e; font-size:13.5px; margin:18px 0 6px; padding-bottom:3px; border-bottom:2px solid #d9a441; }
h3 { color:#2e7d32; font-size:11.5px; margin:12px 0 4px; }
.sub { color:#5a675a; font-size:10px; }
.cover { background:linear-gradient(120deg,#13301a,#235c2e); color:#fff; border-radius:12px; padding:20px 22px; margin-bottom:14px; }
.cover h1 { color:#fff; }
.cover .tag { color:#d9a441; font-weight:700; font-size:11px; letter-spacing:.4px; text-transform:uppercase; }
.cover .sub { color:#cfe6cf; }
table { width:100%; border-collapse:collapse; margin:6px 0 4px; }
th,td { text-align:left; padding:5px 8px; border-bottom:1px solid #e4e9e4; vertical-align:top; }
th { background:#f3faf4; color:#235c2e; font-size:9px; text-transform:uppercase; letter-spacing:.04em; }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; }
.tot td { font-weight:800; color:#13301a; border-top:2px solid #235c2e; background:#f3faf4; }
.cards { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0; }
.card { flex:1 1 30%; border:1px solid #e4e9e4; border-radius:10px; padding:9px 11px; background:#fbfdfb; }
.card .k { font-size:8.5px; text-transform:uppercase; color:#7a857a; letter-spacing:.04em; }
.card .v { font-size:17px; font-weight:800; color:#13301a; }
.card .d { font-size:8.5px; color:#7a857a; }
.callout { background:#eef7ea; border-left:3px solid #4a9e4a; padding:8px 11px; border-radius:6px; margin:8px 0; }
.gold { color:#a07a00; font-weight:700; }
.muted { color:#7a857a; }
.foot { margin-top:14px; padding-top:8px; border-top:1px solid #e4e9e4; color:#9aa39a; font-size:8.5px; }
ul { margin:3px 0 3px 16px; padding:0; } li { margin:2px 0; }
.big { font-size:22px; font-weight:800; color:#235c2e; }
"""

HTML_DOC = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<div class="cover">
  <div class="tag">Valoração & Modelo de Negócio</div>
  <h1>WiNS Hub Agro</h1>
  <div class="sub">Inteligência genética bovina + prospecção + app de campo · {HOJE}</div>
</div>

<h2>1. O ativo de dados (números reais do banco — 4,1 GB)</h2>
<div class="cards">
  <div class="card"><div class="k">Fazendas c/ decisor</div><div class="v">200.489</div><div class="d">199.856 c/ decisor nomeado (49.331 c/ 2+)</div></div>
  <div class="card"><div class="k">Avaliações genéticas (DEP)</div><div class="v">1,24 mi</div><div class="d">58.064 touros + 19.812 matrizes · 22 raças</div></div>
  <div class="card"><div class="k">ICP genético qualificado</div><div class="v">1.411</div><div class="d">508 alta + 903 média (compram genética)</div></div>
  <div class="card"><div class="k">Canal técnico (vet/zootec)</div><div class="v">15.964</div><div class="d">4.448 confirmados · 536 CRMV</div></div>
  <div class="card"><div class="k">Contato (WhatsApp)</div><div class="v">70,2k</div><div class="d">WhatsApp/celular · 143,9k e-mails · 7,6k IG</div></div>
  <div class="card"><div class="k">Catálogo / sêmen</div><div class="v">843</div><div class="d">touros c/ preço · 34 embriões · 19 centrais · 5.536 municípios</div></div>
  <div class="card"><div class="k">Deserto vet (oportunidade)</div><div class="v">91 mi</div><div class="d">cabeças em 539 municípios sem cobertura vet regional</div></div>
</div>

<h2>2. As duas ferramentas</h2>
<h3>Site (Hub) — 5 páginas</h3>
<p class="muted"><b>Fazendas</b> (banco de leads + dossiê/PDF por fazenda) · <b>Técnica</b> (canal vet, tier, alcance) ·
<b>Mapa</b> (5 camadas + relatório territorial PDF) · <b>Cruzamento</b> (catálogo, ficha c/ radar de DEPs, R$/IQGg,
bezerro previsto + gráfico, sugestões vaca→touros, monetização, parecer PDF) · <b>Comercial</b> (motor de matching
perfil→touros, <b>ROI / valor agregado</b>, justificativa de preço, parecer zootécnico PDF). Segurança bancária
(bcrypt + MFA + login por digital, auditoria, backup cifrado).</p>
<h3>App de campo (offline-first, PWA + APK Android)</h3>
<p class="muted">Cadastro / pesagem / sanitário / agenda c/ alertas / GTA / descarte · OCR de brinco (câmera) ·
auditoria genética do rebanho · Cruzar ao vivo (bezerro + gráfico + ROI) · cotação / proposta / parecer / briefing em PDF ·
estação de monta IATF · painel de vendas · flywheel previsto×realizado. Sincroniza com o Hub.</p>

<h2>3. Modelo recomendado — "pacote" (melhor cenário, por grupo)</h2>
<table>
  <thead><tr><th>Item (mensal)</th><th class="n">Gado (agora)</th><th class="n">Gado + equino (maduro)</th></tr></thead>
  <tbody>
    <tr><td><b>Mari</b> — vet + zootec + cientista de dados (CLT carregado + campo)</td><td class="n">R$ 20–22k</td><td class="n">R$ 25k</td></tr>
    <tr><td><b>Hub</b> (dados + inteligência) — licença</td><td class="n">R$ 15k</td><td class="n">R$ 17k</td></tr>
    <tr><td><b>App de campo</b> — licença</td><td class="n">R$ 9k</td><td class="n">R$ 9k</td></tr>
    <tr><td>Incremento <b>equino</b> (canal-aware vale mais)</td><td class="n">—</td><td class="n">R$ 8k</td></tr>
    <tr><td>Subtotal fixo / mês</td><td class="n">~R$ 44–46k</td><td class="n">~R$ 59k</td></tr>
    <tr><td>+ Royalty 8% sobre venda atribuível</td><td class="n">~R$ 8–12k</td><td class="n">~R$ 14–18k</td></tr>
    <tr class="tot"><td>= Total por grupo / mês</td><td class="n">~R$ 54–58k</td><td class="n">~R$ 73–77k</td></tr>
  </tbody>
</table>
<div class="callout">Melhor cenário: <span class="big">~R$ 75k/mês por grupo ≈ R$ 0,9 mi/ano</span></div>

<h3>Sua remuneração (PJ — não é salário)</h3>
<p>Como PJ você <b>fatura</b> via nota fiscal (licença + royalty), não recebe salário. Mas tem base fixa: a
<b>licença Hub+App é a garantia mínima</b> (cai todo mês) e o royalty é o variável por cima.</p>
<table>
  <thead><tr><th>Sua PJ (melhor cenário, gado+equino)</th><th class="n">Mensal</th></tr></thead>
  <tbody>
    <tr><td>Licença Hub + App (fixo / garantia mínima)</td><td class="n">~R$ 34k</td></tr>
    <tr><td>Royalty (variável)</td><td class="n">~R$ 14–18k</td></tr>
    <tr class="tot"><td>Faturamento bruto PJ</td><td class="n">~R$ 50k</td></tr>
    <tr><td class="muted">Líquido após imposto PJ (~6–16%, Simples/Lucro Presumido)</td><td class="n muted">~R$ 42–47k</td></tr>
  </tbody>
</table>
<p class="muted">Dentro da PJ: dividir entre <b>pró-labore</b> (parte menor, com INSS) + <b>distribuição de lucros</b>
(o grosso, isento de IR) = eficiência tributária. Projetos em outras ferramentas do grupo = orçamento à parte por
projeto (nunca por hora — evita vínculo). A Mari (R$ 25k) é folha do grupo + comissões.</p>

<h2>4. Opções alternativas de monetização (faixas de valor)</h2>
<table>
  <thead><tr><th>Opção</th><th>O que é</th><th class="n">Faixa de valor</th></tr></thead>
  <tbody>
    <tr><td><b>Lista crua</b> (commodity)</td><td>200k fazendas, contato majoritariamente RFB. Moat fino (brokers já vendem). <b>Não recomendado</b> — queima exclusividade.</td><td class="n">R$ 30–150k (única)<br>ou R$ 0,5–2k/mês</td></tr>
    <tr><td><b>Núcleo qualificado</b></td><td>1.411 ICP genético + 4.448 técnicos confirmados + contatos verificados + camada genética. Pacote direcionado/exclusivo.</td><td class="n">R$ 15–80k (pacote)</td></tr>
    <tr><td><b>SaaS por cliente</b></td><td>Licença mensal a outra empresa que vende pra fazenda (genética / farma vet / nutrição / equipamento).</td><td class="n">R$ 1–10k/mês por cliente</td></tr>
    <tr><td><b>App por ativação</b></td><td>Seat por técnico extra que usar o app de campo.</td><td class="n">~R$ 200–600/técnico/mês</td></tr>
    <tr><td><b>Aquisição estratégica</b></td><td>Custo de reconstruir tudo (pipeline RFB + 1,24 mi DEP + camada genética + 2 ferramentas, ~6–10 meses de time).</td><td class="n">R$ 600k – 1,5 mi+</td></tr>
  </tbody>
</table>

<h2>5. Escala</h2>
<p>O mesmo Hub vira receita nova <b>sem custo proporcional</b> — a base de decisores serve a qualquer empresa que
vende pra fazenda. <b>3 grupos ≈ R$ 1,5–2,2 mi/ano</b> de licença + royalty, com a Mari só no 1º.</p>

<h2>6. Premissas (o que sustenta o melhor cenário)</h2>
<ul>
  <li>O valor está na <b>integração + motor genético (ROI/valor agregado) + app de campo + a Mari embarcada</b>, não na lista crua (RFB é commodity).</li>
  <li>A conta fecha quando a operação destrava <b>R$ 150–250k/mês de receita nova</b> (margem premium do grupo é alta; no equino, 1 cota/embrião paga meses).</li>
  <li><b>Royalty é o coração</b>: captura o upside sem precisar provar tudo antes.</li>
  <li><b>Frescor do dado</b> justifica o aluguel recorrente (atualização contínua na licença).</li>
  <li>Proteger: IP separado do vínculo CLT da Mari · escopo de exclusividade · royalty sobre venda atribuível + piso mensal.</li>
</ul>

<div class="foot">Documento interno de modelagem — ordens de grandeza a calibrar com salário real da Mari, volume de venda e
custo de fontes de dado. Gerado em {HOJE}. WiNS Hub Agro.</div>

</body></html>"""

HTML(string=HTML_DOC).write_pdf("/tmp/WiNS_Valoracao.pdf")
print("OK /tmp/WiNS_Valoracao.pdf")
