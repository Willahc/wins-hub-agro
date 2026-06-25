"""Geração de PDF via HTML/CSS -> WeasyPrint (qualidade de impressão, vetorial).
Espelha a identidade visual da plataforma (verde, cards, tabelas). Ícones SVG
inline (sem dependência de fonte de emoji).

Dois pareceres compartilham o mesmo CSS base (_BASE_CSS) para consistência:
  - gerar_parecer_cruzamento  -> acasalamento (Touro × Vaca = Bezerro)
  - gerar_parecer_matching    -> recomendação de reprodutores (matching)
"""
from datetime import datetime
from html import escape as _html_escape
from weasyprint import HTML
from pdf_generator import LABEL_FINALIDADE, LABEL_PRIORIDADE, _num  # reusa labels/coerção


def _esc(v):
    """Escapa texto vindo do usuário (nome de fazenda/animal, obs, GTA…) antes de
    interpolar no HTML do PDF. Sem isso, '&', '<' ou tags quebram a renderização
    (WeasyPrint parseia XML) ou injetam conteúdo. None -> string vazia."""
    return _html_escape(str(v)) if v is not None else ""

# --- paleta (mesma do front) ---
VERDE_ESCURO = "#1a3a1a"
VERDE_MEDIO = "#2d5a2d"
VERDE_CLARO = "#4a9e4a"
OURO = "#caa45a"


def _f(v, dec=1):
    v = _num(v)
    return f"{v:.{dec}f}" if v is not None else "—"


def _brl(v, dec=0):
    v = _num(v)
    if v is None:
        return "—"
    s = f"{v:,.{dec}f}".replace(",", "·").replace(".", ",").replace("·", ".")
    return f"R$ {s}"


def _delta(v, dec=2):
    v = _num(v)
    if v is None:
        return '<span class="d-na">—</span>'
    cls = "d-pos" if v > 0 else ("d-neg" if v < 0 else "d-zero")
    sig = "+" if v > 0 else ""
    return f'<span class="{cls}">{sig}{v:.{dec}f}</span>'


def _calf_chart_svg(iqgg: dict, traits: dict, labels: dict) -> str:
    """Gráfico de barras agrupado Pai/Mãe/Bezerro por característica (SVG vetorial).
    Cada grupo é normalizado pelo maior valor entre pai/mãe/bezerro — mesma leitura
    do gráfico da tela. Ausência (DEP faltando) = sem barra, com um tracinho na base."""
    items, seen = [("IQGg", iqgg or {})], {"IQGg"}
    for k, t in (traits or {}).items():
        lbl = (labels.get(k, k) or k).split(" (")[0]
        if lbl in seen:
            continue
        seen.add(lbl)
        items.append((lbl, t or {}))
    n = max(len(items), 1)
    W, H, top, label_h = 660, 52, 3, 15
    gw = W / n
    bw = min(15.0, (gw - 16) / 3)
    gap = 4
    series = [("touro", "#9cc49c"), ("vaca", "#d8c4a8"), ("cria", "#2d5a2d")]
    parts = [f'<line x1="0" y1="{top+H}" x2="{W}" y2="{top+H}" stroke="#e3ebe3" stroke-width="1"/>']
    for gi, (lbl, t) in enumerate(items):
        vals = [_num(t.get(s)) for s, _ in series]
        mx = max([v for v in vals if v is not None and v > 0] + [0.0001])
        cx = gi * gw + gw / 2
        x0 = cx - (3 * bw + 2 * gap) / 2
        for bi, (key, cor) in enumerate(series):
            v = _num(t.get(key))
            x = x0 + bi * (bw + gap)
            if v is not None and v > 0:
                h = v / mx * H
                parts.append(f'<rect x="{x:.1f}" y="{top+H-h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{cor}"/>')
            else:
                parts.append(f'<line x1="{x:.1f}" y1="{top+H}" x2="{x+bw:.1f}" y2="{top+H}" stroke="#c4d0c4" stroke-width="2"/>')
        parts.append(f'<text x="{cx:.1f}" y="{top+H+13:.1f}" font-size="9" text-anchor="middle" fill="#445544">{lbl}</text>')
    svg = (f'<svg viewBox="0 0 {W} {top+H+label_h}" width="100%" preserveAspectRatio="xMidYMid meet" '
           f'style="display:block;margin-top:6px">{"".join(parts)}</svg>')
    legenda = (
        '<div style="display:flex;gap:18px;justify-content:center;margin-top:4px;font-size:8.5pt;color:#566">'
        '<span><span style="display:inline-block;width:10px;height:10px;background:#9cc49c;border-radius:2px"></span> Pai</span>'
        '<span><span style="display:inline-block;width:10px;height:10px;background:#d8c4a8;border-radius:2px"></span> Mãe</span>'
        '<span><span style="display:inline-block;width:10px;height:10px;background:#2d5a2d;border-radius:2px"></span> Bezerro</span>'
        '</div>')
    return svg + legenda


def _cattle_svg(cor: str, horns: bool = True) -> str:
    """Cabeça de bovino estilizada (inline SVG). horns=False p/ vaca/cria."""
    h = (f'<path d="M14 18 C6 11 5 22 17 27 Z" fill="{cor}"/>'
         f'<path d="M50 18 C58 11 59 22 47 27 Z" fill="{cor}"/>') if horns else ""
    return (
        f'<svg width="20" height="20" viewBox="0 0 64 64" style="vertical-align:-3px">'
        f'{h}'
        f'<ellipse cx="14" cy="31" rx="7" ry="4.6" fill="{cor}"/>'
        f'<ellipse cx="50" cy="31" rx="7" ry="4.6" fill="{cor}"/>'
        f'<path d="M20 25 H44 a9 9 0 0 1 9 9 v5 a21 19 0 0 1 -42 0 v-5 a9 9 0 0 1 9 -9 Z" fill="{cor}"/>'
        f'<ellipse cx="32" cy="46" rx="11.5" ry="8" fill="#ffffff" opacity="0.9"/>'
        f'<circle cx="27.5" cy="46" r="1.7" fill="{cor}"/>'
        f'<circle cx="36.5" cy="46" r="1.7" fill="{cor}"/></svg>'
    )


