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
