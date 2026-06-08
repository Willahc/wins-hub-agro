#!/usr/bin/env python3
"""PoC: parecer de acasalamento em HTML/CSS -> PDF via WeasyPrint.
Lê /tmp/cruz.json (payload real de /api/cruzamento) e gera /tmp/out/parecer_poc.pdf.
Espelha a identidade visual da plataforma (verde, cards, tabelas)."""
import json, os
from datetime import datetime
from weasyprint import HTML

d = json.load(open("/tmp/cruz.json"))
touro, vaca, calf, rel = d["touro"], d["vaca"], d["calf"], d["relacao"]
iqgg = calf["iqgg"]; traits = calf["traits"]; labels = calf["trait_labels"]
f1 = " · F1" if d.get("f1") else ""

def f(v, dec=1):
    return f"{v:.{dec}f}" if isinstance(v, (int, float)) else "—"

def delta(v, dec=2):
    if not isinstance(v, (int, float)): return '<span class="d-na">—</span>'
    cls = "d-pos" if v > 0 else ("d-neg" if v < 0 else "d-zero")
    sig = "+" if v > 0 else ""
    return f'<span class="{cls}">{sig}{v:.{dec}f}</span>'

# severidade -> cor do banner de parentesco
sev = rel.get("severidade")
banner_cls = {"bloqueio": "bn-block", "alerta": "bn-warn"}.get(sev, "bn-ok")
banner_ico = {"bloqueio": "&#9940;", "alerta": "&#9888;"}.get(sev, "&#10003;")
banner_txt = (f"<b>Acasalamento liberado.</b> {rel.get('label','Sem parentesco detectado')}."
              if sev not in ("bloqueio", "alerta")
              else f"<b>{rel.get('label','')}</b>")

# linhas da tabela
rows = ""
ordered = [("__iqgg__", "Índice geral (IQGg)", iqgg)] + \
          [(k, labels.get(k, k), traits[k]) for k in traits if k != "__iqgg__" and labels.get(k) != "Índice geral (IQGg)"]
seen = set()
for k, lbl, t in ordered:
    if lbl in seen: continue
    seen.add(lbl)
    destaque = ' class="hl"' if lbl.startswith("Índice geral") else ""
    rows += f"""<tr{destaque}>
      <td class="lbl">{lbl}</td>
      <td>{f(t.get('touro'),2)}</td>
      <td>{f(t.get('vaca'),2)}</td>
      <td class="cria">{f(t.get('cria'),2)}</td>
      <td>{delta(t.get('vs_touro'))}</td>
      <td>{delta(t.get('vs_vaca'))}</td>
    </tr>"""

# barras vetoriais (pai/mãe/cria) para o IQGg — demonstra "gráfico" sem raster
vals = [("Touro (pai)", iqgg.get("touro"), "#4a9e4a"),
        ("Vaca (mãe)", iqgg.get("vaca"), "#caa45a"),
        ("Bezerro previsto", iqgg.get("cria"), "#1a3a1a")]
mx = max([v for _, v, _ in vals if isinstance(v, (int, float))] + [1])
bars = ""
for nome, v, cor in vals:
    w = (max(v, 0) / mx * 100) if isinstance(v, (int, float)) else 0
    bars += f"""<div class="bar-row">
      <div class="bar-name">{nome}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%;background:{cor}"></div></div>
      <div class="bar-val">{f(v,1)}</div>
    </div>"""

data_str = datetime.now().strftime("%d/%m/%Y")