# CSS base compartilhado pelos dois pareceres (sem o bloco @page, que leva rótulo).
_BASE_CSS = """
  * { box-sizing: border-box; }
  body { margin: 0; font-family: 'DejaVu Sans', Arial, sans-serif; color: #1f2a1f; font-size: 10.5pt; }
  .wrap { padding: 0 18mm; }
  .cover { background: #1a3a1a; color: #fff; padding: 21mm 18mm 11mm; }
  .brand { font-size: 22pt; font-weight: 700; letter-spacing: .5px; }
  .brand .a { color: #7fc77f; }
  .doc-title { margin-top: 14px; font-size: 13pt; color: #cfe6cf; text-transform: uppercase; letter-spacing: 2px; }
  .doc-sub { margin-top: 4px; font-size: 10pt; color: #9fc59f; }
  h2 { font-size: 12pt; color: #1a3a1a; margin: 10px 0 4px; }
  .rule { height: 3px; background: #4a9e4a; border-radius: 2px; width: 46px; margin-bottom: 12px; }

  /* equação Touro × Vaca = Bezerro (acasalamento) */
  .cross { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 14px; }
  .cross td { vertical-align: middle; text-align: center; }
  .card { border-radius: 12px; padding: 11px 9px; }
  .card .role { font-size: 8pt; color: #6b7a6b; text-transform: uppercase; letter-spacing: 1px; }
  .card .nome { font-size: 11pt; font-weight: 700; margin: 3px 0; color: #1a3a1a; }
  .card .meta { font-size: 8pt; color: #788078; }
  .card .iq { font-size: 9pt; margin-top: 4px; color: #2d5a2d; }
  .c-bull { background: #eef5ee; }
  .c-cow  { background: #f6f1ea; }
  .c-calf { background: #e7f3e0; border: 1.5px solid #4a9e4a; }
  .c-calf .big { font-size: 19pt; font-weight: 800; color: #1a3a1a; line-height: 1; margin: 4px 0 2px; }
  .op { font-size: 18pt; color: #2d5a2d; font-weight: 700; width: 26px; }

  /* banners */
  .banner { margin-top: 9px; border-radius: 10px; padding: 10px 14px; font-size: 10pt; }
  .bn-ok    { background: #eef7ea; border: 1px solid #4a9e4a; color: #1f5a1f; }
  .bn-warn  { background: #fdf6e8; border: 1px solid #c79a2a; color: #7a5a12; }
  .bn-block { background: #fbeaea; border: 1px solid #bb3344; color: #8a2222; }

  /* perfil (matching) — grade de mini-cards */
  .profile { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .pcard { flex: 1 1 28%; min-width: 130px; background: #f5f8f4; border: 1px solid #e6ece6;
           border-radius: 9px; padding: 9px 11px; }
  .pcard .pl { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .6px; color: #6b7a6b; }
  .pcard .pv { font-size: 10.5pt; font-weight: 700; color: #1a3a1a; margin-top: 2px; }

  /* hero do #1 recomendado (matching) */
  .hero { margin-top: 12px; background: #e7f3e0; border: 1.5px solid #4a9e4a; border-radius: 14px; padding: 16px 18px; }
  .hero .rank { display: inline-block; background: #1a3a1a; color: #fff; font-size: 8pt; font-weight: 700;
                text-transform: uppercase; letter-spacing: 1px; padding: 3px 10px; border-radius: 20px; }
  .hero .hn { font-size: 16pt; font-weight: 800; color: #1a3a1a; margin: 8px 0 1px; }
  .hero .hc { font-size: 9pt; color: #5a6b5a; }
  .stat-row { display: flex; gap: 10px; margin-top: 13px; }
  .stat { flex: 1; background: #ffffff; border: 1px solid #d6e6d0; border-radius: 10px; padding: 10px 8px; text-align: center; }
  .stat .sl { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .5px; color: #6b7a6b; }
  .stat .sv { font-size: 16pt; font-weight: 800; color: #1a3a1a; line-height: 1.1; margin-top: 3px; }
  .stat .sv.nd { font-size: 9.5pt; font-weight: 600; color: #9aa39a; }

  /* tabelas (acasalamento e matching) */
  table.cmp { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 9.5pt;
    border-radius: 10px; overflow: hidden; }
  table.cmp thead th { background: #1a3a1a; color: #fff; padding: 9px 8px; font-size: 8.5pt;
    text-transform: uppercase; letter-spacing: .4px; text-align: center; }
  table.cmp thead th:first-child, table.cmp thead th.l { text-align: left; }
  table.cmp td { padding: 6px 8px; text-align: center; border-bottom: 1px solid #eef2ee; }
  table.cmp td.lbl, table.cmp td.l { text-align: left; color: #344334; }
  table.cmp td.nome { text-align: left; font-weight: 700; color: #1a3a1a; overflow-wrap: anywhere; }
  table.cmp td.cria { font-weight: 700; color: #1a3a1a; }
  table.cmp td.nd { color: #b3bcb3; }
  table.cmp tbody tr:nth-child(even) { background: #f7faf6; }
  table.cmp tr.hl, table.cmp tr.top1 { background: #eef7ea !important; }
  table.cmp tr.hl td, table.cmp tr.top1 td { font-weight: 700; }
  .d-pos { color: #2d7d2d; font-weight: 700; }
  .d-neg { color: #c0392b; font-weight: 700; }
  .d-zero, .d-na { color: #9aa39a; }

  /* barras vetoriais */
  .bars { margin-top: 10px; }
  .bar-row { display: flex; align-items: center; margin: 7px 0; }
  .bar-name { width: 130px; font-size: 9pt; color: #445544; }
  .bar-track { flex: 1; height: 16px; background: #eef3ee; border-radius: 8px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 8px; }
  .bar-val { width: 56px; text-align: right; font-size: 9pt; font-weight: 700; color: #1a3a1a; }

  /* fichas anexas (pai/mãe) — cada uma começa em página nova */
  .ficha { break-before: page; padding-top: 4mm; }
  .section-head { background: #1a3a1a; color: #fff; border-radius: 12px; padding: 14px 18px; margin-top: 2px; }
  .section-head .st { font-size: 14pt; font-weight: 700; }
  .section-head .ss { font-size: 9pt; color: #9fc59f; margin-top: 3px; }
  .cols2 { display: flex; gap: 16px; align-items: flex-start; margin-top: 12px; }
  .cols2 > div { flex: 1; }
  .colh { font-size: 9pt; font-weight: 700; color: #2d5a2d; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
  .kv { width: 100%; border-collapse: collapse; font-size: 9.5pt; border-radius: 10px; overflow: hidden; }
  .kv td { padding: 7px 10px; border-bottom: 1px solid #eef2ee; }
  .kv td.k { color: #5a6b5a; }
  .kv td.v { text-align: right; font-weight: 700; color: #1a3a1a; }
  .kv tr:nth-child(even) { background: #f7faf6; }
  .legend { margin-top: 7px; font-size: 8pt; color: #8a948a; }
  /* estratégia de monetização (canal-aware) */
  .mon-row { display: flex; gap: 9px; margin-top: 8px; }
  .mon { flex: 1; border: 1px solid #e0e8e0; border-radius: 10px; padding: 8px 9px; background: #fafcf9; }
  .mon.rec { border: 1.5px solid #4a9e4a; background: #eef7ea; }
  .mon .mt { font-size: 7.5pt; color: #6b7a6b; text-transform: uppercase; letter-spacing: .3px; }
  .mon .mv { font-size: 12pt; font-weight: 800; color: #1a3a1a; margin: 2px 0; }
  .mon .mv .u { font-size: 7.5pt; font-weight: 600; }
  .mon .mv.nd { font-size: 8.5pt; font-weight: 600; color: #9aa39a; }
  .mon .ms { font-size: 7pt; color: #7a857a; line-height: 1.3; }
  .mon .badge { display: inline-block; background: #1a3a1a; color: #fff; font-size: 6pt; font-weight: 700;
    padding: 1px 5px; border-radius: 10px; text-transform: uppercase; letter-spacing: .3px; margin-left: 3px; }
  .mon-rac { margin-top: 6px; font-size: 9pt; color: #283428; line-height: 1.4; }
  .analysis { margin-top: 6px; font-size: 10pt; line-height: 1.55; color: #283428; }
  .analysis b { color: #1a3a1a; }
  .note { margin-top: 9px; font-size: 8.5pt; color: #7a857a; line-height: 1.45;
    border-top: 1px solid #e6ece6; padding-top: 8px; }
"""


def _page_css(footer_label: str) -> str:
    return (
        "@page { size: A4; margin: 0 0 22mm 0;"
        "  @bottom-center { content: \"WiNS Hub Agro · " + footer_label +
        " · pág. \" counter(page) \" de \" counter(pages);"
        "  font: 8pt 'DejaVu Sans', sans-serif; color: #8a978a; } }"
    )


def _render(footer_label: str, cover_title: str, cover_sub: str, body: str) -> bytes:
    html = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>'
        + _page_css(footer_label) + _BASE_CSS +
        '</style></head><body>'
        '<div class="cover"><div class="brand">WiNS Hub <span class="a">Agro</span></div>'
        f'<div class="doc-title">{cover_title}</div>'
        f'<div class="doc-sub">{cover_sub}</div></div>'
        f'<div class="wrap">{body}</div></body></html>'
    )
    return HTML(string=html).write_pdf()


# --- fichas anexas (pai/mãe) — reusam o payload de /api/touro e /api/matriz ---

