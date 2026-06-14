#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-pager de IMPACTO do WiNS Hub Agro p/ enviar a grandes grupos.
Foco: decisores + técnicos com contato (WhatsApp/e-mail/Instagram), com gráficos SVG.
Roda no container api (WeasyPrint). Saída: /tmp/WiNS_OnePager.pdf"""
from weasyprint import HTML

def br(n): return f"{n:,}".replace(",", ".")

# ---- gráfico de barras horizontais em SVG (WeasyPrint renderiza inline) ----
def bars(items, maxv, color="#2e7d32", hi="#d9a441", w=560, rowh=36, gap=15, lab=13):
    top, labelw, valw = 4, 150, 100
    barx = labelw + 10
    barw = w - barx - valw
    h = top + len(items) * (rowh + gap)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI,Arial,sans-serif">']
    for i, (label, val, note) in enumerate(items):
        y = top + i * (rowh + gap)
        bw = max(4, round(barw * val / maxv))
        c = hi if i == 0 else color
        out.append(f'<text x="0" y="{y+rowh/2+5}" font-size="{lab}" font-weight="700" fill="#1f2a20">{label}</text>')
        out.append(f'<rect x="{barx}" y="{y}" width="{bw}" height="{rowh}" rx="6" fill="{c}"/>')
        out.append(f'<text x="{barx+bw+9}" y="{y+rowh/2-1}" font-size="15" font-weight="800" fill="#13301a">{br(val)}</text>')
        if note:
            out.append(f'<text x="{barx+bw+9}" y="{y+rowh/2+13}" font-size="9" fill="#7a857a">{note}</text>')
    out.append('</svg>')
    return "".join(out)

# ===== dados reais =====
DECISORES = 200489
# WhatsApp/Celular = casado com o KPI da página Fazendas (whatsapp OU celular do RFB).
DEC_TEL, DEC_WA, DEC_EMAIL, DEC_IG = 199406, 70218, 143852, 7598
TECNICOS = 15964            # fila técnica curada (canal técnico amplo = 53.270)
TEC_EMAIL, TEC_WA = 13607, 10199
DEP, ICP = 1242711, 1461
# Deserto Vet v3 (regional, raio 75km, carga gado/técnico): municípios + cabeças + fazendas da base
DESERTO_MUN, DESERTO_CAB, DESERTO_FAZ, BAIXA_FAZ = 539, 91433748, 3190, 7362

chart_dec = bars([
    ("Telefone", DEC_TEL, "99% das fazendas"),
    ("E-mail", DEC_EMAIL, "72%"),
    ("WhatsApp / celular", DEC_WA, "35%"),
    ("Instagram", DEC_IG, "4% — fazenda-marca"),
], maxv=DEC_TEL)

chart_tec = bars([
    ("E-mail", TEC_EMAIL, "85%"),
    ("WhatsApp / cel.", TEC_WA, "64%"),
], maxv=TECNICOS, color="#235c2e", w=420, lab=12)

CSS = """
@page { size: A4; margin: 13mm 13mm; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; color:#1f2a20; font-size:11px; }
.hero { background:linear-gradient(120deg,#13301a 0%,#235c2e 60%,#2e7d32 100%); color:#fff; border-radius:15px; padding:24px 26px; }
.hero .tag { color:#f0d28a; font-size:10.5px; font-weight:700; letter-spacing:1.8px; text-transform:uppercase; }
.hero h1 { font-size:30px; line-height:1.1; margin:7px 0 6px; font-weight:800; }
.hero p { color:#d4ead4; font-size:13px; }
.stats { display:flex; gap:10px; margin:16px 0; }
.stat { flex:1; border:1px solid #e4e9e4; border-radius:12px; padding:14px 8px; text-align:center; background:#fbfdfb; }
.stat .v { font-size:28px; font-weight:800; color:#13301a; line-height:1; }
.stat .k { font-size:9px; color:#5a675a; text-transform:uppercase; letter-spacing:.3px; margin-top:6px; }
h2 { color:#235c2e; font-size:14.5px; margin:18px 0 4px; }
h2 .s { color:#9aa39a; font-weight:600; font-size:10px; }
.two { display:flex; gap:20px; align-items:flex-start; margin-top:10px; }
.two .col { flex:1; }
.why { margin-top:4px; }
.why .row { background:#f3faf4; border-left:4px solid #d9a441; border-radius:7px; padding:9px 13px; margin-bottom:8px; font-size:11.5px; }
.why b { color:#13301a; }
.cta { text-align:center; margin-top:20px; padding:18px; background:#13301a; color:#fff; border-radius:13px; }
.cta .big { font-size:18px; font-weight:800; }
.cta .small { color:#cfe6cf; font-size:11px; margin-top:4px; }
.foot { text-align:center; color:#9aa39a; font-size:9px; margin-top:12px; }
.gold { color:#a07a00; }
"""

DOC = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<div class="hero">
  <div class="tag">WiNS Hub Agro · Inteligência Genética Bovina</div>
  <h1>Você não vende pra quem não conhece.</h1>
  <p>O <b style="color:#fff">mapa de quem decide</b> em cada fazenda do Brasil — com o contato na mão e a genética que fecha a venda.</p>
</div>

<div class="stats">
  <div class="stat"><div class="v">{br(DECISORES)}</div><div class="k">Decisores identificados</div></div>
  <div class="stat"><div class="v">99%</div><div class="k">Fazendas com contato</div></div>
  <div class="stat"><div class="v">91&nbsp;mi</div><div class="k">Cabeças em deserto vet</div></div>
  <div class="stat"><div class="v">1,24&nbsp;mi</div><div class="k">Avaliações genéticas</div></div>
</div>

<h2>Fale DIRETO com o decisor de cada fazenda <span class="s">— {br(DECISORES)} fazendas mapeadas, contato por canal</span></h2>
{chart_dec}

<div class="two">
  <div class="col">
    <h2>O canal técnico <span class="s">— quem influencia a compra</span></h2>
    {chart_tec}
    <div style="font-size:9px;color:#7a857a;margin-top:2px">{br(TECNICOS)} veterinários e zootecnistas — o multiplicador da sua genética.</div>
  </div>
  <div class="col">
    <h2>O que isso significa pra você</h2>
    <div class="why">
      <div class="row"><b>Ache o decisor certo</b> — não o telefone da portaria; o dono/administrador que assina a compra.</div>
      <div class="row"><b>Fale na hora</b> — WhatsApp, e-mail e Instagram já prontos pra abordar.</div>
      <div class="row"><b>Prove o retorno</b> — cruzamento, bezerro previsto e <span class="gold">ROI por dose</span> na tela, no campo.</div>
      <div class="row"><b>539 municípios em deserto vet</b> (91 mi de cabeças) — regiões sem cobertura veterinária regional: mercado sem concorrência.</div>
    </div>
  </div>
</div>

<div class="cta">
  <div class="big">Pare de procurar cliente. Comece a escolher.</div>
  <div class="small">Site (gestão) + App de campo (offline) — a inteligência do rebanho brasileiro na palma da mão.</div>
</div>

<div class="foot">WiNS Hub Agro · dados Receita Federal + programas de melhoramento genético · números reais da base.</div>

</body></html>"""

HTML(string=DOC).write_pdf("/tmp/WiNS_OnePager.pdf")
print("OK /tmp/WiNS_OnePager.pdf")
