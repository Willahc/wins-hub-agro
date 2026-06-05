from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io

VERDE_ESCURO = colors.HexColor('#1a3a1a')
VERDE_MEDIO = colors.HexColor('#2d5a2d')
VERDE_CLARO = colors.HexColor('#4a9e4a')
BRANCO = colors.white
CINZA = colors.HexColor('#f5f7f5')

LABEL_FINALIDADE = {
    "corte": "Corte", "leite": "Leite", "dupla": "Dupla Aptidão"
}
LABEL_PRIORIDADE = {
    "crescimento": "Crescimento (GPD)",
    "carcaca": "Carcaça (AOL)",
    "precocidade": "Precocidade Sexual (PES)",
    "fertilidade": "Fertilidade (HP/Stayability)",
    "marmoreio": "Marmoreio (MAR)",
    "geral": "Geral (IQGg)"
}


def _num(v):
    """Coerce possibly-None / Decimal / str values to float, else None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def gerar_parecer_pdf(perfil: dict, touros: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()
    story = []

    # --- CAPA ---
    style_titulo = ParagraphStyle('titulo',
        fontSize=28, textColor=BRANCO,
        alignment=TA_CENTER, fontName='Helvetica-Bold',
        spaceAfter=8)
    style_sub = ParagraphStyle('sub',
        fontSize=14, textColor=VERDE_MEDIO,
        alignment=TA_CENTER, fontName='Helvetica',
        spaceAfter=6)
    style_data = ParagraphStyle('data',
        fontSize=11, textColor=colors.black,
        alignment=TA_CENTER, fontName='Helvetica')

    # Fundo capa via Table (faixa verde com o título)
    capa_data = [[Paragraph("WiNS Hub Agro", style_titulo)]]
    capa = Table(capa_data, colWidths=[17 * cm])
    capa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), VERDE_ESCURO),
        ('TOPPADDING', (0, 0), (-1, -1), 80),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(Spacer(1, 3 * cm))
    story.append(capa)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("PARECER ZOOTÉCNICO", style_sub))
    story.append(Paragraph("Recomendação de Reprodutores Bovinos", style_sub))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        f"Data: {datetime.now().strftime('%d/%m/%Y')} &middot; Gerado por: WiNS Hub Agro",
        style_data
    ))
    story.append(PageBreak())

    # --- PERFIL ---
    style_h2 = ParagraphStyle('h2',
        fontSize=14, textColor=VERDE_ESCURO,
        fontName='Helvetica-Bold', spaceAfter=12)
    style_body = ParagraphStyle('body',
        fontSize=10, textColor=colors.black,
        fontName='Helvetica', spaceAfter=6, leading=15)

    story.append(Paragraph("PERFIL DO SISTEMA DE PRODUÇÃO", style_h2))
    story.append(HRFlowable(width="100%", color=VERDE_CLARO))
    story.append(Spacer(1, 0.3 * cm))

    uf_label = perfil.get('uf') or 'Todos os estados'
    raca_label = perfil.get('raca_nome') or 'Todas as raças'
    orcamento = _num(perfil.get('orcamento_max'))
    orcamento_label = f"R$ {orcamento:.2f}/dose" if orcamento else 'Sem limite'
    sexado_label = "Sexado" if perfil.get('sexado') else "Convencional"

    perfil_data = [
        ["Finalidade", LABEL_FINALIDADE.get(perfil.get('finalidade', ''), perfil.get('finalidade', 'Não informada'))],
        ["Estado (UF)", uf_label],
        ["Raça", raca_label],
        ["Prioridade Genética", LABEL_PRIORIDADE.get(perfil.get('prioridade', 'geral'), 'Geral')],
        ["Orçamento máximo", orcamento_label],
        ["Tipo de sêmen", sexado_label],
        ["Reprodutores encontrados", str(perfil.get('total', len(touros)))],
    ]

    t = Table(perfil_data, colWidths=[6 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [CINZA, BRANCO]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(PageBreak())

    # --- TABELA TOUROS ---
    story.append(Paragraph(f"TOUROS RECOMENDADOS — Top {min(10, len(touros))}", style_h2))
    story.append(HRFlowable(width="100%", color=VERDE_CLARO))
    story.append(Spacer(1, 0.3 * cm))

    top10 = touros[:10]
    header = ["#", "Touro", "Central", "Score", "IQGg", "DEP", "R$/dose"]
    rows = [header]
    for i, td in enumerate(top10, 1):
        nome_raw = td.get('nome') or '—'
        nome = (nome_raw[:20] + "…") if len(nome_raw) > 20 else nome_raw
        central = (td.get('central') or '—')[:12]
        preco = _num(td.get('preco_dose'))
        iqgg = _num(td.get('iqgg'))
        dep = _num(td.get('dep_prioritaria'))
        score = _num(td.get('score'))
        rows.append([
            str(i), nome, central,
            f"{score:.3f}" if score is not None else "—",
            f"{iqgg:.1f}" if iqgg is not None else "—",
            f"{dep:.1f}" if dep is not None else "—",
            f"R${preco:.0f}" if preco else "—",
        ])

    col_widths = [1 * cm, 5 * cm, 3.5 * cm, 2 * cm, 2 * cm, 2 * cm, 2.5 * cm]
    tabela = Table(rows, colWidths=col_widths)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERDE_ESCURO),
        ('TEXTCOLOR', (0, 0), (-1, 0), BRANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CINZA, BRANCO]),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ]))
    story.append(tabela)
    story.append(PageBreak())

    # --- ANÁLISE NARRATIVA ---
    story.append(Paragraph("ANÁLISE E RECOMENDAÇÕES", style_h2))
    story.append(HRFlowable(width="100%", color=VERDE_CLARO))
    story.append(Spacer(1, 0.3 * cm))

    prioridade_label = LABEL_PRIORIDADE.get(perfil.get('prioridade', 'geral'), 'Geral')
    total = perfil.get('total', len(touros))
    uf_txt = f"no estado de {uf_label}" if perfil.get('uf') else "em todos os estados"
    orc_txt = f"com orçamento até {orcamento_label}" if orcamento else "sem restrição de orçamento"

    if not top10:
        vazio = (
            f"Para o perfil informado ({orc_txt}, {uf_txt}, prioridade {prioridade_label.lower()}), "
            "<b>nenhum reprodutor elegível</b> foi encontrado no banco de dados WiNS Hub Agro. "
            "Recomenda-se afrouxar o orçamento, alterar a raça ou optar por sêmen convencional."
        )
        story.append(Paragraph(vazio, style_body))
    else:
        intro = (
            f"Com base no perfil informado (finalidade {LABEL_FINALIDADE.get(perfil.get('finalidade', ''), 'não informada').lower()}, "
            f"prioridade {prioridade_label.lower()}, {orc_txt}, {uf_txt}), "
            f"foram identificados <b>{total} reprodutores elegíveis</b> no banco de dados WiNS Hub Agro."
        )
        story.append(Paragraph(intro, style_body))
        story.append(Spacer(1, 0.4 * cm))

        t1 = top10[0]
        t1_nome = t1.get('nome') or '—'
        t1_central = t1.get('central') or '—'
        t1_iqgg_n = _num(t1.get('iqgg'))
        t1_dep_n = _num(t1.get('dep_prioritaria'))
        t1_preco_n = _num(t1.get('preco_dose'))
        t1_iqgg = f"{t1_iqgg_n:.1f}" if t1_iqgg_n is not None else "—"
        t1_dep = f"{t1_dep_n:.1f}" if t1_dep_n is not None else "—"
        t1_preco = f"R${t1_preco_n:.0f}" if t1_preco_n else "—"
        sexo_txt = "sexado" if perfil.get('sexado') else "convencional"
        t1_rpiqgg = (
            f"R${(t1_preco_n / t1_iqgg_n):.2f}/IQGg"
            if (t1_preco_n and t1_iqgg_n) else ""
        )

        destaque = (
            f"O touro de maior score foi <b>{t1_nome}</b> ({t1_central}), com IQGg {t1_iqgg} "
            f"e {prioridade_label} {t1_dep}, a {t1_preco}/dose {sexo_txt}"
            f"{f' — relação custo-benefício de {t1_rpiqgg}, entre as melhores do catálogo nacional' if t1_rpiqgg else ''}."
        )
        story.append(Paragraph(destaque, style_body))

    story.append(Spacer(1, 0.6 * cm))
    rodape_txt = (
        "Este parecer foi gerado automaticamente pela plataforma <b>WiNS Hub Agro</b> "
        "com base nos dados do sumário Geneplus (janeiro/2026) e catálogos comerciais "
        f"das centrais de IA parceiras. Data de geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}."
    )
    story.append(Paragraph(rodape_txt, style_body))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


UF_NOME = {
    "TO": "Tocantins", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "GO": "Goiás", "PA": "Pará", "MG": "Minas Gerais", "SP": "São Paulo",
    "BA": "Bahia", "RO": "Rondônia", "MA": "Maranhão", "GO": "Goiás",
}


def gerar_relatorio_territorial(uf: str, dados: dict) -> bytes:
    """Relatório territorial executivo de um estado (panorama + alvos de prospecção)."""
    pan = dados.get("panorama") or {}
    prioritarios = dados.get("prioritarios") or []
    grupos = dados.get("grandes_grupos") or []
    uf_nome = UF_NOME.get(uf, uf)

    def _i(v):
        return _num(v) or 0

    reb24 = _i(pan.get("rebanho_2024"))
    reb20 = _i(pan.get("rebanho_2020"))
    cresc = (100.0 * (reb24 - reb20) / reb20) if reb20 else 0
    n_fmt = lambda v: f"{int(_i(v)):,}".replace(",", ".")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    st_titulo = ParagraphStyle('t', fontSize=26, textColor=BRANCO, alignment=TA_CENTER,
                               fontName='Helvetica-Bold', spaceAfter=8)
    st_sub = ParagraphStyle('s', fontSize=15, textColor=VERDE_MEDIO, alignment=TA_CENTER,
                            fontName='Helvetica', spaceAfter=6)
    st_data = ParagraphStyle('d', fontSize=11, textColor=colors.black, alignment=TA_CENTER,
                             fontName='Helvetica')
    st_h2 = ParagraphStyle('h2', fontSize=14, textColor=VERDE_ESCURO,
                           fontName='Helvetica-Bold', spaceAfter=10)
    st_body = ParagraphStyle('b', fontSize=10, textColor=colors.black, fontName='Helvetica',
                             spaceAfter=6, leading=15)

    # --- CAPA ---
    capa = Table([[Paragraph("WiNS Hub Agro", st_titulo)]], colWidths=[17 * cm])
    capa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), VERDE_ESCURO),
        ('TOPPADDING', (0, 0), (-1, -1), 70), ('BOTTOMPADDING', (0, 0), (-1, -1), 18),
    ]))
    story += [Spacer(1, 3 * cm), capa, Spacer(1, 0.5 * cm),
              Paragraph("RELATÓRIO TERRITORIAL", st_sub),
              Paragraph(f"{uf_nome} ({uf}) — Inteligência de Prospecção", st_sub),
              Spacer(1, 1 * cm),
              Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y')} &middot; "
                        "Base IBGE/PPM 2024, MapBiomas, CNPJ e cobertura veterinária", st_data),
              PageBreak()]

    # --- PANORAMA ---
    story += [Paragraph(f"PANORAMA DA PECUÁRIA — {uf_nome}", st_h2),
              HRFlowable(width="100%", color=VERDE_CLARO), Spacer(1, 0.3 * cm)]
    cresc_txt = f"+{cresc:.0f}%" if cresc >= 0 else f"{cresc:.0f}%"
    pan_data = [
        ["Rebanho bovino (2024)", f"{n_fmt(reb24)} cabeças"],
        ["Crescimento do rebanho (2020→2024)", cresc_txt],
        ["Municípios analisados", n_fmt(pan.get("municipios"))],
        ["Desertos Vet (rebanho alto, sem suporte técnico)", n_fmt(pan.get("desertos_vet"))],
        ["Criadores de corte (CNPJ ativo)", n_fmt(pan.get("criadores_corte"))],
        ["Criadores de leite (CNPJ ativo)", n_fmt(pan.get("criadores_leite"))],
        ["Criadores com contato (tel./e-mail)", n_fmt(pan.get("com_contato"))],
    ]
    t = Table(pan_data, colWidths=[10 * cm, 7 * cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [CINZA, BRANCO]),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story += [t, Spacer(1, 0.6 * cm)]

    # --- MUNICÍPIOS PRIORITÁRIOS ---
    story += [Paragraph("MUNICÍPIOS PRIORITÁRIOS — onde a Mari entra primeiro", st_h2),
              HRFlowable(width="100%", color=VERDE_CLARO), Spacer(1, 0.2 * cm),
              Paragraph("Desertos Vet ordenados por rebanho: maior gado, <b>zero suporte "
                        "técnico</b> = maior potencial de consultoria e venda de genética.", st_body),
              Spacer(1, 0.2 * cm)]
    rows = [["#", "Município", "Rebanho (cab.)", "Estab. Vet"]]
    for i, m in enumerate(prioritarios[:15], 1):
        rows.append([str(i), (m.get("municipio") or "—")[:28],
                     n_fmt(m.get("bovinos")), n_fmt(m.get("cnpj_vet"))])
    tp = Table(rows, colWidths=[1 * cm, 8 * cm, 4.5 * cm, 3.5 * cm])
    tp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERDE_ESCURO), ('TEXTCOLOR', (0, 0), (-1, 0), BRANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CINZA, BRANCO]),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
    ]))
    story += [tp, PageBreak()]

    # --- GRANDES GRUPOS ---
    if grupos:
        story += [Paragraph("GRANDES GRUPOS — alvos B2B (sócios multi-fazenda)", st_h2),
                  HRFlowable(width="100%", color=VERDE_CLARO), Spacer(1, 0.2 * cm),
                  Paragraph("Pessoas que controlam várias empresas rurais no estado: um "
                            "negócio fecha muitas fazendas.", st_body), Spacer(1, 0.2 * cm)]
        gr = [["Sócio", "Fazendas no estado"]]
        for g in grupos[:10]:
            gr.append([(g.get("socio") or "—")[:45], n_fmt(g.get("fazendas"))])
        tg = Table(gr, colWidths=[12 * cm, 5 * cm])
        tg.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), VERDE_ESCURO), ('TEXTCOLOR', (0, 0), (-1, 0), BRANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CINZA, BRANCO]),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ]))
        story += [tg, Spacer(1, 0.6 * cm)]

    # --- ESTRATÉGIA ---
    story += [Paragraph("ESTRATÉGIA DE ATUAÇÃO", st_h2),
              HRFlowable(width="100%", color=VERDE_CLARO), Spacer(1, 0.3 * cm),
              Paragraph(
                  f"O estado de <b>{uf_nome}</b> reúne <b>{n_fmt(reb24)} cabeças</b> e "
                  f"<b>{n_fmt(pan.get('desertos_vet'))} Desertos Vet</b> — municípios com rebanho "
                  "expressivo e <b>zero suporte técnico veterinário</b>. É exatamente o vazio onde "
                  "a consultoria técnica entra: a Mari atua como consultora nesses municípios, usa o "
                  "<b>Motor de Matching</b> do WiNS Hub Agro para recomendar o reprodutor adequado ao "
                  "perfil de cada fazenda, emite o <b>parecer zootécnico</b> e converte a recomendação "
                  "em venda — sendo o canal de distribuição técnica nos mercados ainda não atendidos.",
                  st_body),
              Spacer(1, 0.5 * cm),
              Paragraph("Relatório gerado automaticamente pela plataforma <b>WiNS Hub Agro</b>. "
                        "Dados: IBGE/PPM (rebanho 2024), MapBiomas (pastagem), Receita Federal (CNPJ) "
                        f"e cobertura veterinária. {datetime.now().strftime('%d/%m/%Y %H:%M')}.", st_body)]

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