# DEPs do touro na mesma ordem/rótulo do radar da ficha de tela, + extras se houver.
_DEP_TOURO = [
    ("iqg_genomico", "Índice geral (IQGg)"),
    ("dep_ps", "Crescimento — peso ao sobreano (PS)"),
    ("dep_gpd", "Ganho pós-desmama (GPD)"),
    ("dep_aol", "Carcaça — área de olho de lombo (AOL)"),
    ("dep_mar", "Marmoreio (MAR)"),
    ("dep_hp", "Fertilidade — stayability (HP)"),
    ("dep_pes", "Precocidade sexual (PES)"),
    ("dep_pn", "Peso ao nascer (PN)"),
    ("dep_pd", "Peso à desmama (PD)"),
    ("dep_egs", "Espessura de gordura subcutânea (EGS)"),
]


def _ficha_touro_html(t: dict) -> str:
    if not t or t.get("error"):
        return ""
    ofertas = t.get("ofertas") or []
    central = next((o.get("central") for o in ofertas if o.get("central")), None) or "—"
    dados = [
        ("IQGg genômico", _f(t.get("iqg_genomico"), 1)),
        ("Fazenda de origem", _esc(t.get("fazenda_origem") or "—")),
        ("Nascimento", _esc(t.get("data_nascimento") or "—")),
        ("Genotipado", "Sim" if t.get("genotipado") else "Não"),
        ("CEIP", "Sim" if t.get("ceip") else "Não"),
        ("Consanguinidade", f"{_num(t.get('consanguinidade')):.2f}%" if _num(t.get("consanguinidade")) is not None else "—"),
    ]
    kv = "".join(f"<tr><td class='k'>{k}</td><td class='v'>{v}</td></tr>" for k, v in dados)
    deps = "".join(
        f"<tr><td class='k'>{lbl}</td><td class='v'>{_f(t.get(col), 2)}</td></tr>"
        for col, lbl in _DEP_TOURO if _num(t.get(col)) is not None
    ) or "<tr><td class='k' colspan='2' style='color:#9aa39a'>Sem DEPs disponíveis na base.</td></tr>"

    if ofertas:
        orows = "".join(
            f"<tr><td class='l'>{o.get('central','—')}</td>"
            f"<td>{_brl(o.get('preco_dose_brl'))}</td>"
            f"<td>{_brl(o.get('preco_dose_sexado_m')) if _num(o.get('preco_dose_sexado_m')) else '—'}</td></tr>"
            for o in ofertas
        )
        ofertas_html = (
            "<h2>Ofertas comerciais</h2><div class='rule'></div>"
            "<table class='cmp'><thead><tr><th class='l'>Central</th>"
            "<th>Dose convencional</th><th>Dose sexada</th></tr></thead>"
            f"<tbody>{orows}</tbody></table>"
        )
    else:
        ofertas_html = ("<h2>Ofertas comerciais</h2><div class='rule'></div>"
                        "<div class='legend'>Sem oferta comercial cadastrada para este reprodutor "
                        "(catálogo da central não integrado).</div>")

    return f"""
    <div class="ficha">
      <div class="section-head">
        <div class="st">{_cattle_svg('#7fc77f', horns=True)} &nbsp;Ficha do Touro (pai)</div>
        <div class="ss">{_esc(t.get('nome','—'))} · {_esc(t.get('raca',''))} · Reg. {_esc(t.get('registro','—'))} · {_esc(central)}</div>
      </div>
      <div class="cols2">
        <div><div class="colh">Dados do reprodutor</div>
          <table class="kv">{kv}</table></div>
        <div><div class="colh">DEPs por característica</div>
          <table class="kv">{deps}</table></div>
      </div>
      {ofertas_html}
    </div>"""


def _ficha_matriz_html(m: dict) -> str:
    if not m or m.get("error"):
        return ""
    pai = _esc(m.get("pai_nome") or "—")
    if m.get("pai_registro"):
        pai += f" (Reg. {_esc(m.get('pai_registro'))})"
    dados = [
        ("Mérito materno (IQGg)", _f(m.get("merito_iqgg"), 2)),
        ("Pai (avô materno)", pai),
        ("Filhos touros", str(m.get("filhos_touros") if m.get("filhos_touros") is not None else "—")),
        ("Filhos avaliados", str(m.get("filhos_avaliados") if m.get("filhos_avaliados") is not None else "—")),
        ("IQGg médio dos filhos", _f(m.get("iqgg_medio_filhos"), 2)),
        ("Melhor filho (IQGg)", _f(m.get("iqgg_melhor_filho"), 2)),
        ("Fazenda de origem", _esc(m.get("fazenda_origem") or "—")),
    ]
    kv = "".join(f"<tr><td class='k'>{k}</td><td class='v'>{v}</td></tr>" for k, v in dados)
    filhos = m.get("filhos") or []
    if filhos:
        frows = "".join(
            f"<tr><td class='nome'>{_esc(f.get('nome','—'))}</td>"
            f"<td class='l'>{_esc(f.get('registro','—'))}</td>"
            f"<td class='cria'>{_f(f.get('iqgg'), 2)}</td></tr>"
            for f in filhos
        )
        prog = ("<table class='cmp'><thead><tr><th class='l'>Filho (touro)</th>"
                "<th class='l'>Registro</th><th>IQGg</th></tr></thead>"
                f"<tbody>{frows}</tbody></table>")
    else:
        prog = "<div class='legend'>Sem progênie avaliada cadastrada.</div>"

    return f"""
    <div class="ficha">
      <div class="section-head">
        <div class="st">{_cattle_svg('#e6c98a', horns=False)} &nbsp;Ficha da Matriz (mãe)</div>
        <div class="ss">{_esc(m.get('nome','—'))} · {_esc(m.get('raca_sigla',''))} · Reg. {_esc(m.get('registro','—'))} · ♀ matriz</div>
      </div>
      <h2>Mérito materno</h2><div class="rule"></div>
      <table class="kv">{kv}</table>
      <h2>Progênie — filhos touros</h2><div class="rule"></div>
      {prog}
    </div>"""


def _mon_section_html(mon: dict) -> str:
    """Seção 'Estratégia de monetização': 3 canais (dose/embrião/animal vivo) + racional."""
    if not mon:
        return ""
    rec = mon.get("recomendado")
    cards = ""
    for ch in mon.get("canais", []):
        is_rec = ch["tipo"] == rec
        badge = '<span class="badge">Recomendado</span>' if is_rec else ""
        if ch.get("status") == "ok" and ch["tipo"] == "dose":
            mv = f'<div class="mv">{_brl(ch.get("preco"))}<span class="u">/dose</span></div>'
            extra = []
            if ch.get("valor_cria") is not None:
                extra.append(f"+{_brl(ch['valor_cria'])}/cria")
            if ch.get("roi") is not None:
                extra.append(f"ROI {ch['roi']:.1f}×")
            " · ".join(extra) or ch.get("nota", "")
        else:
            mv = '<div class="mv nd">informar preço</div>'
            ch.get("nota", "")
        cards += (f'<div class="mon{" rec" if is_rec else ""}">'
                  f'<div class="mt">{ch["label"]}{badge}</div>{mv}</div>')
    return ('<div style="break-inside:avoid">'
            '<h2>Estratégia de monetização</h2><div class="rule"></div>'
            f'<div class="mon-row">{cards}</div>'
            f'<p class="mon-rac">{mon.get("racional","")}</p></div>')


