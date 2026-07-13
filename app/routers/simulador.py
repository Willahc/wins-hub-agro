"""Router: Simulador público (Feature 5) — Mari abre na fazenda; sem login; ZERO PII.

Primeiro router extraído do monolito (Fase 2 da modularização). É o mais isolado:
público (o middleware libera /api/simulador/*), sem PII e só leitura. Importa os
helpers de negócio do `main` (constantes genéticas, _prenhez_est, _error, templates)
e a camada de dados do `db`. O `app.include_router` em main.py roda DEPOIS que esses
nomes já existem, então o import circular se resolve pela ordem.
"""
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from datetime import datetime
import math

import external_apis
from db import query
from pdf_html import gerar_proposta_simulador
from main import (
    templates, _error, _prenhez_est, get_current_user, APP_VERSION,
    PD_ID, PES_ID, IQGG_ID, MONTE_SIAO_CENTRAL_ID,
)

router = APIRouter()


@router.get("/simulador", response_class=HTMLResponse)
def simulador_page(request: Request):
    return templates.TemplateResponse("simulador.html", {"request": request})


@router.get("/pasto-limpo", response_class=HTMLResponse)
def pasto_limpo_page(request: Request):
    """Simulador de ROI 'Pasto Limpo' (herbicida -> recuperacao de lotacao). Ferramenta de
    venda baseada em valor (payback/ROI), calculo no cliente e ZERO PII.

    Usuarios autenticados recebem o shell do Hub. Sem sessao, a mesma URL continua
    publica e independente para preservar links compartilhados com produtores.
    """
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse("pasto_limpo_public.html", {"request": request})
    response = templates.TemplateResponse("pasto_limpo.html", {
        "request": request, "user": user, "active": "pasto_limpo", "app_version": APP_VERSION,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/api/simulador/touros")
def simulador_touros():
    """Catálogo público p/ o simulador: SÓ os touros do Monte Sião com preço de dose
    (é ferramenta de venda DELES, não comparador de mercado). DEP de peso (ganho/cria) +
    prenhez estimada. Sem PII — só genética + preço. O cálculo financeiro é feito no cliente."""
    try:
        rows = query(
            f"""
            SELECT r.id, r.nome, ra.sigla AS raca_sigla,
                   MAX(a.valor) FILTER (WHERE a.caracteristica_id = {PD_ID})   AS pd,
                   MAX(a.valor) FILTER (WHERE a.caracteristica_id = {PES_ID})  AS pes,
                   MAX(a.valor) FILTER (WHERE a.caracteristica_id = {IQGG_ID}) AS iqgg,
                   MIN(o.preco_dose_brl) AS preco_dose
            FROM mercado.reprodutor r
            JOIN catalogo.raca ra ON ra.id = r.raca_id
            JOIN mercado.touro_oferta o ON o.reprodutor_id = r.id
                 AND o.preco_dose_brl > 0 AND o.central_id = %(central)s
            LEFT JOIN mercado.avaliacao a ON a.reprodutor_id = r.id
                 AND a.caracteristica_id IN ({PD_ID}, {PES_ID}, {IQGG_ID})
            WHERE r.sexo = 'M'
            GROUP BY r.id, r.nome, ra.sigla
            ORDER BY MAX(a.valor) FILTER (WHERE a.caracteristica_id = {IQGG_ID}) DESC NULLS LAST
            """, {"central": MONTE_SIAO_CENTRAL_ID})
        for t in rows:
            t["prenhez_est"] = _prenhez_est(t.get("pes"))
        arroba = (external_apis.boi_gordo() or {}).get("valor")
        return {"touros": rows, "arroba": arroba}
    except Exception as e:
        return _error(e)


@router.get("/api/simulador/proposta")
async def simulador_proposta(t: int, m: int = 100, p: float = 60, a: float = None):
    """PDF da proposta de retorno (Feature 5) — público, ZERO PII. `t`=touro Monte Sião,
    `m`=matrizes, `p`=prenhez atual %, `a`=preço @ (default = boi gordo ao vivo)."""
    try:
        # endpoint PÚBLICO: clamp de tudo que entra no cálculo/PDF. float('nan'/'inf')
        # passa pelo parse do FastAPI e estoura no round(); valores absurdos não fazem
        # sentido e encarecem o WeasyPrint de graça.
        m = max(0, min(int(m), 100_000))
        p = float(p) if (p is not None and math.isfinite(float(p))) else 60.0
        p = max(0.0, min(p, 100.0))
        if a is not None:
            a = float(a)
            a = a if (math.isfinite(a) and 0 < a <= 5000) else None
        rows = query(
            f"""SELECT r.id, r.nome, ra.nome AS raca,
                       MAX(av.valor) FILTER (WHERE av.caracteristica_id = {PD_ID})  AS pd,
                       MAX(av.valor) FILTER (WHERE av.caracteristica_id = {PES_ID}) AS pes,
                       MIN(o.preco_dose_brl) AS preco_dose
                FROM mercado.reprodutor r
                JOIN catalogo.raca ra ON ra.id = r.raca_id
                JOIN mercado.touro_oferta o ON o.reprodutor_id = r.id
                     AND o.preco_dose_brl > 0 AND o.central_id = %(central)s
                LEFT JOIN mercado.avaliacao av ON av.reprodutor_id = r.id
                     AND av.caracteristica_id IN ({PD_ID}, {PES_ID})
                WHERE r.id = %(id)s
                GROUP BY r.id, r.nome, ra.nome""",
            {"id": t, "central": MONTE_SIAO_CENTRAL_ID})
        if not rows:
            return JSONResponse({"error": "touro fora do catálogo Monte Sião"}, status_code=404)
        b = rows[0]
        # handler é async: o fetch da arroba (HTTP externo, até 20s) vai pro threadpool
        # p/ não bloquear o event loop inteiro do uvicorn.
        arroba = a if (a and a > 0) else \
            (await run_in_threadpool(external_apis.boi_gordo) or {}).get("valor")
        pd, pes, preco_dose = b.get("pd"), b.get("pes"), b.get("preco_dose")
        ganho_cria = round(pd * arroba / 30) if (pd and pd > 0 and arroba) else None
        prenhez_esp = _prenhez_est(pes) or int(p)
        matrizes = max(0, int(m))
        total_bezerros = round(matrizes * prenhez_esp / 100)
        bezerros_add = max(0, round(matrizes * max(0, prenhez_esp - p) / 100))
        ganho_safra = (total_bezerros * ganho_cria) if ganho_cria else 0
        equil = (-(-int(preco_dose) // ganho_cria)) if (preco_dose and ganho_cria and ganho_cria > 0) else None
        dados = {
            "touro_nome": b.get("nome"), "raca": b.get("raca"), "matrizes": matrizes,
            "prenhez_atual": round(p), "prenhez_esperada": prenhez_esp, "arroba": round(arroba) if arroba else None,
            "ganho_cria": ganho_cria, "total_bezerros": total_bezerros, "bezerros_adicionais": bezerros_add,
            "ganho_genetico_safra": ganho_safra, "equilibrio": equil, "preco_dose": preco_dose,
            "data_str": datetime.now().strftime("%d/%m/%Y"),
        }
        pdf = await run_in_threadpool(gerar_proposta_simulador, dados)
        nome = (b.get("nome") or "touro").replace(" ", "_")[:30]
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="proposta_{nome}.pdf"'})
    except Exception as e:
        return _error(e)
