#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-pager de VENDA: Mapa dos Desertos Veterinários (WiNS Hub Agro).
Território virgem com demanda comprovada p/ centrais de sêmen / farma / nutrição.
Roda no container api (WeasyPrint). Saída: /tmp/WiNS_Mapa_Desertos.pdf"""
from weasyprint import HTML

def br(n): return f"{n:,}".replace(",", ".")

# ===== dados reais (banco wins_agro, jun/2026; PPM/IBGE 2023 + CNPJ RFB abr/2026) =====
MUN, CAB, UFS = 284, 38_715_927, 20
FAZ_DESERTO, FAZ_BAIXA = 3190, 7362
VETS, NUCLEO = 14226, 8252

UF_ROWS = [  # (uf, municipios, cabecas)
    ("MT", 39, 7_426_169), ("PA", 31, 5_105_532), ("TO", 46, 4_826_438),
    ("RO", 20, 4_070_431), ("GO", 37, 3_627_510), ("MS", 14, 3_036_676),
    ("MA", 27, 2_770_600), ("BA", 24, 2_317_341),
]
TOP_MUN = [
    ("Porto Murtinho", "MS", 708_463), ("Cumaru do Norte", "PA", 690_442),
    ("Porto Esperidião", "MT", 663_778), ("Lábrea", "AM", 652_247),
    ("Brasnorte", "MT", 515_136), ("Rio Maria", "PA", 515_019),
    ("Castanheira", "MT", 464_222), ("Nova Canaã do Norte", "MT", 424_411),
]

# ---- barras horizontais SVG por UF (nº de municípios-deserto) ----
def bars(items, w=520, rowh=30, gap=12):
    maxv = max(v for _, v, _ in items)
    labelw, top = 40, 4
    barx = labelw + 8
    valw = 150
    barw = w - barx - valw
    h = top + len(items) * (rowh + gap)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI,Arial,sans-serif">']
    for i, (uf, val, cab) in enumerate(items):
        y = top + i * (rowh + gap)
        bw = max(4, round(barw * val / maxv))
        c = "#d9a441" if i == 0 else "#2e7d32"
        out.append(f'<text x="0" y="{y+rowh/2+5}" font-size="14" font-weight="800" fill="#1f2a20">{uf}</text>')
        out.append(f'<rect x="{barx}" y="{y}" width="{bw}" height="{rowh}" rx="5" fill="{c}"/>')
        out.append(f'<text x="{barx+bw+8}" y="{y+rowh/2+5}" font-size="13" font-weight="800" fill="#13301a">{val} mun.</text>')
        out.append(f'<text x="{barx+bw+72}" y="{y+rowh/2+5}" font-size="11" fill="#7a857a">{br(cab)} cab.</text>')
    out.append('</svg>')
    return "".join(out)

rows_mun = "".join(
    f'<tr><td class="m">{n}</td><td class="u">{uf}</td><td class="c">{br(c)}</td></tr>'
    for n, uf, c in TOP_MUN)

HTML_DOC = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 14mm 13mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; color:#1f2a20; margin:0; }}
.kicker {{ color:#2e7d32; font-weight:800; letter-spacing:2px; font-size:11px; text-transform:uppercase; }}
h1 {{ font-size:27px; margin:2px 0 4px; line-height:1.08; }}
h1 span {{ color:#2e7d32; }}
.sub {{ color:#56635a; font-size:12.5px; margin:0 0 12px; }}
.band {{ display:flex; gap:10px; margin:10px 0 14px; }}
.stat {{ flex:1; background:#f3f7f1; border:1px solid #e0ebdd; border-radius:10px; padding:12px 14px; }}
.stat .n {{ font-size:30px; font-weight:900; color:#1b5e20; line-height:1; }}
.stat .n.alt {{ color:#b8860b; }}
.stat .l {{ font-size:10.5px; color:#56635a; margin-top:5px; line-height:1.25; }}
.thesis {{ background:#13301a; color:#eaf3e7; border-radius:10px; padding:13px 16px; font-size:13px; line-height:1.5; margin-bottom:14px; }}
.thesis b {{ color:#d9a441; }}
.cols {{ display:flex; gap:18px; }}
.col {{ flex:1; }}
.h2 {{ font-size:13px; font-weight:800; color:#1b5e20; margin:0 0 8px; border-bottom:2px solid #e0ebdd; padding-bottom:4px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
td {{ padding:4px 2px; border-bottom:1px solid #eef2ec; }}
td.m {{ font-weight:700; }} td.u {{ color:#2e7d32; font-weight:800; width:34px; }}
td.c {{ text-align:right; color:#13301a; font-weight:700; }}
.chan {{ background:#f3f7f1; border:1px solid #e0ebdd; border-radius:10px; padding:12px 16px; margin-top:14px; font-size:12.5px; line-height:1.5; }}
.chan b {{ color:#1b5e20; }}
.offer {{ margin-top:13px; font-size:12.5px; line-height:1.55; }}
.offer li {{ margin-bottom:3px; }}
.foot {{ margin-top:13px; padding-top:9px; border-top:1px solid #e0ebdd; font-size:9.5px; color:#8a948a; line-height:1.4; }}
</style></head><body>

<div class="kicker">WiNS Hub Agro · Inteligência de Território</div>
<h1>O Mapa dos <span>Desertos Veterinários</span></h1>
<p class="sub">Onde há gado de sobra e assistência técnica de menos — território virgem, demanda comprovada, zero concorrência instalada.</p>

<div class="band">
  <div class="stat"><div class="n">{MUN}</div><div class="l">municípios com <b>50 mil+ cabeças</b> e <b>ZERO</b> CNPJ veterinário</div></div>
  <div class="stat"><div class="n alt">{br(round(CAB/1_000_000))}M</div><div class="l">cabeças de gado <b>sem assistência</b> formalizada nesses municípios</div></div>
  <div class="stat"><div class="n">{UFS}</div><div class="l">estados com fronteira pecuária descoberta</div></div>
  <div class="stat"><div class="n">{br(FAZ_DESERTO)}</div><div class="l">fazendas mapeadas em <b>deserto vet</b> (+{br(FAZ_BAIXA)} em baixa cobertura)</div></div>
</div>

<div class="thesis">
Cada cabeça de gado precisa de vacina, vermífugo, mineral, manejo reprodutivo e genética.
Nestes {MUN} municípios há <b>{br(round(CAB/1_000_000))} milhões de cabeças</b> e <b>nenhum veterinário formalizado</b> para atendê-las.
Para uma central de sêmen, farma ou nutrição, isto não é um vazio — é <b>mercado endereçável sem disputa</b>,
com o contato do decisor já na mão.
</div>

<div class="cols">
  <div class="col">
    <div class="h2">Onde está a fronteira (por estado)</div>
    {bars(UF_ROWS)}
  </div>
  <div class="col">
    <div class="h2">Maiores municípios-deserto</div>
    <table>{rows_mun}</table>
  </div>
</div>

<div class="chan">
  <b>Como se entra:</b> não pelo disparo frio — pelo <b>multiplicador</b>. Temos <b>{br(VETS)} médicos-veterinários de pecuária</b>
  triados e contactáveis (núcleo de alta confiança: <b>{br(NUCLEO)}</b>), cada um prescritor para dezenas de fazendas.
  É o canal de entrada legítimo e de maior alcance nesses territórios.
</div>

<div class="offer">
  <b>O que está incluído no recorte:</b>
  <ul>
    <li>Lista dos municípios-deserto da raça/região escolhida, com rebanho e ranking de oportunidade.</li>
    <li>Fazendas com porte de rebanho, decisor identificado e <b>WhatsApp</b> (quando disponível).</li>
    <li>Vets de pecuária da região como canal de prescrição.</li>
    <li>Atualização trimestral (Receita + IBGE/PPM).</li>
  </ul>
</div>

<div class="foot">
  Fontes: IBGE/PPM (rebanho bovino, 2023) · Receita Federal/CNPJ (estabelecimentos e CNAE veterinário, dump abr/2026) · base proprietária WiNS Hub Agro.
  Deserto = município com rebanho bovino ≥ 50.000 cabeças e nenhum CNPJ com atividade veterinária (CNAE 7500100).
  Dados de contato tratados sob interesse legítimo B2B, com origem rastreável e opção de descadastro (LGPD). Documento sem dados pessoais sensíveis.
  Gerado em jun/2026.
</div>

</body></html>"""

HTML(string=HTML_DOC).write_pdf("/tmp/WiNS_Mapa_Desertos.pdf")
print("OK -> /tmp/WiNS_Mapa_Desertos.pdf")