# ===========================================================================
# Parecer de ACASALAMENTO (Touro × Vaca = Bezerro previsto)
# ===========================================================================
def gerar_parecer_cruzamento(cruz: dict, touro_ficha: dict = None, matriz_ficha: dict = None) -> bytes:
    touro = cruz.get("touro") or {}
    vaca = cruz.get("vaca") or {}
    calf = cruz.get("calf") or {}
    rel = cruz.get("relacao") or {}
    iqgg = calf.get("iqgg") or {}
    traits = calf.get("traits") or {}
    labels = calf.get("trait_labels") or {}
    f1 = " · F1" if cruz.get("f1") else ""

    sev = rel.get("severidade")
    if sev == "bloqueio":
        banner_cls, ico = "bn-block", "&#10006;"
        banner_txt = f"<b>Cruzamento bloqueado — {rel.get('label','')}.</b> Consanguinidade próxima; não recomendado."
    elif sev == "alerta":
        banner_cls, ico = "bn-warn", "&#9888;"
        banner_txt = f"<b>Atenção — {rel.get('label','')}.</b> Avaliar o grau de parentesco antes de acasalar."
    else:
        banner_cls, ico = "bn-ok", "&#10003;"
        banner_txt = f"<b>Acasalamento liberado.</b> {rel.get('label','Sem parentesco detectado')}."

    rows, seen = "", set()
    ordered = [("Índice geral (IQGg)", iqgg)] + [(labels.get(k, k), traits[k]) for k in traits]
    for lbl, t in ordered:
        if lbl in seen:
            continue
        seen.add(lbl)
        t = t or {}
        hl = ' class="hl"' if lbl.startswith("Índice geral") else ""
        rows += (
            f"<tr{hl}><td class='lbl'>{lbl}</td>"
            f"<td>{_f(t.get('touro'),2)}</td><td>{_f(t.get('vaca'),2)}</td>"
            f"<td class='cria'>{_f(t.get('cria'),2)}</td>"
            f"<td>{_delta(t.get('vs_touro'))}</td><td>{_delta(t.get('vs_vaca'))}</td></tr>"
        )

    chart = _calf_chart_svg(iqgg, traits, labels)
    mon_html = _mon_section_html(cruz.get("monetizacao"))
    ico_bull = _cattle_svg(VERDE_MEDIO, horns=True)
    ico_cow = _cattle_svg("#a9863f", horns=False)
    ico_calf = _cattle_svg(VERDE_ESCURO, horns=False)

    body = f"""
    <h2>Cruzamento</h2><div class="rule"></div>
    <table class="cross"><tr>
      <td style="width:30%"><div class="card c-bull">
        <div class="role">{ico_bull} Touro (pai)</div>
        <div class="nome">{_esc(touro.get('nome','—'))}</div>
        <div class="meta">{_esc(touro.get('raca_sigla',''))} · {_esc(touro.get('registro','—'))}</div>
        <div class="iq">IQGg {_f(touro.get('iqgg'))}</div></div></td>
      <td class="op">×</td>
      <td style="width:30%"><div class="card c-cow">
        <div class="role">{ico_cow} Vaca (mãe)</div>
        <div class="nome">{_esc(vaca.get('nome','—'))}</div>
        <div class="meta">{_esc(vaca.get('raca_sigla',''))} · {_esc(vaca.get('registro','—'))}</div>
        <div class="iq">IQGg {_f(vaca.get('iqgg'))}</div></div></td>
      <td class="op">=</td>
      <td style="width:32%"><div class="card c-calf">
        <div class="role">{ico_calf} Bezerro previsto</div>
        <div class="big">{_f(iqgg.get('cria'))}</div>
        <div class="meta">IQGg estimado · vs pai {_delta(iqgg.get('vs_touro'),1)} · vs mãe {_delta(iqgg.get('vs_vaca'),1)}</div>
      </div></td>
    </tr></table>
    <div class="banner {banner_cls}">{ico} &nbsp;{banner_txt}</div>
    <h2>Comparativo por característica</h2><div class="rule"></div>
    {chart}
    <p class="legend" style="text-align:center">Cada barra = % do maior valor entre pai/mãe/bezerro na característica. Ausência (—) = DEP não disponível na base.</p>
    <h2>Previsão por característica</h2><div class="rule"></div>
    <table class="cmp">
      <thead><tr><th>Característica</th><th>Touro (pai)</th><th>Vaca (mãe)</th>
        <th>Bezerro</th><th>vs pai</th><th>vs mãe</th></tr></thead>
      <tbody>{rows}</tbody></table>
    {mon_html}
    <div class="note">O bezerro previsto reflete o mérito médio dos pais (½ touro + ½ vaca) por característica.
      Valores ausentes (—) indicam DEP não disponível na base para o animal/característica.
      Parentesco avaliado pelo pedigree. Documento gerado automaticamente pela plataforma WiNS Hub Agro.</div>
    """
    body += _ficha_touro_html(touro_ficha) + _ficha_matriz_html(matriz_ficha)
    return _render("Parecer de acasalamento",
                   f"Parecer de Acasalamento{f1}",
                   f"Touro × Vaca = Bezerro previsto · Gerado em {datetime.now().strftime('%d/%m/%Y')}",
                   body)