html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
  @page {{
    size: A4; margin: 0 0 22mm 0;
    @bottom-center {{
      content: "WiNS Hub Agro · Parecer de acasalamento · pág. " counter(page) " de " counter(pages);
      font: 8pt 'DejaVu Sans', sans-serif; color: #8a978a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: 'DejaVu Sans', Arial, sans-serif; color: #1f2a1f; font-size: 10.5pt; }}
  .wrap {{ padding: 0 18mm; }}

  /* faixa-capa verde full-bleed */
  .cover {{ background: #1a3a1a; color: #fff; padding: 30mm 18mm 14mm; }}
  .brand {{ font-size: 22pt; font-weight: 700; letter-spacing: .5px; }}
  .brand .a {{ color: #7fc77f; }}
  .doc-title {{ margin-top: 14px; font-size: 13pt; color: #cfe6cf; text-transform: uppercase; letter-spacing: 2px; }}
  .doc-sub {{ margin-top: 4px; font-size: 10pt; color: #9fc59f; }}

  h2 {{ font-size: 12pt; color: #1a3a1a; margin: 22px 0 4px; }}
  .rule {{ height: 3px; background: #4a9e4a; border-radius: 2px; width: 46px; margin-bottom: 12px; }}

  /* cruzamento: 3 cards via tabela (robusto no WeasyPrint) */
  .cross {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 14px; }}
  .cross td {{ vertical-align: middle; text-align: center; }}
  .card {{ border-radius: 12px; padding: 14px 10px; }}
  .card .role {{ font-size: 8pt; color: #6b7a6b; text-transform: uppercase; letter-spacing: 1px; }}
  .card .nome {{ font-size: 11pt; font-weight: 700; margin: 3px 0; color: #1a3a1a; }}
  .card .meta {{ font-size: 8pt; color: #788; }}
  .card .iq {{ font-size: 9pt; margin-top: 4px; color: #2d5a2d; }}
  .c-bull {{ background: #eef5ee; }}
  .c-cow  {{ background: #f6f1ea; }}
  .c-calf {{ background: #e7f3e0; border: 1.5px solid #4a9e4a; }}
  .c-calf .big {{ font-size: 19pt; font-weight: 800; color: #1a3a1a; line-height: 1; margin: 4px 0 2px; }}
  .op {{ font-size: 18pt; color: #2d5a2d; font-weight: 700; width: 26px; }}

  /* banner parentesco */
  .banner {{ margin-top: 16px; border-radius: 10px; padding: 11px 14px; font-size: 10pt; }}
  .bn-ok    {{ background: #eef7ea; border: 1px solid #4a9e4a; color: #1f5a1f; }}
  .bn-warn  {{ background: #fdf6e8; border: 1px solid #c79a2a; color: #7a5a12; }}
  .bn-block {{ background: #fbeaea; border: 1px solid #b34; color: #8a2222; }}

  /* tabela de características — cara da plataforma */
  table.cmp {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 9.5pt;
              border-radius: 10px; overflow: hidden; box-shadow: 0 1px 0 #e3ebe3; }}
  table.cmp thead th {{ background: #1a3a1a; color: #fff; padding: 9px 8px; font-size: 8.5pt;
              text-transform: uppercase; letter-spacing: .4px; text-align: center; }}
  table.cmp thead th:first-child {{ text-align: left; }}
  table.cmp td {{ padding: 8px; text-align: center; border-bottom: 1px solid #eef2ee; }}
  table.cmp td.lbl {{ text-align: left; color: #344334; }}
  table.cmp td.cria {{ font-weight: 700; color: #1a3a1a; }}
  table.cmp tbody tr:nth-child(even) {{ background: #f7faf6; }}
  table.cmp tr.hl {{ background: #eef7ea !important; }}
  table.cmp tr.hl td {{ font-weight: 700; }}
  .d-pos {{ color: #2d7d2d; font-weight: 700; }}
  .d-neg {{ color: #c0392b; font-weight: 700; }}
  .d-zero, .d-na {{ color: #9aa39a; }}

  /* barras vetoriais */
  .bars {{ margin-top: 10px; }}
  .bar-row {{ display: flex; align-items: center; margin: 7px 0; }}
  .bar-name {{ width: 130px; font-size: 9pt; color: #445; }}
  .bar-track {{ flex: 1; height: 16px; background: #eef3ee; border-radius: 8px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 8px; }}
  .bar-val {{ width: 56px; text-align: right; font-size: 9pt; font-weight: 700; color: #1a3a1a; }}

  .note {{ margin-top: 18px; font-size: 8.5pt; color: #7a857a; line-height: 1.5; border-top: 1px solid #e6ece6; padding-top: 10px; }}
</style></head><body>

  <div class="cover">
    <div class="brand">WiNS Hub <span class="a">Agro</span></div>
    <div class="doc-title">Parecer de Acasalamento{f1}</div>
    <div class="doc-sub">Touro × Vaca = Bezerro previsto · Gerado em {data_str}</div>
  </div>

  <div class="wrap">
    <h2>Cruzamento</h2><div class="rule"></div>
    <table class="cross"><tr>
      <td style="width:30%"><div class="card c-bull">
        <div class="role">&#128002; Touro (pai)</div>
        <div class="nome">{touro.get('nome','—')}</div>
        <div class="meta">{touro.get('raca_sigla','')} · {touro.get('registro','—')}</div>
        <div class="iq">IQGg {f(touro.get('iqgg'))}</div>
      </div></td>
      <td class="op">×</td>
      <td style="width:30%"><div class="card c-cow">
        <div class="role">&#128004; Vaca (mãe)</div>
        <div class="nome">{vaca.get('nome','—')}</div>
        <div class="meta">{vaca.get('raca_sigla','')} · {vaca.get('registro','—')}</div>
        <div class="iq">IQGg {f(vaca.get('iqgg'))}</div>
      </div></td>
      <td class="op">=</td>
      <td style="width:32%"><div class="card c-calf">
        <div class="role">&#128046; Bezerro previsto</div>
        <div class="big">{f(iqgg.get('cria'))}</div>
        <div class="meta">IQGg estimado · vs pai {delta(iqgg.get('vs_touro'),1)} · vs mãe {delta(iqgg.get('vs_vaca'),1)}</div>
      </div></td>
    </tr></table>

    <div class="banner {banner_cls}">{banner_ico} &nbsp;{banner_txt}</div>

    <h2>Índice geral previsto</h2><div class="rule"></div>
    <div class="bars">{bars}</div>

    <h2>Previsão por característica</h2><div class="rule"></div>
    <table class="cmp">
      <thead><tr><th>Característica</th><th>Touro (pai)</th><th>Vaca (mãe)</th>
        <th>Bezerro</th><th>vs pai</th><th>vs mãe</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>

    <div class="note">
      O bezerro previsto reflete o mérito médio dos pais (½ touro + ½ vaca) por característica.
      Valores ausentes (—) indicam DEP não disponível na base para o animal/característica.
      Parentesco avaliado pelo pedigree. Documento gerado automaticamente pela plataforma WiNS Hub Agro.
    </div>
  </div>
</body></html>"""

os.makedirs("/tmp/out", exist_ok=True)
open("/tmp/out/parecer_poc.html", "w").write(html)
HTML(string=html).write_pdf("/tmp/out/parecer_poc.pdf")
print("OK -> /tmp/out/parecer_poc.pdf")