# ===========================================================================
# Parecer ZOOTÉCNICO de MATCHING (recomendação de reprodutores)
# ===========================================================================
def gerar_parecer_matching(perfil: dict, touros: list) -> bytes:
    fin = perfil.get("finalidade", "") or ""
    fin_label = LABEL_FINALIDADE.get(fin, fin or "Não informada")
    prio_label = LABEL_PRIORIDADE.get(perfil.get("prioridade", "geral"), "Geral (IQGg)")
    uf_label = _esc(perfil.get("uf") or "Todos os estados")
    raca_label = _esc(perfil.get("raca_nome") or "Todas as raças")
    orc = _num(perfil.get("orcamento_max"))
    orc_label = f"R$ {orc:.0f}/dose" if orc else "Sem limite"
    semen_label = "Sexado" if perfil.get("sexado") else "Convencional"
    total = perfil.get("total", len(touros))
    is_leite = fin == "leite"
    ganho_label = "Valor agregado (R$/filha)" if is_leite else "Valor agregado (R$/cria)"
    unidade = "filha (por lactação)" if is_leite else "bezerro"

    def ganho_of(td):
        return _num(td.get("valor_filha") if is_leite else td.get("valor_bezerro"))

    # --- perfil em mini-cards ---
    pcards = [
        ("Finalidade", fin_label), ("Prioridade genética", prio_label),
        ("Estado (UF)", uf_label), ("Raça", raca_label),
        ("Orçamento máx.", orc_label), ("Tipo de sêmen", semen_label),
        ("Reprodutores elegíveis", str(total)),
    ]
    profile = "".join(
        f"<div class='pcard'><div class='pl'>{l}</div><div class='pv'>{v}</div></div>"
        for l, v in pcards
    )

    top10 = touros[:10]

    # --- nenhum resultado ---
    if not top10:
        body = (
            "<h2>Perfil do sistema de produção</h2><div class='rule'></div>"
            f"<div class='profile'>{profile}</div>"
            "<div class='banner bn-warn' style='margin-top:18px'>&#9888; &nbsp;<b>Nenhum reprodutor "
            "elegível</b> para este perfil. Recomenda-se afrouxar o orçamento, alterar a raça ou "
            "optar por sêmen convencional.</div>"
        )
        return _render("Parecer zootécnico", "Parecer Zootécnico",
                       f"Recomendação de reprodutores · Gerado em {datetime.now().strftime('%d/%m/%Y')}", body)

    # --- hero do #1 ---
    t1 = top10[0]
    nome1 = _esc(t1.get("nome") or "—")
    central1 = _esc(t1.get("central") or "central não informada")
    iqgg1, dep1 = _num(t1.get("iqgg")), _num(t1.get("dep_prioritaria"))
    preco1, ganho1, roi1 = _num(t1.get("preco_dose")), ganho_of(t1), _num(t1.get("roi_dose"))
    lucro1 = _num(t1.get("lucro_bezerro"))

    sv_ganho = f"+{_brl(ganho1)}" if ganho1 is not None else "n/d"
    cls_ganho = "" if ganho1 is not None else " nd"
    sv_roi = f"{roi1:.1f}×" if roi1 is not None else "n/d"
    cls_roi = "" if roi1 is not None else " nd"

    hero = f"""
    <div class="hero">
      <span class="rank">&#9733; #1 Recomendado</span>
      <div class="hn">{nome1}</div>
      <div class="hc">{central1} · {_esc(t1.get('raca',''))} · Reg. {_esc(t1.get('registro','—'))}</div>
      <div class="stat-row">
        <div class="stat"><div class="sl">IQGg</div><div class="sv">{_f(iqgg1,1)}</div></div>
        <div class="stat"><div class="sl">{ganho_label}</div><div class="sv{cls_ganho}">{sv_ganho}</div></div>
        <div class="stat"><div class="sl">ROI / dose</div><div class="sv{cls_roi}">{sv_roi}</div></div>
      </div>
    </div>
    """

    # frase de recomendação + justificativa de ROI
    rec = (f"O reprodutor de maior score para este perfil é <b>{nome1}</b> ({central1}), "
           f"com IQGg <b>{_f(iqgg1,1)}</b> e {prio_label.split(' (')[0].lower()} <b>{_f(dep1,1)}</b>.")
    if ganho1 is not None and preco1 and roi1 is not None:
        rec += (f" Cada dose de <b>{_brl(preco1)}</b> gera um {unidade} <b>+{_brl(ganho1)}</b> "
                f"mais valioso que a média da raça — retorno de <b>{roi1:.1f}×</b> sobre o custo da dose"
                + (f" (lucro líquido de <b>{_brl(lucro1)}</b> por cria)" if lucro1 is not None else "")
                + f". Num lote de 30 matrizes, são cerca de <b>{_brl(ganho1*30)}</b> de valor agregado "
                "na bezerrada — a genética superior se paga já na primeira safra.")
    elif ganho1 is not None:
        rec += (f" A cria projetada é <b>+{_brl(ganho1)}</b> mais valiosa que a média da raça. "
                "<b>ROI por dose não calculado:</b> catálogo comercial da central ainda não integrado "
                "(preço da dose indisponível).")

    # --- tabela Top 10 ---
    ganho_col = "+R$/filha" if is_leite else "+R$/cria"
    prio_label.split(" (")[0]
    sem_preco = True
    rows = ""
    for i, td in enumerate(top10, 1):
        nome = _esc(td.get("nome") or "—")
        central = _esc(td.get("central") or "—")
        iq = _num(td.get("iqgg")); dp = _num(td.get("dep_prioritaria"))
        pr = _num(td.get("preco_dose")); gh = ganho_of(td); ro = _num(td.get("roi_dose"))
        if pr:
            sem_preco = False
        cpr = f"{_brl(pr)}" if pr else "<span class='nd'>n/d</span>"
        cgh = f"+{_brl(gh)}" if gh is not None else "<span class='nd'>—</span>"
        cro = f"{ro:.1f}×" if ro is not None else "<span class='nd'>n/d</span>"
        top1 = " class='top1'" if i == 1 else ""
        rows += (
            f"<tr{top1}><td>{i}</td><td class='nome'>{nome}</td><td class='l'>{central}</td>"
            f"<td>{_f(iq,1)}</td><td>{_f(dp,1)}</td>"
            f"<td>{cpr}</td><td>{cgh}</td><td>{cro}</td></tr>"
        )

    legenda = (f"* DEP prioritária = {prio_label}."
               + (" &nbsp;·&nbsp; <b>n/d</b> = catálogo comercial da central não integrado "
                  "(preço e ROI indisponíveis para esta seleção)." if sem_preco
                  else " &nbsp;·&nbsp; <b>n/d</b> = preço/ROI não disponível para o touro."))

    analise = (
        f"<p class='analysis'>{rec}</p>"
        f"<p class='analysis' style='margin-top:8px'>O <b>score</b> combina o mérito genético total "
        f"(IQGg) com a DEP da prioridade escolhida ({prio_label.split(' (')[0].lower()}) e, quando há "
        f"catálogo integrado, a relação custo-benefício por dose. O <b>valor agregado</b> traduz a "
        f"superioridade genética em reais por {unidade}, frente à média da raça — é o que torna o "
        f"investimento na dose objetivamente justificável ao produtor.</p>"
    )

    body = f"""
    <h2>Perfil do sistema de produção</h2><div class="rule"></div>
    <div class="profile">{profile}</div>
    <h2>Reprodutor recomendado</h2><div class="rule"></div>
    {hero}
    <h2>Top {len(top10)} reprodutores</h2><div class="rule"></div>
    <table class="cmp">
      <thead><tr><th>#</th><th class="l">Touro</th><th class="l">Central</th>
        <th>IQGg</th><th>DEP*</th><th>R$/dose</th><th>{ganho_col}</th><th>ROI</th></tr></thead>
      <tbody>{rows}</tbody></table>
    <div class="legend">{legenda}</div>
    <h2>Análise e recomendações</h2><div class="rule"></div>
    {analise}
    <div class="note">Parecer gerado automaticamente pela plataforma <b>WiNS Hub Agro</b> com base no
      sumário <b>Geneplus (janeiro/2026)</b> e nos catálogos comerciais das centrais de IA parceiras.
      Foram avaliados {total} reprodutores elegíveis. Gerado em
      {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
    """
    return _render("Parecer zootécnico", "Parecer Zootécnico",
                   f"Recomendação de Reprodutores · {fin_label} · {uf_label} · Gerado em {datetime.now().strftime('%d/%m/%Y')}",
                   body)


# ---------------------------------------------------------------------------
# Relatório territorial executivo de um estado (panorama + alvos de prospecção).
# Migrado do ReportLab p/ o padrão WeasyPrint (mesma identidade dos pareceres).
# ---------------------------------------------------------------------------
UF_NOME = {
    "TO": "Tocantins", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "GO": "Goiás", "PA": "Pará", "MG": "Minas Gerais", "SP": "São Paulo",
    "BA": "Bahia", "RO": "Rondônia", "MA": "Maranhão", "PR": "Paraná",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "AC": "Acre",
    "AM": "Amazonas", "AP": "Amapá", "RR": "Roraima", "CE": "Ceará",
    "PE": "Pernambuco", "PI": "Piauí", "PB": "Paraíba", "RN": "Rio Grande do Norte",
    "AL": "Alagoas", "SE": "Sergipe", "ES": "Espírito Santo", "RJ": "Rio de Janeiro",
    "DF": "Distrito Federal",
}


def _int_fmt(v):
    """Inteiro com separador de milhar pt-BR (1234567 -> 1.234.567). None -> '—'."""
    v = _num(v)
    return f"{int(v):,}".replace(",", ".") if v is not None else "—"


def gerar_relatorio_territorial(uf: str, dados: dict) -> bytes:
    pan = dados.get("panorama") or {}
    prioritarios = dados.get("prioritarios") or []
    grupos = dados.get("grandes_grupos") or []
    uf_nome = UF_NOME.get(uf, uf)

    reb24 = _num(pan.get("rebanho_2024")) or 0
    reb20 = _num(pan.get("rebanho_2020")) or 0
    cresc = (100.0 * (reb24 - reb20) / reb20) if reb20 else None
    cresc_txt = ("—" if cresc is None
                 else (f"+{cresc:.0f}%" if cresc >= 0 else f"{cresc:.0f}%"))

    # --- hero: os 3 números que abrem a conversa comercial ---
    hero = f"""
    <div class="hero">
      <span class="rank">&#128205; {_esc(uf_nome)} ({_esc(uf)})</span>
      <div class="hn">Inteligência de Prospecção</div>
      <div class="hc">Onde a consultoria técnica entra primeiro: rebanho expressivo, suporte zero.</div>
      <div class="stat-row">
        <div class="stat"><div class="sl">Rebanho bovino (2024)</div><div class="sv">{_int_fmt(reb24)}</div></div>
        <div class="stat"><div class="sl">Crescimento 2020→2024</div><div class="sv">{cresc_txt}</div></div>
        <div class="stat"><div class="sl">Desertos Vet</div><div class="sv">{_int_fmt(pan.get('desertos_vet'))}</div></div>
      </div>
    </div>
    """

    # --- demais indicadores em mini-cards ---
    pcards = [
        ("Municípios analisados", _int_fmt(pan.get("municipios"))),
        ("Criadores de corte (CNPJ ativo)", _int_fmt(pan.get("criadores_corte"))),
        ("Criadores de leite (CNPJ ativo)", _int_fmt(pan.get("criadores_leite"))),
        ("Criadores com contato (tel./e-mail)", _int_fmt(pan.get("com_contato"))),
    ]
    profile = "".join(
        f"<div class='pcard'><div class='pl'>{l}</div><div class='pv'>{v}</div></div>"
        for l, v in pcards
    )

    # --- municípios prioritários (Desertos Vet por rebanho) ---
    if prioritarios:
        rows = ""
        for i, m in enumerate(prioritarios[:15], 1):
            top1 = " class='top1'" if i == 1 else ""
            rows += (
                f"<tr{top1}><td>{i}</td><td class='nome'>{_esc(m.get('municipio') or '—')}</td>"
                f"<td>{_int_fmt(m.get('bovinos'))}</td><td>{_int_fmt(m.get('cnpj_vet'))}</td></tr>"
            )
        prioritarios_html = f"""
        <h2>Municípios prioritários — onde a Mari entra primeiro</h2><div class="rule"></div>
        <p class="analysis">Desertos Vet ordenados por rebanho: maior gado, <b>zero suporte técnico</b>
          = maior potencial de consultoria e venda de genética.</p>
        <table class="cmp">
          <thead><tr><th>#</th><th class="l">Município</th><th>Rebanho (cab.)</th><th>Estab. Vet</th></tr></thead>
          <tbody>{rows}</tbody></table>
        """
    else:
        prioritarios_html = ""

    # --- grandes grupos (alvos B2B multi-fazenda) ---
    if grupos:
        grows = ""
        for g in grupos[:10]:
            grows += (f"<tr><td class='nome'>{_esc(g.get('socio') or '—')}</td>"
                      f"<td>{_int_fmt(g.get('fazendas'))}</td></tr>")
        grupos_html = f"""
        <h2>Grandes grupos — alvos B2B (sócios multi-fazenda)</h2><div class="rule"></div>
        <p class="analysis">Pessoas que controlam várias empresas rurais no estado: um negócio fecha
          muitas fazendas.</p>
        <table class="cmp">
          <thead><tr><th class="l">Sócio</th><th>Fazendas no estado</th></tr></thead>
          <tbody>{grows}</tbody></table>
        """
    else:
        grupos_html = ""

    estrategia = (
        f"O estado de <b>{_esc(uf_nome)}</b> reúne <b>{_int_fmt(reb24)} cabeças</b> e "
        f"<b>{_int_fmt(pan.get('desertos_vet'))} Desertos Vet</b> — municípios com rebanho expressivo e "
        "<b>zero suporte técnico veterinário</b>. É exatamente o vazio onde a consultoria técnica entra: "
        "a Mari atua como consultora nesses municípios, usa o <b>Motor de Matching</b> do WiNS Hub Agro "
        "para recomendar o reprodutor adequado ao perfil de cada fazenda, emite o <b>parecer zootécnico</b> "
        "e converte a recomendação em venda — sendo o canal de distribuição técnica nos mercados ainda "
        "não atendidos."
    )

    body = f"""
    <h2>Panorama da pecuária</h2><div class="rule"></div>
    {hero}
    <div class="profile">{profile}</div>
    {prioritarios_html}
    {grupos_html}
    <h2>Estratégia de atuação</h2><div class="rule"></div>
    <p class="analysis">{estrategia}</p>
    <div class="note">Relatório gerado automaticamente pela plataforma <b>WiNS Hub Agro</b>. Dados:
      IBGE/PPM (rebanho 2024), MapBiomas (pastagem), Receita Federal (CNPJ) e cobertura veterinária.
      Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
    """
    return _render("Relatório territorial", "Relatório Territorial",
                   f"{_esc(uf_nome)} ({_esc(uf)}) · Inteligência de Prospecção · "
                   f"Gerado em {datetime.now().strftime('%d/%m/%Y')}",
                   body)


# ---------------------------------------------------------------------------
# Cotação de sêmen / acasalamento — gerada da tela "Cruzar" do app de campo.
# Lista a matriz + o ranking de touros recomendados com preço de dose, p/ o
# produtor decidir e comprar. É o artefato comercial que vira PDF/WhatsApp.
# ---------------------------------------------------------------------------
def gerar_cotacao_acasalamento(matriz: dict, recomendacoes: list, cliente: dict = None,
                               prioridade_label: str = "Geral", n_doses: int = None) -> bytes:
    cliente = cliente or {}
    recs = recomendacoes or []
    vaca_nome = _esc(matriz.get("nome") or matriz.get("registro") or "Matriz")
    faz = _esc(cliente.get("razao_social") or matriz.get("fazenda_origem") or "—")
    local = _esc(" · ".join([x for x in [cliente.get("municipio") or matriz.get("municipio"),
                                         cliente.get("uf") or matriz.get("uf")] if x]) or "—")

    # perfil da matriz
    pcards = [
        ("Raça", _esc(matriz.get("raca") or matriz.get("raca_sigla") or "—")),
        ("Mérito materno (IQGg)", _f(matriz.get("iqgg"), 2)),
        ("Registro", _esc(matriz.get("registro") or "—")),
        ("Filhos no catálogo", str(matriz.get("n_filhos") if matriz.get("n_filhos") is not None else "—")),
        ("Critério da cotação", _esc(prioridade_label)),
    ]
    profile = "".join(f"<div class='pcard'><div class='pl'>{l}</div><div class='pv'>{v}</div></div>"
                      for l, v in pcards)

    # tabela de touros recomendados
    precos = [_num(r.get("preco_dose")) for r in recs if _num(r.get("preco_dose")) is not None]
    rows = ""
    for i, r in enumerate(recs):
        preco = _num(r.get("preco_dose"))
        cls = "top1" if i == 0 else ""
        parent = ("<span class='d-neg'>⚠ " + _esc(r.get("parentesco") or "parente") + "</span>") if r.get("parente") else "—"
        central = _esc(r.get("central") or "—")
        preco_txt = _brl(preco) if preco is not None else "<span class='nd'>sob consulta</span>"
        rows += (
            f"<tr class='{cls}'><td>{i+1}</td>"
            f"<td class='nome'>{_esc(r.get('nome') or '—')}</td>"
            f"<td>{_esc(r.get('raca_sigla') or '—')}</td>"
            f"<td class='l'>{central}</td>"
            f"<td class='cria'>{_f(r.get('prog_iqgg'), 2)}</td>"
            f"<td>{preco_txt}</td>"
            f"<td class='l'>{parent}</td></tr>"
        )

    # estimativa de investimento (melhor opção com preço × nº de doses)
    top_preco = _num(recs[0].get("preco_dose")) if recs else None
    invest_html = ""
    if n_doses and top_preco:
        total = top_preco * n_doses
        invest_html = (
            "<h2>Estimativa de investimento</h2><div class='rule'></div>"
            "<div class='stat-row'>"
            f"<div class='stat'><div class='sl'>Dose (1ª opção)</div><div class='sv'>{_brl(top_preco)}</div></div>"
            f"<div class='stat'><div class='sl'>Doses</div><div class='sv'>{n_doses}</div></div>"
            f"<div class='stat'><div class='sl'>Total estimado</div><div class='sv'>{_brl(total)}</div></div>"
            "</div>"
        )

    n_com_preco = len(precos)
    body = f"""
    <h2>Matriz</h2><div class="rule"></div>
    <div class="banner bn-ok"><b>{vaca_nome}</b> &nbsp;·&nbsp; {faz} &nbsp;·&nbsp; {local}</div>
    <div class="profile">{profile}</div>

    <h2>Touros recomendados ({len(recs)})</h2><div class="rule"></div>
    <table class="cmp">
      <thead><tr><th>#</th><th class="l">Touro</th><th>Raça</th><th class="l">Central</th>
        <th>IQGg da cria</th><th>R$/dose</th><th class="l">Parentesco</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="7" class="nd">Nenhum touro elegível encontrado.</td></tr>'}</tbody>
    </table>
    <div class="legend">Ordenado por mérito esperado da cria (IQGg midparent) + características priorizadas + preço.
      Preço público de dose disponível para {n_com_preco} de {len(recs)} touros (centrais integradas);
      demais saem sob consulta/cotação.</div>

    {invest_html}

    <div class="note">Cotação gerada pela plataforma <b>WiNS Hub Agro</b> a partir do acasalamento ao vivo
      da matriz <b>{vaca_nome}</b> contra o catálogo de reprodutores. Preços de dose conforme catálogos
      das centrais de IA integradas; valores sujeitos a confirmação no ato da compra.
      Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
    """
    return _render("Cotação de sêmen", "Cotação de Sêmen",
                   f"{vaca_nome} · {faz} · Gerado em {datetime.now().strftime('%d/%m/%Y')}",
                   body)


# ---------------------------------------------------------------------------
# Briefing de chegada — protocolo de recepção de um lote (entrada/compra).
# Gerado de uma movimentação tipo "entrada"; entrega à equipe de campo o que
# fazer quando o gado desembarca (quarentena, sanitário, pesagem, adaptação).
# ---------------------------------------------------------------------------
_PROTOCOLO_CHEGADA = [
    ("Descarregamento e descanso", "Água limpa à vontade + feno; 12–24 h de descanso antes de qualquer manejo."),
    ("Quarentena", "Lote isolado em piquete/curral separado por 21–30 dias antes de juntar ao rebanho."),
    ("Identificação", "Conferir/instalar brinco visual e SISBOV; bater contra a GTA e a nota de compra."),
    ("Pesagem de entrada", "Peso de chegada de cada animal — base do ganho e da conversão no período."),
    ("Vermifugação", "Endectocida/endoparasiticida de amplo espectro no embarque na propriedade."),
    ("Vacinação de chegada", "Clostridioses e respiratórias conforme o calendário; agendar reforços."),
    ("Exames sanitários", "Brucelose/tuberculose quando exigido p/ trânsito/SISBOV ou origem desconhecida."),
    ("Adaptação alimentar", "Transição gradual de dieta por 7–10 dias para evitar distúrbio digestivo."),
    ("Observação clínica", "Vistoria diária na quarentena: diarreia, sinal respiratório, claudicação, apetite."),
]


def gerar_briefing_chegada(mov: dict, cliente: dict = None) -> bytes:
    cliente = cliente or {}
    faz = _esc(cliente.get("razao_social") or "—")
    local = _esc(" · ".join([x for x in [cliente.get("municipio"), cliente.get("uf")] if x]) or "—")
    data = mov.get("data_evento")
    data = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else (str(data) if data else "—")
    qtd = mov.get("quantidade")

    dados = [
        ("Nº da GTA", mov.get("gta_numero") or "—"),
        ("Origem", mov.get("origem") or "—"),
        ("Finalidade", mov.get("finalidade") or "—"),
        ("Quantidade", f"{qtd} cabeça(s)" if qtd else "—"),
        ("Data de chegada", data),
    ]
    # k é rótulo fixo; v vem do usuário (GTA/origem/finalidade) -> escapa
    kv = "".join(f"<tr><td class='k'>{k}</td><td class='v'>{_esc(v)}</td></tr>" for k, v in dados)

    passos = "".join(
        f"<tr><td style='width:26px; text-align:center; font-size:13pt; color:#2d5a2d'>&#9744;</td>"
        f"<td><b>{t}</b><div style='font-size:9pt; color:#5a6b5a; margin-top:1px'>{d}</div></td></tr>"
        for t, d in _PROTOCOLO_CHEGADA
    )

    obs_html = ""
    if mov.get("obs"):
        obs_html = f"<div class='banner bn-warn'><b>Observação do lote:</b> {_esc(mov.get('obs'))}</div>"

    body = f"""
    <h2>Lote recebido</h2><div class="rule"></div>
    <div class="banner bn-ok"><b>{faz}</b> &nbsp;·&nbsp; {local}</div>
    <table class="kv" style="margin-top:10px">{kv}</table>
    {obs_html}

    <h2>Protocolo de chegada</h2><div class="rule"></div>
    <table class="kv" style="font-size:10pt">{passos}</table>
    <div class="legend">Marque cada etapa à medida que executa. Protocolo de referência —
      ajuste ao calendário sanitário e às exigências de defesa agropecuária da sua região.</div>

    <div class="note">Briefing gerado pela plataforma <b>WiNS Hub Agro</b> para o lote da movimentação
      registrada em {data}. Documento operacional de recepção — não substitui o atestado sanitário
      nem a GTA oficial.</div>
    """
    return _render("Briefing de chegada", "Briefing de Chegada",
                   f"{faz} · {qtd or '—'} cab. · Chegada {data}",
                   body)


# ===========================================================================
# Feature 5 — Proposta do simulador (artefato que a Mari deixa com o produtor)
# ===========================================================================
def gerar_proposta_simulador(d: dict) -> bytes:
    """Proposta comercial de 1 página a partir da simulação de retorno. `d` traz os
    números já calculados no backend (mesma fórmula do simulador/App)."""
    def _i(v):
        return f"{int(round(v)):,}".replace(",", ".") if v is not None else "—"
    touro = _esc(d.get("touro_nome") or "—")
    raca = _esc(d.get("raca") or "")
    equil = d.get("equilibrio")
    prenhez_esp = d.get("prenhez_esperada")
    body = f"""
      <h2>Proposta de retorno — Genética Monte Sião</h2><div class="rule"></div>
      <div class="hero">
        <span class="rank">Ganho estimado por safra</span>
        <div class="hn">+R$ {_i(d.get('ganho_genetico_safra'))}</div>
        <div class="hc">com <b>{_i(d.get('matrizes'))}</b> matrizes usando <b>{touro}</b> ·
            <b>{_i(d.get('bezerros_adicionais'))}</b> bezerros a mais por safra</div>
        <div class="stat-row">
          <div class="stat"><div class="sl">Bezerros a mais/safra</div><div class="sv">{_i(d.get('bezerros_adicionais'))}</div></div>
          <div class="stat"><div class="sl">Ganho genético/cria</div><div class="sv">+R$ {_i(d.get('ganho_cria'))}</div></div>
          <div class="stat"><div class="sl">Bezerros/safra</div><div class="sv">{_i(d.get('total_bezerros'))}</div></div>
          <div class="stat"><div class="sl">A dose se paga em</div><div class="sv">{(str(equil) + ' crias') if equil else '—'}</div></div>
        </div>
      </div>
      <h2>Premissas da simulação</h2><div class="rule"></div>
      <div class="profile">
        <div class="pcard"><div class="pl">Touro Monte Sião</div><div class="pv">{touro}{(' (' + raca + ')') if raca else ''}</div></div>
        <div class="pcard"><div class="pl">Matrizes</div><div class="pv">{_i(d.get('matrizes'))}</div></div>
        <div class="pcard"><div class="pl">Prenhez atual</div><div class="pv">{_i(d.get('prenhez_atual'))}%</div></div>
        <div class="pcard"><div class="pl">Prenhez esperada</div><div class="pv">{('~' + str(prenhez_esp) + '%') if prenhez_esp else '—'}</div></div>
        <div class="pcard"><div class="pl">Preço da arroba (@)</div><div class="pv">R$ {_i(d.get('arroba'))}</div></div>
        <div class="pcard"><div class="pl">Preço da dose</div><div class="pv">{('R$ ' + _i(d.get('preco_dose'))) if d.get('preco_dose') else '—'}</div></div>
      </div>
      <div class="note">O <b>ganho genético por cria</b> é o quanto o touro agrega por bezerro vs. um touro médio
        da raça (DEP de peso à desmama × arroba ÷ 30). A <b>taxa de prenhez</b> é estimativa (proxy de perímetro
        escrotal). Valores são estimativas para orientar a decisão — resultados reais variam com manejo, nutrição
        e sanidade.{(' Gerado em ' + _esc(d.get('data_str')) + '.') if d.get('data_str') else ''}</div>
    """
    return _render("Proposta · Simulador", "Proposta de Retorno",
                   "Genética Monte Sião · WiNS Hub Agro", body)


# --- Dossiê da Fazenda (ficha completa) — payload de /api/farm/{cnpj} ---
def gerar_dossie_fazenda(data: dict) -> bytes:
    f = data.get("fazenda") or {}
    tec = data.get("tecnicos") or {}
    gen = data.get("genetica") or {}
    linha_prod = data.get("linha_producao") or "—"
    porte = data.get("porte_estimado") or "—"
    nome = _esc((f.get("nome_fazenda") or f.get("razao") or "Fazenda")).split(" (")[0]

    def linha(rotulo, valor, extra=""):
        return (f'<tr><td style="color:#6b7a6b;font-size:9pt;width:38%">{_esc(rotulo)}</td>'
                f'<td style="font-weight:600;color:#1a3a1a">{valor or "—"}{extra}</td></tr>')

    def contatos(d):
        out = []
        if d.get("whatsapp"): out.append(f'WhatsApp: {_esc(d["whatsapp"])}')
        if d.get("email"): out.append(f'E-mail: {_esc(d["email"])}')
        if d.get("instagram"): out.append(f'@{_esc(d["instagram"])}')
        if d.get("telefone_rfb") and not d.get("whatsapp"): out.append(f'Tel: {_esc(d["telefone_rfb"])}')
        return " · ".join(out) or "sem canal"

    def bloco(titulo, inner):
        return (f'<div style="border:1px solid #e0e8e0;border-radius:10px;padding:12px 14px;margin-bottom:12px">'
                f'<div style="color:{VERDE_MEDIO};font-weight:800;font-size:10.5pt;text-transform:uppercase;'
                f'letter-spacing:.4px;border-bottom:2px solid #eef2ee;padding-bottom:6px;margin-bottom:9px">{titulo}</div>{inner}</div>')

    # BLOCO 1
    b1 = ('<table style="width:100%;border-collapse:collapse">'
          + linha("Nome / Razão social", _esc(f.get("razao") or nome))
          + linha("CNPJ", _esc(f.get("cnpj_completo")))
          + linha("Município / UF", f'{_esc(f.get("municipio"))} / {_esc(f.get("uf"))}')
          + linha("Porte (capital social)", (f'R$ {f.get("capital_mi")} M' if f.get("capital_mi") else "—"))
          + linha("Dono / Decisor", _esc((f.get("decisor") or "—")))
          + linha("Operador / Admin", _esc(f.get("operador_jovem") or "—"))
          + linha("Contato da fazenda", _esc(contatos(f)))
          + linha("Canal recomendado", _esc(f.get("canal_recomendado")))
          + '</table>')

    # BLOCO 2
    rows2 = ""
    for t in (tec.get("vinculados") or []):
        rows2 += (f'<tr><td style="font-weight:600">{_esc(t.get("nome"))}</td>'
                  f'<td style="color:{VERDE_MEDIO};font-size:8.5pt">VINCULADO (sócio-técnico)</td>'
                  f'<td>{("CRMV "+_esc(t.get("crmv"))) if t.get("crmv") else ""}</td>'
                  f'<td>{_esc(t.get("contato") or "")}</td></tr>')
    for t in (tec.get("regiao") or []):
        rows2 += (f'<tr><td style="font-weight:600">{_esc(t.get("nome"))}</td>'
                  f'<td style="color:#a07a00;font-size:8.5pt">SUGESTÃO · na região</td>'
                  f'<td>{("CRMV "+_esc(t.get("crmv"))) if t.get("crmv") else ""}</td>'
                  f'<td>{_esc(t.get("contato") or t.get("email") or "")}</td></tr>')
    b2 = (f'<table style="width:100%;border-collapse:collapse;font-size:9.5pt">{rows2}</table>'
          if rows2 else '<div style="color:#9aa39a">Nenhum técnico mapeado para esta fazenda nem no município.</div>')

    # BLOCO 3
    if gen.get("sinal"):
        apt = {}
        for x in (gen.get("por_aptidao") or []): apt[x["aptidao"]] = apt.get(x["aptidao"], 0) + x["n"]
        racas_m = ", ".join(sorted({x["raca"] for x in (gen.get("por_aptidao") or []) if x["sexo"] == "M"}))
        racas_f = ", ".join(sorted({x["raca"] for x in (gen.get("por_aptidao") or []) if x["sexo"] == "F"}))
        b3 = (f'<div style="margin-bottom:8px">Sinal genético: <b>{_esc(gen.get("sinal"))}</b> '
              f'<span style="color:#8a948a;font-size:8.5pt">· por correspondência de nome ({_esc(gen.get("match_fazenda"))}), não posse confirmada</span></div>'
              '<table style="width:100%;border-collapse:collapse">'
              + linha("🐂 Touros", f'<b>{gen.get("touros",0)}</b>', f' <span style="color:#6b7a6b;font-size:8.5pt">{_esc(racas_m)}</span>')
              + linha("🐄 Vacas / Matrizes", f'<b>{gen.get("matrizes",0)}</b>', f' <span style="color:#6b7a6b;font-size:8.5pt">{_esc(racas_f)}</span>')
              + (linha("💧 Sêmen à venda", f'{len(gen.get("semen") or [])} touros com oferta') if gen.get("semen") else "")
              + linha("Aptidão", _esc(" · ".join(f"{k}: {v}" for k, v in apt.items())))
              + '</table>')
    else:
        b3 = '<div style="color:#9aa39a">Sinal genético não mapeado para esta fazenda.</div>'

    of = data.get("oferta") or {}
    rows4 = ""
    for t in (of.get("touros") or []):
        rows4 += (f'<tr><td style="font-weight:600">{_esc(t.get("nome"))}</td><td>{_esc(t.get("raca"))}</td>'
                  f'<td style="color:{VERDE_MEDIO}">{_esc(t.get("indice_tipo"))} {_f(t.get("indice"),1)}</td>'
                  f'<td>{_brl(t.get("preco_dose"))}/dose · {_esc(t.get("central"))}</td></tr>')
    b4 = ((f'<div style="font-size:9pt;color:#6b7a6b;margin-bottom:6px">Recomendação para a linha <b>{_esc(linha_prod)}</b> ({_esc(of.get("tipo"))}):</div>'
           f'<table style="width:100%;border-collapse:collapse;font-size:9.5pt">{rows4}</table>')
          if rows4 else '<div style="color:#9aa39a">Sem oferta vendável catalogada para esta linha.</div>')
    head = (f'<div style="margin:-4px 0 10px;font-size:9.5pt;color:#283428"><b>Linha de produção:</b> {_esc(linha_prod)} '
            f'&nbsp;·&nbsp; <b>Porte estimado:</b> {_esc(porte)} '
            f'<span style="color:#8a948a;font-size:8pt">(estimativa por cruzamento, não headcount)</span></div>')
    body = head + bloco("Fazenda", b1) + bloco("Técnicos", b2) + bloco("Genética", b3) + bloco("O que oferecer", b4)
    sub = f'{_esc(f.get("municipio"))}/{_esc(f.get("uf"))} · {_esc(f.get("cnpj_completo"))} · {datetime.now().strftime("%d/%m/%Y")}'
    return _render("Dossiê da Fazenda", nome, sub, body)
