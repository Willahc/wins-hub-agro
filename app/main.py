from fastapi import FastAPI, Request, Response, Form, UploadFile, File
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse, FileResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from starlette.concurrency import run_in_threadpool
from auth import authenticate_user, create_access_token, decode_token
from pdf_html import (gerar_parecer_cruzamento, gerar_parecer_matching,  # HTML/CSS -> WeasyPrint
                      gerar_cotacao_acasalamento, gerar_briefing_chegada,
                      gerar_proposta_simulador, gerar_relatorio_territorial)
import external_apis
import psycopg2
import psycopg2.extras
from psycopg2 import pool as pgpool
import asyncio
import logging
import io
import os

logger = logging.getLogger("wins_agro")

# docs/openapi desligados: app single-tenant não deve expor o mapa de rotas/schemas
# (incl. endpoints de PII/lead) a quem não está autenticado. O middleware só protege /api/*.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
# Versão do shell — bumpar a cada deploy de front. O cliente compara com /api/version e
# se auto-atualiza (limpa cache + reload) se estiver velho. Mata o "downgrade pra v1".
APP_VERSION = "2026-06-11.9"
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/api/version")
def app_version():
    from fastapi.responses import JSONResponse as _JR
    return _JR({"version": APP_VERSION}, headers={"Cache-Control": "no-store"})
templates = Jinja2Templates(directory="frontend")


@app.middleware("http")
async def request_pipeline(request: Request, call_next):
    """Exige sessão válida em /api/* (dados sensíveis/PII) e aplica cache longo
    nos assets versionados de /static/vendor/."""
    path = request.url.path
    # CSRF defense-in-depth: requisições que mudam estado só são aceitas same-origin.
    # SameSite=Lax já barra a maior parte; isto fecha o resto sem custo. Browsers
    # mandam Sec-Fetch-Site/Origin; clientes legítimos same-origin passam.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        sfs = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        host = request.headers.get("host")
        cross = (sfs in ("cross-site", "same-site")) or (
            origin is not None and host is not None
            and origin.split("://")[-1] != host)
        if cross:
            return JSONResponse({"error": "Origem não permitida"}, status_code=403)
    # /api/simulador/* é PÚBLICO (Feature 5: simulador que a Mari abre na fazenda) — só
    # devolve catálogo de touros + cálculo, ZERO PII. O resto de /api/* exige sessão.
    if path.startswith("/api/") and not path.startswith("/api/simulador"):
        token = request.cookies.get("access_token")
        if not token or decode_token(token) is None:
            return JSONResponse({"error": "Não autenticado"}, status_code=401)
    response = await call_next(request)
    if path.startswith("/static/vendor/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        "frontend/sw.js", media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse("frontend/manifest.webmanifest",
                        media_type="application/manifest+json")


def _error(e):
    """Loga o erro real no servidor e devolve mensagem genérica ao cliente
    (evita vazar SQL/estrutura interna)."""
    logger.exception("Erro ao processar requisição: %s", e)
    return {"error": "Erro interno ao processar a requisição."}

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    # least-privilege: a app conecta como DB_USER (wins_app, só DML nos schemas de
    # negócio) — POSTGRES_USER/PASSWORD ficam só p/ o container do banco (superuser).
    "user": os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", ""),
}

# IQGg = Índice de Qualificação Genética Genômica (Básico) — catalogo.caracteristica.id = 20
IQGG_ID = 20
PD_ID = 5    # Peso à Desmama (210d) — DEP usada p/ o ganho financeiro por cria (R$/cria)
PES_ID = 12  # Perímetro Escrotal ao Sobreano — proxy de fertilidade (taxa de prenhez)
MONTE_SIAO_CENTRAL_ID = 24  # catalogo.central "Monte Sião Genética" (simulador é ferramenta de venda DELES)

# Protocolo IATF 11 dias (Brief B/F1): (dias desde o D0, descrição do passo).
# Vira agenda automática do lote — o "calendário" da estação de monta.
PROTOCOLO_IATF = [
    (0,  "Implante de progesterona + GnRH"),
    (8,  "Retira implante + PGF2α + eCG"),
    (11, "IATF + GnRH"),
    (41, "Diagnóstico de gestação (DG)"),
]

# Heurística DEP(PES) -> % prenhez estimada (ANCP). base + DEP×coef, limitada a [50,90].
# Coeficiente provisório — calibrar com zootecnista; SEMPRE exibir com "~" (estimativa).
PRENHEZ_BASE = 65.0
PRENHEZ_COEF = 0.3


def _prenhez_est(pes_dep):
    """Taxa de prenhez estimada (%) a partir do DEP de Perímetro Escrotal. None se sem dado."""
    if pes_dep is None:
        return None
    return int(max(50, min(90, round(PRENHEZ_BASE + float(pes_dep) * PRENHEZ_COEF))))

# Mapeamento prioridade -> caracteristica_id (IDs reais confirmados no B0 da Sessão 3).
# Só usamos traços com objetivo_aumentar=TRUE (maior = melhor), pois o score normaliza
# assumindo "maior DEP = melhor". Por isso precocidade usa PES (não IPP, que é invertido).
PRIORIDADE_DEP = {
    "crescimento": 8,   # GPD — Ganho Pós-Desmama
    "carcaca": 16,      # AOL — Área de Olho de Lombo
    "precocidade": 12,  # PES — Perímetro Escrotal ao Sobreano (precocidade sexual)
    "fertilidade": 11,  # HP  — Habilidade de Permanência (Stayability)
    "marmoreio": 18,    # MAR — Marmoreio (dados de Nelore + Wagyu)
    "geral": 20,        # IQGg
}


# Pool de conexões (reaproveita conexões em vez de abrir uma nova por query).
_POOL = None


def _get_pool():
    global _POOL
    if _POOL is None:
        _POOL = pgpool.ThreadedConnectionPool(1, 12, **DB_CONFIG)
    return _POOL


def _fetch(sql, params, dict_rows):
    """Executa um SELECT usando o pool. Só leitura -> autocommit (sem transações
    pendentes). Em conexão morta (OperationalError), descarta e tenta 1x de novo."""
    pool = _get_pool()
    err = None
    for _ in range(2):
        conn = pool.getconn()
        try:
            conn.autocommit = True
            cur = (conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                   if dict_rows else conn.cursor())
            cur.execute(sql, params or {})
            rows = cur.fetchall()
            pool.putconn(conn)
            return rows
        except psycopg2.OperationalError as e:
            err = e
            try:
                pool.putconn(conn, close=True)  # conexão morta -> remove do pool
            except Exception:
                pass
        except Exception:
            try:
                pool.putconn(conn)
            except Exception:
                pass
            raise
    raise err


def query(sql, params=None):
    """Run a SELECT and return a list of dict rows (decimals cast to float)."""
    result = []
    for row in _fetch(sql, params, True):
        d = dict(row)
        for k, v in d.items():
            # JSON-serialize numeric/Decimal as float
            if v.__class__.__name__ == "Decimal":
                d[k] = float(v)
        result.append(d)
    return result


def scalar(sql, params=None):
    return _fetch(sql, params, False)[0][0]


def audit(request, acao, detalhe=None, n_linhas=None):
    """Trilha de auditoria — quem (usuário do cookie) fez o quê (login/view/export),
    quando, de qual IP, quantas linhas. Dado é valioso: tudo que toca PII em volume é logado.
    Falha de log NUNCA derruba a requisição (best-effort)."""
    try:
        u = get_current_user(request)
        usuario = (u or {}).get("sub") if isinstance(u, dict) else None
        ip = (request.headers.get("x-forwarded-for") or
              (request.client.host if request.client else None))
        if ip:
            ip = ip.split(",")[0].strip()
        pool = _get_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO prospeccao.audit_log(usuario,acao,detalhe,ip,n_linhas) "
                "VALUES (%s,%s,%s,%s,%s)",
                (usuario, acao, detalhe, ip, n_linhas))
        finally:
            pool.putconn(conn)
    except Exception:
        logger.warning("audit falhou (acao=%s)", acao)


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_token(token)


# ---------------------------------------------------------------------------
# Auth / pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    resp = templates.TemplateResponse("index.html", {"request": request, "user": user, "app_version": APP_VERSION})
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"  # shell nunca cacheado (mata downgrade do app/WebView)
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(response: Response, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    if not user:
        return RedirectResponse("/login?error=1", status_code=303)
    token = create_access_token({"sub": user["email"], "name": user["name"]})
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        "access_token", token,
        httponly=True, secure=True, samesite="lax",
        max_age=60 * 60 * 8,
    )
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp


# ---------------------------------------------------------------------------
# Feature 5 — Simulador público (Mari abre na fazenda; sem login; ZERO PII)
# ---------------------------------------------------------------------------
@app.get("/simulador", response_class=HTMLResponse)
def simulador_page(request: Request):
    return templates.TemplateResponse("simulador.html", {"request": request})


@app.get("/api/simulador/touros")
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


@app.get("/api/simulador/proposta")
async def simulador_proposta(t: int, m: int = 100, p: float = 60, a: float = None):
    """PDF da proposta de retorno (Feature 5) — público, ZERO PII. `t`=touro Monte Sião,
    `m`=matrizes, `p`=prenhez atual %, `a`=preço @ (default = boi gordo ao vivo)."""
    try:
        import math
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


# ---------------------------------------------------------------------------
# API — data endpoints
# ---------------------------------------------------------------------------
@app.get("/api/stats")
def stats():
    try:
        # uma única ida ao banco (era 6 conexões/queries separadas)
        return query(
            """
            SELECT
              (SELECT COUNT(*) FROM mercado.reprodutor WHERE sexo = 'M' OR sexo IS NULL) AS reprodutores,
              (SELECT COUNT(*) FROM mercado.reprodutor WHERE sexo = 'F') AS matrizes,
              -- reprodutores de leite = têm avaliação em grupo de produção/conformação leiteira
              -- (PTA Leite/Gordura/Proteína/Sólidos, STA Úbere). Hoje: Gir Leiteiro + Girolando.
              (SELECT COUNT(DISTINCT a.reprodutor_id)
                 FROM mercado.avaliacao a
                 JOIN catalogo.caracteristica c ON c.id = a.caracteristica_id
                 WHERE c.grupo IN ('producao_leite', 'conformacao_leite')) AS leite,
              -- corte = reprodutores avaliados que NÃO são de leite (split exclusivo)
              ((SELECT COUNT(DISTINCT reprodutor_id) FROM mercado.avaliacao)
                - (SELECT COUNT(DISTINCT a.reprodutor_id)
                     FROM mercado.avaliacao a
                     JOIN catalogo.caracteristica c ON c.id = a.caracteristica_id
                     WHERE c.grupo IN ('producao_leite', 'conformacao_leite'))) AS corte,
              (SELECT COUNT(*) FROM mercado.avaliacao)             AS avaliacoes,
              (SELECT COUNT(*) FROM catalogo.central)              AS centrais,
              (SELECT COUNT(*) FROM mercado.touro_oferta)          AS ofertas,
              (SELECT COUNT(*) FROM prospeccao.v_white_space_pecuaria) AS municipios,
              (SELECT COUNT(*) FROM prospeccao.v_white_space_pecuaria
                 WHERE classificacao_vet = 'DESERTO VET')          AS desertos_vet
            """
        )[0]
    except Exception as e:
        return _error(e)


# Aptidão zootécnica por raça (id da catalogo.raca). Classificação baseada em
# fontes do setor (ABCZ, Embrapa, associações de raça): corte / leite / dupla
# aptidão. Equinos (especie EQU) = esporte/trabalho; búfalo (BUF) = bubalino.
# Mantido em código (não no banco) — é referência estável e reversível.
RACA_APTIDAO = {
    # CORTE (carne)
    1: "corte",   # Nelore
    2: "corte",   # Brahman
    7: "corte",   # Tabapuã
    8: "corte",   # Senepol
    9: "corte",   # Aberdeen Angus
    10: "corte",  # Hereford
    11: "corte",  # Braford
    12: "corte",  # Charolês
    13: "corte",  # Limousin
    14: "corte",  # Canchim
    16: "corte",  # Curraleiro Pé-Duro
    17: "corte",  # Brangus
    18: "corte",  # Ultrablack
    19: "corte",  # Santa Gertrudis
    20: "corte",  # Montana
    36: "corte",  # Red Brangus
    37: "corte",  # Red Angus
    41: "corte",  # Bonsmara
    44: "corte",  # Wagyu
    47: "corte",  # Texas Longhorn
    48: "corte",  # Speckle Park
    # LEITE
    21: "leite",  # Holandês
    22: "leite",  # Gir Leiteiro
    23: "leite",  # Jersey
    24: "leite",  # Pardo Suíço
    35: "leite",  # Simental Leiteiro
    38: "leite",  # Girolando
    39: "leite",  # Guzerá Leiteiro
    40: "leite",  # Sindi Leiteiro
    # DUPLA APTIDÃO (corte + leite)
    3: "dupla",   # Gir
    4: "dupla",   # Guzerá
    5: "dupla",   # Indubrasil
    6: "dupla",   # Sindi
    15: "dupla",  # Caracu
    34: "dupla",  # Simental
    42: "dupla",  # Braunvieh
    43: "dupla",  # Devon
    45: "dupla",  # Gelbvieh
    46: "dupla",  # Shorthorn
    # EQUINOS (esporte/trabalho)
    26: "esporte", 27: "esporte", 28: "esporte", 29: "esporte",
    30: "esporte", 31: "esporte", 32: "esporte", 33: "esporte",
    # BUBALINO
    25: "bubalino",  # Búfalo
}


def _aptidao(raca_id):
    return RACA_APTIDAO.get(raca_id, "corte")


def _racas_por_finalidade(fin):
    """IDs de raça elegíveis p/ a finalidade do matching: corte=corte+dupla,
    leite=leite+dupla, dupla=só dupla. Exclui equino/bubalino."""
    fin = (fin or "corte").lower()
    if fin == "leite":
        alvo = {"leite", "dupla"}
    elif fin == "dupla":
        alvo = {"dupla"}
    else:
        alvo = {"corte", "dupla"}
    return tuple(rid for rid, ap in RACA_APTIDAO.items() if ap in alvo)


@app.get("/api/overview/racas")
def overview_racas():
    """Top 8 raças por volume de reprodutores (barras da Visão Geral), com aptidão."""
    try:
        rows = query(
            """
            SELECT ra.id, ra.nome, COUNT(*) AS total
            FROM mercado.reprodutor r
            JOIN catalogo.raca ra ON ra.id = r.raca_id
            WHERE r.sexo = 'M' OR r.sexo IS NULL
            GROUP BY ra.id, ra.nome
            ORDER BY total DESC
            LIMIT 8
            """
        )
        for r in rows:
            r["aptidao"] = _aptidao(r["id"])
        return rows
    except Exception as e:
        return _error(e)


@app.get("/api/racas/aptidao")
def racas_aptidao():
    """Catálogo de raças agrupado por aptidão (corte/leite/dupla) + equinos/búfalo,
    com nº de reprodutores de cada. Alimenta a seção 'Raças por aptidão' no front."""
    try:
        rows = query(
            """
            SELECT ra.id, ra.nome, ra.sigla, ra.especie_codigo AS especie,
                   COUNT(r.id) AS reprodutores
            FROM catalogo.raca ra
            LEFT JOIN mercado.reprodutor r ON r.raca_id = ra.id
                 AND (r.sexo = 'M' OR r.sexo IS NULL)
            GROUP BY ra.id, ra.nome, ra.sigla, ra.especie_codigo
            ORDER BY COUNT(r.id) DESC, ra.nome
            """
        )
        grupos = {"corte": [], "leite": [], "dupla": [], "esporte": [], "bubalino": []}
        for r in rows:
            ap = _aptidao(r["id"])
            grupos.setdefault(ap, []).append({
                "nome": r["nome"], "sigla": r["sigla"],
                "especie": r["especie"], "reprodutores": r["reprodutores"],
            })
        return grupos
    except Exception as e:
        return _error(e)


@app.get("/api/overview/regioes")
def overview_regioes():
    """Top 6 UFs por rebanho com nº de Desertos Vet (genética × território)."""
    try:
        return query(
            """
            SELECT uf,
                   SUM(bovinos) AS rebanho,
                   COUNT(*) FILTER (WHERE classificacao_vet = 'DESERTO VET') AS desertos
            FROM prospeccao.v_white_space_pecuaria
            WHERE uf IS NOT NULL
            GROUP BY uf
            ORDER BY rebanho DESC
            LIMIT 6
            """
        )
    except Exception as e:
        return _error(e)


@app.get("/api/ufs")
def ufs():
    try:
        rows = query(
            "SELECT DISTINCT uf FROM prospeccao.v_white_space_pecuaria "
            "WHERE uf IS NOT NULL ORDER BY uf"
        )
        return [r["uf"] for r in rows]
    except Exception as e:
        return _error(e)


@app.get("/api/racas")
def racas():
    try:
        return query(
            """
            SELECT DISTINCT ra.id, ra.nome
            FROM catalogo.raca ra
            JOIN mercado.reprodutor r ON r.raca_id = ra.id
            JOIN mercado.touro_oferta o ON o.reprodutor_id = r.id
            WHERE o.preco_dose_brl > 0
            ORDER BY ra.nome
            """
        )
    except Exception as e:
        return _error(e)


@app.get("/api/whitespace")
def whitespace(uf: str = None):
    try:
        return query(
            """
            SELECT nome AS municipio_nome, uf, bovinos AS total_bovinos,
                   cnpj_vet, classificacao_vet
            FROM prospeccao.v_white_space_pecuaria
            WHERE bovinos > 50000
              AND (%(uf)s IS NULL OR uf = %(uf)s)
            ORDER BY bovinos DESC
            LIMIT 50
            """,
            {"uf": uf if uf else None},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/arbitragem")
def arbitragem(raca: int = None, segmento: str = None, central: str = None):
    try:
        use_apt = segmento in ("corte", "leite", "dupla")
        racas_apt = _racas_por_finalidade(segmento) if use_apt else (0,)
        return query(
            """
            SELECT r.id, r.nome AS nome_touro, r.registro,
                   ra.nome AS raca, c.nome AS central,
                   o.preco_dose_brl AS preco_convencional,
                   o.preco_dose_sexado_m AS preco_sexado_macho,
                   iq.valor AS iqgg,
                   CASE WHEN iq.valor > 0 AND o.preco_dose_brl > 0
                        THEN ROUND((o.preco_dose_brl / iq.valor)::numeric, 2)
                        ELSE NULL END AS preco_por_iqgg
            FROM mercado.reprodutor r
            JOIN catalogo.raca ra ON ra.id = r.raca_id
            JOIN mercado.touro_oferta o ON o.reprodutor_id = r.id
            JOIN catalogo.central c ON c.id = o.central_id
            LEFT JOIN (
                SELECT reprodutor_id, MAX(valor) AS valor
                FROM mercado.avaliacao
                WHERE caracteristica_id = %(iqgg)s
                GROUP BY reprodutor_id
            ) iq ON iq.reprodutor_id = r.id
            WHERE o.preco_dose_brl IS NOT NULL AND o.preco_dose_brl > 0
              AND (%(raca)s IS NULL OR ra.id = %(raca)s)
              -- filtro por aptidão (corte/leite/dupla); raça específica tem prioridade
              AND (%(raca)s IS NOT NULL OR NOT %(use_apt)s OR ra.id IN %(racas_apt)s)
              AND (%(central)s IS NULL OR c.nome = %(central)s)
            ORDER BY preco_por_iqgg ASC NULLS LAST
            LIMIT 200
            """,
            {"iqgg": IQGG_ID, "raca": raca, "use_apt": use_apt, "racas_apt": racas_apt,
             "central": central},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/centrais")
def centrais():
    try:
        return query(
            """
            -- CRV Brasil (id 23) e CRV Lagoa (id 9) são a MESMA central, cadastradas
            -- em 2 registros -> consolida na linha "CRV" (nome canônico).
            -- Agregados por CTE separada: o join duplo touro_central × touro_oferta
            -- fazia fan-out e distorcia o AVG (cada oferta repetida N vezes).
            WITH cn AS (
                SELECT id, CASE WHEN nome ILIKE 'CRV%%' THEN 'CRV' ELSE nome END AS central
                FROM catalogo.central
            ),
            t AS (
                SELECT cn.central, COUNT(DISTINCT tc.reprodutor_id) AS total_touros
                FROM cn JOIN mercado.touro_central tc ON tc.central_id = cn.id
                GROUP BY cn.central
            ),
            o AS (
                SELECT cn.central, COUNT(*) AS total_ofertas,
                       ROUND(AVG(ofr.preco_dose_brl)::numeric, 2) AS preco_medio
                FROM cn JOIN mercado.touro_oferta ofr ON ofr.central_id = cn.id
                GROUP BY cn.central
            )
            SELECT c.central,
                   COALESCE(t.total_touros, 0) AS total_touros,
                   COALESCE(o.total_ofertas, 0) AS total_ofertas,
                   o.preco_medio
            FROM (SELECT DISTINCT central FROM cn) c
            LEFT JOIN t USING (central)
            LEFT JOIN o USING (central)
            ORDER BY total_touros DESC
            """
        )
    except Exception as e:
        return _error(e)


@app.get("/api/fazendas")
def fazendas():
    try:
        return query(
            """
            -- agrupa por nome normalizado (UPPER+TRIM+unaccent) p/ consolidar
            -- variações de caixa (ex.: "Genealogia"/"GENEALOGIA"); exibe um nome
            -- representativo. Exclui "GENEALOGIA" = placeholder de origem não
            -- informada (não é fazenda real; puxava IQGg médio negativo p/ o topo).
            SELECT initcap(MIN(r.fazenda_origem)) AS fazenda_origem,
                   COUNT(*) AS total_reprodutores,
                   ROUND(AVG(iq.valor)::numeric, 2) AS iqgg_medio
            FROM mercado.reprodutor r
            LEFT JOIN (
                SELECT reprodutor_id, AVG(valor) AS valor
                FROM mercado.avaliacao
                WHERE caracteristica_id = %(iqgg)s
                GROUP BY reprodutor_id
            ) iq ON iq.reprodutor_id = r.id
            WHERE r.fazenda_origem IS NOT NULL
              AND upper(unaccent(trim(r.fazenda_origem))) <> 'GENEALOGIA'
            GROUP BY upper(unaccent(trim(r.fazenda_origem)))
            HAVING COUNT(*) >= 3
            ORDER BY total_reprodutores DESC
            LIMIT 20
            """,
            {"iqgg": IQGG_ID},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/caracteristicas")
def caracteristicas():
    try:
        return query(
            """
            SELECT id, sigla, nome, objetivo_aumentar
            FROM catalogo.caracteristica
            WHERE id IN %(ids)s
            ORDER BY array_position(%(order)s::int[], id)
            """,
            {
                "ids": tuple(PRIORIDADE_DEP.values()),
                "order": list(PRIORIDADE_DEP.values()),
            },
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Motor de matching
# ---------------------------------------------------------------------------
class MatchingRequest(BaseModel):
    finalidade: Optional[str] = "corte"      # corte | leite | dupla (informativo)
    uf: Optional[str] = None
    raca_id: Optional[int] = None
    prioridade: str = "geral"                # crescimento|carcaca|precocidade|fertilidade|geral
    orcamento_max: Optional[float] = None    # R$/dose
    sexado: bool = False


def _scorar_matching(rows):
    """Score 0..1 de adequação para COMPRA de sêmen, calculado em Python sobre o
    conjunto de candidatos. Combina três eixos, deliberadamente NÃO comparando
    DEPs crus entre raças (escalas incompatíveis):

      • genética (0.45): mérito na DEP prioritária, normalizado POR RAÇA
        (dep / melhor-da-raça). Responde "quão elite é dentro da própria raça".
      • valor econômico (0.35): valor agregado em R$ por filho(a), normalizado
        por FINALIDADE (corte=bezerro, leite=filha). R$ é comparável entre raças.
      • disponibilidade comercial (0.20): touro com preço público acionável e
        eficiente (menor R$/IQGg da raça) pontua mais; sem preço público recebe
        baseline baixa — o matching premia o que dá pra de fato comprar.

    Sem este blend o score saturava em 1.000 (o líder de cada raça empatava no
    topo no modo raça=Todas) e touros com preço nunca emergiam.
    """
    if not rows:
        return rows
    dep_range = {}        # [min, max] da DEP prioritária por raça (normaliza no intervalo
                          # OBSERVADO; DEP é desvio e pode ser negativa — dividir pelo max
                          # zeraria o eixo genético inteiro quando o melhor touro tem DEP<=0)
    min_ppi = {}          # melhor (menor) R$/IQGg por raça
    max_bezerro = 0.0     # melhor valor/bezerro global (finalidade corte)
    max_filha = 0.0       # melhor valor/filha global (finalidade leite)
    for t in rows:
        r = t.get("raca")
        dep = t.get("dep_prioritaria")
        if dep is not None:
            rng = dep_range.get(r)
            if rng is None:
                dep_range[r] = [dep, dep]
            else:
                if dep < rng[0]: rng[0] = dep
                if dep > rng[1]: rng[1] = dep
        ppi = t.get("preco_por_iqgg")
        if ppi and (r not in min_ppi or ppi < min_ppi[r]):
            min_ppi[r] = ppi
        if t.get("valor_bezerro"):
            max_bezerro = max(max_bezerro, t["valor_bezerro"])
        if t.get("valor_filha"):
            max_filha = max(max_filha, t["valor_filha"])

    for t in rows:
        r = t.get("raca")
        dep = t.get("dep_prioritaria")
        rng = dep_range.get(r)
        if dep is None or rng is None:
            g = 0.0
        else:
            lo, hi = rng
            g = (dep - lo) / (hi - lo) if hi > lo else 0.5   # raça com 1 touro -> neutro
        # valor econômico (por finalidade; corte tem precedência se ambos)
        if t.get("valor_bezerro") and max_bezerro > 0:
            v = t["valor_bezerro"] / max_bezerro
        elif t.get("valor_filha") and max_filha > 0:
            v = t["valor_filha"] / max_filha
        else:
            v = 0.0
        # disponibilidade comercial + eficiência de preço
        ppi = t.get("preco_por_iqgg")
        if ppi and min_ppi.get(r):
            a = 0.5 + 0.5 * (min_ppi[r] / ppi)   # 0.5..1.0 (melhor preço -> 1.0)
        elif t.get("preco_dose"):
            a = 0.6
        else:
            a = 0.30                              # sem preço público (não acionável)
        t["score"] = round(0.45 * g + 0.35 * v + 0.20 * a, 3)

    rows.sort(key=lambda t: t["score"], reverse=True)
    return rows


@app.post("/api/matching")
async def matching(req: MatchingRequest):
    try:
        dep_id = PRIORIDADE_DEP.get(req.prioridade, IQGG_ID)
        params = {
            "iqgg": IQGG_ID,
            "dep_id": dep_id,
            "raca_id": req.raca_id,
            "uf": req.uf,
            "orcamento_max": req.orcamento_max,
            "sexado": bool(req.sexado),
            "racas_apt": _racas_por_finalidade(req.finalidade) or (0,),  # nunca IN () -> erro SQL
        }
        # DISTINCT ON (r.id) -> um único registro por touro (touro_central pode
        # repetir o touro em várias centrais). O score é calculado em Python
        # (ver _scorar_matching) sobre este conjunto de candidatos: aqui só
        # trazemos os campos crus.
        # IMPORTANTE: a seleção de candidatos é POR RAÇA (ROW_NUMBER particionado),
        # pegando os top-60 de cada raça pela DEP prioritária. Um LIMIT global por
        # DEP cru viesaria tudo p/ raças de escala alta (Girolando IQGg ~2000 vs
        # Nelore ~50), engolindo as demais raças no modo raça=Todas.
        rows = query(
            """
            WITH deps AS (
                SELECT reprodutor_id,
                    MAX(CASE WHEN caracteristica_id = %(iqgg)s THEN valor END) AS iqgg,
                    MAX(CASE WHEN caracteristica_id = %(dep_id)s THEN valor END) AS dep_prioritaria,
                    MAX(CASE WHEN caracteristica_id = 5 THEN valor END) AS peso_dep,
                    MAX(CASE WHEN caracteristica_id = 32 THEN valor END) AS pta_leite
                FROM mercado.avaliacao
                GROUP BY reprodutor_id
            ),
            ofertas AS (
                SELECT reprodutor_id,
                    MIN(preco_dose_brl) AS preco_dose,
                    MIN(preco_dose_sexado_m) AS preco_sexado
                FROM mercado.touro_oferta
                GROUP BY reprodutor_id
            ),
            cand AS (
                SELECT DISTINCT ON (r.id)
                    r.id, r.nome, r.registro, r.raca_id, ra.nome AS raca, c.nome AS central,
                    r.fazenda_origem,
                    (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) AS preco_dose,
                    d.iqgg, d.dep_prioritaria, d.peso_dep, d.pta_leite
                FROM mercado.reprodutor r
                JOIN catalogo.raca ra ON ra.id = r.raca_id
                JOIN deps d ON d.reprodutor_id = r.id
                LEFT JOIN mercado.touro_central tc ON tc.reprodutor_id = r.id
                LEFT JOIN catalogo.central c ON c.id = tc.central_id
                LEFT JOIN ofertas o ON o.reprodutor_id = r.id
                WHERE d.iqgg IS NOT NULL
                  AND d.dep_prioritaria IS NOT NULL
                  AND (%(raca_id)s IS NULL OR r.raca_id = %(raca_id)s)
                  -- filtro por aptidão: corte traz raças de corte+dupla, leite traz
                  -- leite+dupla, dupla só dupla. Se o usuário escolheu uma raça
                  -- específica (raca_id), respeita a escolha dele e ignora o filtro.
                  AND (%(raca_id)s IS NOT NULL OR r.raca_id IN %(racas_apt)s)
                  -- preço é opcional: sem orçamento, raças sem oferta entram pelo mérito
                  -- genético. COM orçamento definido (modo comercial), só passam os que
                  -- têm preço dentro do teto.
                  AND (%(orcamento_max)s IS NULL OR %(orcamento_max)s = 0
                       OR (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) <= %(orcamento_max)s)
                ORDER BY r.id, c.nome NULLS LAST
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY raca_id ORDER BY dep_prioritaria DESC NULLS LAST
                ) AS rn
                FROM cand
            )
            -- top-60 genéticos por raça + TODOS os touros com preço público
            -- (comercialmente acionáveis): estes têm genética menor que a elite de
            -- registro e ficariam de fora do corte por DEP, mas são justamente os
            -- que o comprador pode adquirir — precisam entrar no score.
            SELECT * FROM ranked WHERE rn <= 60 OR preco_dose IS NOT NULL
            """,
            params,
        )
        # Valor econômico estimado por bezerro: vantagem de PD (peso à desmama, kg,
        # vs a média da raça) × cotação do boi. Carcaça ~50%, @ = 15 kg ->
        # valor = peso_dep × 0,5 ÷ 15 × R$/@ = peso_dep × preço / 30. É ESTIMATIVA.
        boi = await run_in_threadpool(external_apis.boi_gordo)
        arroba = (boi or {}).get("valor")
        leite = await run_in_threadpool(external_apis.leite_preco)
        litro = (leite or {}).get("valor")
        fin = (req.finalidade or "corte").lower()
        for t in rows:
            pd = t.get("peso_dep")
            # corte: vantagem de PD (kg) x cotação do boi / 30 (R$/bezerro vs média)
            t["valor_bezerro"] = (
                round(pd * arroba / 30, 2)
                if (pd is not None and pd > 0 and arroba) else None
            )
            # leite: PTA Leite (kg/lactação) x preço do leite (R$/lactação por filha)
            pta = t.get("pta_leite")
            t["valor_filha"] = (
                round(pta * litro, 2)
                if (pta is not None and pta > 0 and litro) else None
            )
            # finalidade dirige a métrica de valor agregado: corte só mostra/pontua
            # R$/bezerro, leite só R$/lactação; "dupla" mantém ambos. Sem o gate, um
            # touro de corte sem PD mas com PTA Leite vazava "/lact" no topo do rank.
            if fin == "corte":
                t["valor_filha"] = None
            elif fin == "leite":
                t["valor_bezerro"] = None
            # R$ por ponto de IQGg (eficiência de compra), só quando há preço
            iq = t.get("iqgg")
            pr = t.get("preco_dose")
            t["preco_por_iqgg"] = (
                round(pr / iq, 2) if (pr and iq and iq > 0) else None
            )
            # ROI da dose: valor agregado por bezerro/filha vs custo da dose.
            # É a JUSTIFICATIVA DO PREÇO — premium genético paga mesmo a dose cara.
            ganho = t.get("valor_bezerro") if fin != "leite" else t.get("valor_filha")
            if ganho is not None and pr and pr > 0:
                t["roi_dose"] = round(ganho / pr, 1)              # retorno por R$1 na dose
                t["lucro_bezerro"] = round(ganho - pr, 2)         # lucro líquido / cria
                # nº de bezerros p/ pagar 1 dose (normalmente <1 = paga no 1º)
                t["paga_em"] = round(pr / ganho, 2) if ganho > 0 else None
            else:
                t["roi_dose"] = t["lucro_bezerro"] = t["paga_em"] = None

        rows = _scorar_matching(rows)[:30]
        return {
            "total": len(rows),
            "prioridade": req.prioridade,
            "dep_id": dep_id,
            "boi_arroba": arroba,
            "leite_litro": litro,
            "touros": rows,
        }
    except Exception as e:
        return _error(e)


@app.post("/api/matching/pdf")
async def matching_pdf(req: MatchingRequest):
    # Reusa a mesma lógica do /api/matching
    resultado = await matching(req)
    if "error" in resultado:
        return resultado
    touros = resultado["touros"]

    raca_nome = None
    if req.raca_id:
        rows = query(
            "SELECT nome FROM catalogo.raca WHERE id = %(id)s", {"id": req.raca_id}
        )
        if rows:
            raca_nome = rows[0]["nome"]

    perfil = {
        "finalidade": req.finalidade,
        "uf": req.uf,
        "raca_nome": raca_nome,
        "prioridade": req.prioridade,
        "orcamento_max": req.orcamento_max,
        "sexado": req.sexado,
        "total": resultado["total"],
    }

    pdf_bytes = await run_in_threadpool(gerar_parecer_matching, perfil, touros)
    data_str = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=parecer_zootecnico_{data_str}.pdf"
        },
    )


# ---------------------------------------------------------------------------
# Ficha completa do touro (pivot de DEPs)
# ---------------------------------------------------------------------------
@app.get("/api/touro/{touro_id}")
def touro_detalhe(touro_id: int):
    try:
        rows = query(
            "SELECT * FROM mercado.v_touros_nelore_pivot WHERE id = %(id)s",
            {"id": touro_id},
        )
        if not rows:
            rows = query(
                """
                SELECT r.id, r.nome, r.registro, ra.nome AS raca, r.fazenda_origem,
                       r.consanguinidade, r.genotipado, r.ceip, r.data_nascimento
                FROM mercado.reprodutor r
                JOIN catalogo.raca ra ON ra.id = r.raca_id
                WHERE r.id = %(id)s
                """,
                {"id": touro_id},
            )
            if not rows:
                return {"error": "Touro não encontrado"}
        touro = rows[0]
        # Para raças que não estão no pivot Nelore, monta os DEPs a partir de avaliacao
        # (sigla -> coluna dep_*), pra ficha/radar funcionar em todas as raças.
        sigla_col = {
            "PN": "dep_pn", "PD": "dep_pd", "PS": "dep_ps", "GPD": "dep_gpd",
            "IPP": "dep_ipp", "PES": "dep_pes", "HP": "dep_hp", "AOL": "dep_aol",
            "EGS": "dep_egs", "MAR": "dep_mar", "CAR": "dep_car", "IQGg": "iqg_genomico",
        }
        if not touro.get("iqg_genomico") and not touro.get("dep_ps"):
            deps = query(
                """
                SELECT c.sigla, MAX(a.valor) AS val
                FROM mercado.avaliacao a
                JOIN catalogo.caracteristica c ON c.id = a.caracteristica_id
                WHERE a.reprodutor_id = %(id)s
                GROUP BY c.sigla
                """,
                {"id": touro_id},
            )
            for d in deps:
                col = sigla_col.get(d["sigla"])
                if col:
                    touro[col] = d["val"]
        touro["ofertas"] = query(
            """
            SELECT c.nome AS central, o.preco_dose_brl, o.preco_dose_sexado_m
            FROM mercado.touro_oferta o
            JOIN catalogo.central c ON c.id = o.central_id
            WHERE o.reprodutor_id = %(id)s
            ORDER BY o.preco_dose_brl ASC NULLS LAST
            """,
            {"id": touro_id},
        )
        touro["prenhez_est"] = _prenhez_est(touro.get("dep_pes"))   # Feature 3
        # Brief A: prenhez REALIZADA deste touro nos cruzamentos com DG (previsto × realizado)
        real = query(
            """SELECT COUNT(*) AS n,
                      ROUND(100.0*COUNT(*) FILTER (WHERE resultado='prenhe')/NULLIF(COUNT(*),0)) AS prenhez_real
                 FROM fazenda.cruzamento
                WHERE touro_id = %(id)s AND resultado IN ('prenhe','vazia')""",
            {"id": touro_id})
        touro["prenhez_real"] = (real[0]["prenhez_real"] if real and real[0]["n"] else None)
        touro["dg_n"] = (real[0]["n"] if real else 0)
        return touro
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Matrizes (fêmeas) — catálogo de doadoras/matrizes com mérito materno,
# derivado do pedigree (mãe dos touros avaliados). Ver mercado.v_matriz.
# ---------------------------------------------------------------------------
@app.get("/api/matrizes")
def matrizes(raca: str | None = None, q: str | None = None, uf: str | None = None,
                   min_filhos: int = 1, limit: int = 50):
    """Lista matrizes rankeadas por performance da progênie (filhos touros avaliados)."""
    try:
        # inclui matrizes com mérito por progênie OU com avaliação genômica própria
        # (vacas reais genotipadas do rebanho do cliente, que não têm filhos avaliados)
        cond = ["(filhos_touros >= %(min_filhos)s OR iqgg_proprio IS NOT NULL)"]
        params: dict = {"min_filhos": min_filhos, "limit": min(limit, 500)}
        if raca:
            cond.append("raca_sigla = %(raca)s")
            params["raca"] = raca.upper()
        if uf:
            cond.append("uf = %(uf)s")
            params["uf"] = uf.upper()
        if q:
            cond.append("(nome ILIKE %(q)s OR registro ILIKE %(q)s)")
            params["q"] = f"%{q}%"
        return query(
            f"""
            SELECT id, registro, nome, raca_sigla, pai_nome,
                   filhos_touros, filhos_avaliados,
                   iqgg_medio_filhos, iqgg_melhor_filho,
                   iqgg_proprio, merito_iqgg, merito_origem,
                   fazenda_origem, uf, municipio
            FROM mercado.v_matriz
            WHERE {' AND '.join(cond)}
            ORDER BY merito_iqgg DESC NULLS LAST, filhos_avaliados DESC
            LIMIT %(limit)s
            """,
            params,
        )
    except Exception as e:
        return _error(e)


@app.get("/api/matriz/{matriz_id}")
def matriz_detalhe(matriz_id: int):
    """Ficha da matriz: dados, pai (avô materno) e a progênie com IQGg de cada filho."""
    try:
        rows = query(
            "SELECT * FROM mercado.v_matriz WHERE id = %(id)s", {"id": matriz_id}
        )
        if not rows:
            return {"error": "Matriz não encontrada"}
        matriz = rows[0]
        matriz["filhos"] = query(
            """
            SELECT f.id, f.nome, f.registro,
                   MAX(a.valor) FILTER (WHERE a.caracteristica_id = 20) AS iqgg
            FROM mercado.reprodutor f
            LEFT JOIN mercado.avaliacao a ON a.reprodutor_id = f.id
            WHERE f.mae_id = %(id)s
            GROUP BY f.id, f.nome, f.registro
            ORDER BY iqgg DESC NULLS LAST
            """,
            {"id": matriz_id},
        )
        return matriz
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Acasalamento dirigido (PROTÓTIPO sobre base de exemplo)
# Recomenda touros p/ uma matriz maximizando o mérito esperado da cria e
# EVITANDO consanguinidade via o grafo de pedigree (mae_id / pai_registro /
# avo_materno_registro). Demonstra o fluxo p/ a Monte Sião.
# ---------------------------------------------------------------------------
# características selecionáveis no acasalamento (key -> caracteristica_id, rótulo)
TRAITS_MENU = [
    ("geral", 20, "Índice geral (IQGg)"),
    ("crescimento", 8, "Crescimento (GPD)"),
    ("carcaca", 16, "Carcaça (AOL)"),
    ("precocidade", 12, "Precocidade (PES)"),
    ("fertilidade", 11, "Fertilidade (HP)"),
    ("marmoreio", 18, "Marmoreio (MAR)"),
]
TRAIT_BY_KEY = {k: (cid, lbl) for k, cid, lbl in TRAITS_MENU}
_TRAIT_LABEL = {k: lbl for k, cid, lbl in TRAITS_MENU}


def _trait_keys(traits, prioridade="geral"):
    """Normaliza o parâmetro de características (lista CSV) p/ keys válidas."""
    keys = [k.strip() for k in (traits or "").split(",") if k.strip() in TRAIT_BY_KEY]
    if not keys:
        keys = [prioridade if prioridade in TRAIT_BY_KEY else "geral"]
    # dedup preservando ordem
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k); out.append(k)
    return out


def _ancestrais(a):
    """Registros de ancestrais próximos (não vazios) do animal."""
    return {(a.get(k) or "").strip()
            for k in ("pai_registro", "mae_registro", "avo_materno_registro")
            if (a.get(k) or "").strip()}


def _relacao(a, b):
    """Grau de parentesco entre dois animais (raso, via pedigree). Retorna
    (label, severidade) com severidade em 'bloqueio' | 'alerta' | 'ok'.
    'bloqueio' = consanguinidade próxima (pai/mãe×filho, irmãos); o front impede
    o cruzamento. 'alerta' = ancestral comum mais distante (avós)."""
    ra, rb = (a.get("registro") or "").strip(), (b.get("registro") or "").strip()
    pa, ma = (a.get("pai_registro") or "").strip(), (a.get("mae_registro") or "").strip()
    pb, mb = (b.get("pai_registro") or "").strip(), (b.get("mae_registro") or "").strip()
    avo_a = (a.get("avo_materno_registro") or "").strip()
    avo_b = (b.get("avo_materno_registro") or "").strip()
    # pai/mãe × filho(a) — por registro ou por FK direta
    if ra and ra in (pb, mb):
        return ("Genitor × descendente", "bloqueio")
    if rb and rb in (pa, ma):
        return ("Genitor × descendente", "bloqueio")
    if a.get("id") and a["id"] in (b.get("pai_id"), b.get("mae_id")):
        return ("Genitor × descendente", "bloqueio")
    if b.get("id") and b["id"] in (a.get("pai_id"), a.get("mae_id")):
        return ("Genitor × descendente", "bloqueio")
    # irmãos
    if pa and pa == pb and ma and ma == mb:
        return ("Irmãos completos", "bloqueio")
    if pa and pa == pb:
        return ("Meio-irmãos (mesmo pai)", "bloqueio")
    if ma and ma == mb:
        return ("Meio-irmãos (mesma mãe)", "bloqueio")
    # avô × neto(a)
    if ra and ra == avo_b:
        return ("Avô × neta", "bloqueio")
    if rb and rb == avo_a:
        return ("Avô × neto(a)", "bloqueio")
    # ancestral comum mais distante (avós etc.)
    comum = _ancestrais(a) & _ancestrais(b)
    if comum:
        return ("Ancestral comum: " + ", ".join(sorted(comum)[:2]), "alerta")
    return ("Sem parentesco detectado", "ok")


@app.get("/api/acasalamento/{matriz_id}")
def acasalamento(matriz_id: int, prioridade: str = "geral",
                       traits: str | None = None, raca: str | None = None,
                       tipo: str | None = None, uf: str | None = None,
                       orcamento: float | None = None, top: int = 10):
    try:
        keys = _trait_keys(traits, prioridade)
        trait_ids = [TRAIT_BY_KEY[k][0] for k in keys]
        # PD_ID (ganho/cria) e PES_ID (prenhez) entram só p/ os indicadores — não pontuam no score
        all_ids = list(dict.fromkeys([IQGG_ID, PD_ID, PES_ID] + trait_ids))

        # 1) matriz + dados de pedigree
        drow = query(
            """
            SELECT dam.id, dam.nome, dam.registro, dam.raca_id, ra.nome AS raca, ra.sigla AS raca_sigla,
                   dam.pai_registro, dam.pai_nome, dam.mae_registro, dam.avo_materno_registro,
                   dam.pai_id, dam.mae_id, dam.fazenda_origem, dam.uf, dam.municipio,
                   (SELECT COUNT(*) FROM mercado.reprodutor f WHERE f.mae_id = dam.id) AS n_filhos,
                   (SELECT ROUND(AVG(a.valor), 2) FROM mercado.reprodutor f
                      JOIN mercado.avaliacao a ON a.reprodutor_id = f.id
                      WHERE f.mae_id = dam.id AND a.caracteristica_id = %(iqgg)s) AS iqgg
            FROM mercado.reprodutor dam
            JOIN catalogo.raca ra ON ra.id = dam.raca_id
            WHERE dam.id = %(id)s AND dam.sexo = 'F'
            """,
            {"id": matriz_id, "iqgg": IQGG_ID},
        )
        if not drow:
            return {"error": "Matriz não encontrada"}
        dam = drow[0]
        # nível genético da matriz: avaliação PRÓPRIA (vaca genotipada do rebanho real),
        # senão proxy = média da progênie.
        dam_deps = {r["cid"]: r["v"] for r in query(
            """
            SELECT caracteristica_id AS cid, MAX(valor) AS v FROM mercado.avaliacao
            WHERE reprodutor_id = %(id)s AND caracteristica_id IN %(ids)s
            GROUP BY caracteristica_id
            """, {"id": matriz_id, "ids": tuple(all_ids)})}
        if not dam_deps:
            dam_deps = {r["cid"]: r["v"] for r in query(
                """
                SELECT a.caracteristica_id AS cid, ROUND(AVG(a.valor), 2) AS v
                FROM mercado.reprodutor f JOIN mercado.avaliacao a ON a.reprodutor_id = f.id
                WHERE f.mae_id = %(id)s AND a.caracteristica_id IN %(ids)s
                GROUP BY a.caracteristica_id
                """, {"id": matriz_id, "ids": tuple(all_ids)})}
        dam_iqgg = dam_deps.get(IQGG_ID) or dam.get("iqgg") or 0

        # raça-alvo dos candidatos: explícita (raca) > tipo (aptidão) > mesma raça da matriz
        cand_params = {"ids": tuple(all_ids), "orc": orcamento, "uf": (uf.upper() if uf else None)}
        if raca:
            raca_cond = "AND ra.sigla = %(raca_sigla)s"
            cand_params["raca_sigla"] = raca.upper()
        elif tipo and _racas_por_finalidade(tipo):
            raca_cond = "AND r.raca_id IN %(racas_apt)s"
            cand_params["racas_apt"] = _racas_por_finalidade(tipo)
        else:
            raca_cond = "AND r.raca_id = %(raca_id)s"
            cand_params["raca_id"] = dam["raca_id"]

        # colunas de deps geradas a partir de IDs de whitelist (seguro injetar)
        dep_cols = ", ".join(
            f"MAX(CASE WHEN caracteristica_id = {cid} THEN valor END) AS t_{cid}" for cid in all_ids
        )
        cands = query(
            f"""
            WITH deps AS (
                SELECT reprodutor_id, {dep_cols}
                FROM mercado.avaliacao WHERE caracteristica_id IN %(ids)s
                GROUP BY reprodutor_id
            ),
            ofertas AS (
                -- menor preço E a central DESSE preço (a exibida tem que ser a do preço,
                -- não a 1ª em ordem alfabética de touro_central)
                SELECT DISTINCT ON (o.reprodutor_id)
                       o.reprodutor_id, o.preco_dose_brl AS preco, co.nome AS central_preco
                FROM mercado.touro_oferta o
                LEFT JOIN catalogo.central co ON co.id = o.central_id
                WHERE o.preco_dose_brl IS NOT NULL
                ORDER BY o.reprodutor_id, o.preco_dose_brl ASC
            )
            SELECT * FROM (
                SELECT DISTINCT ON (r.id)
                    r.id, r.nome, r.registro, r.fazenda_origem, r.uf, r.municipio, ra.sigla AS raca_sigla,
                    r.pai_registro, r.mae_registro, r.avo_materno_registro, r.mae_id, r.pai_id,
                    COALESCE(o.central_preco, c.nome) AS central, o.preco AS preco_dose, d.*
                FROM mercado.reprodutor r
                JOIN catalogo.raca ra ON ra.id = r.raca_id
                JOIN deps d ON d.reprodutor_id = r.id
                LEFT JOIN ofertas o ON o.reprodutor_id = r.id
                LEFT JOIN mercado.touro_central tc ON tc.reprodutor_id = r.id
                LEFT JOIN catalogo.central c ON c.id = tc.central_id
                WHERE r.sexo = 'M' AND d.t_{IQGG_ID} IS NOT NULL {raca_cond}
                  AND (%(uf)s IS NULL OR r.uf = %(uf)s)
                  -- preço opcional: sem orçamento entram pelo mérito genético; com
                  -- orçamento, só os que têm preço dentro do teto (modo comercial).
                  AND (%(orc)s IS NULL OR %(orc)s = 0 OR o.preco <= %(orc)s)
                ORDER BY r.id, c.nome NULLS LAST
            ) cand
            ORDER BY t_{IQGG_ID} DESC NULLS LAST
            LIMIT 400
            """,
            cand_params,
        )

        # 2) screen de consanguinidade (bloqueia parentes próximos)
        excluidos, pool = 0, []
        for b in cands:
            label, sev = _relacao(dam, b)
            if sev == "bloqueio":
                excluidos += 1
                continue
            b["parentesco"] = label
            b["parente"] = sev == "alerta"
            pool.append(b)

        # 3) score: mérito esperado da cria (midparent IQGg) + média das características
        #    escolhidas (normalizada no pool) + preço
        if pool:
            di = dam_iqgg
            # IQGg da cria (midparent) normalizado no intervalo OBSERVADO do pool — NÃO por
            # /max: ~39% dos IQGg são negativos; dividir pelo max inverteria o ranking quando
            # a matriz puxa a combinação p/ negativo (o melhor touro ficaria com o menor score).
            _prog_vals = [0.5 * ((b.get(f"t_{IQGG_ID}") or 0) + di) for b in pool]
            iqgg_lo, iqgg_hi = min(_prog_vals), max(_prog_vals)
            trait_mid, trait_rng = {}, {}
            for cid in trait_ids:
                dv = dam_deps.get(cid)
                vals = [0.5 * (b.get(f"t_{cid}") + dv) if (b.get(f"t_{cid}") is not None and dv is not None) else None
                        for b in pool]
                trait_mid[cid] = vals
                present = [v for v in vals if v is not None]
                trait_rng[cid] = (min(present), max(present)) if present else (0, 0)
            precos = [b["preco_dose"] for b in pool if b.get("preco_dose")]
            max_preco = max(precos) if precos else 0
            # preço da arroba do boi gordo (cacheado) p/ o ganho financeiro/cria.
            # MESMA fórmula do _monetizacao (PD x @ / 30) -> o número do App bate com o do Hub.
            # (÷30 = 15kg carcaça/@ ÷ ~50% rendimento; NÃO ÷15, que ignoraria o rendimento.)
            arroba = (external_apis.boi_gordo() or {}).get("valor")
            for i, b in enumerate(pool):
                prog_iqgg = round(0.5 * ((b.get(f"t_{IQGG_ID}") or 0) + di), 2)
                b["prog_iqgg"] = prog_iqgg
                # ganho marginal por cria vs. touro médio da raça (DEP de peso já É o desvio)
                _pd = b.get(f"t_{PD_ID}")
                b["ganho_cria"] = (round(_pd * arroba / 30) if (_pd and _pd > 0 and arroba) else None)
                b["roi_cria"] = (round(b["ganho_cria"] / b["preco_dose"], 1)
                                 if (b.get("ganho_cria") and b.get("preco_dose")) else None)
                b["prenhez_est"] = _prenhez_est(b.get(f"t_{PES_ID}"))   # Feature 3
                calf, norms = {}, []
                for k, cid in zip(keys, trait_ids):
                    mv = trait_mid[cid][i]
                    calf[k] = round(mv, 2) if mv is not None else None
                    lo, hi = trait_rng[cid]
                    if mv is not None:
                        norms.append((mv - lo) / (hi - lo) if hi > lo else 0.5)
                b["calf"] = calf
                iqgg_norm = (prog_iqgg - iqgg_lo) / (iqgg_hi - iqgg_lo) if iqgg_hi > iqgg_lo else 0.5
                trait_norm = (sum(norms) / len(norms)) if norms else 0.5
                preco_score = (1 - b["preco_dose"] / max_preco) if (b.get("preco_dose") and max_preco) else 0.3
                score = 0.50 * iqgg_norm + 0.35 * trait_norm + 0.15 * preco_score
                if b["parente"]:
                    score *= 0.85
                b["score"] = round(score, 3)
                b["nota"] = ("⚠ " + b["parentesco"]) if b["parente"] else ""
                # limpa colunas cruas t_<id> do payload
                for cid in all_ids:
                    b.pop(f"t_{cid}", None)
                b.pop("reprodutor_id", None)
            pool.sort(key=lambda b: b["score"], reverse=True)

        trait_labels = {k: TRAIT_BY_KEY[k][1] for k in keys}
        return {
            "matriz": {"id": dam["id"], "nome": dam["nome"], "registro": dam["registro"],
                       "raca": dam["raca"], "raca_sigla": dam.get("raca_sigla"),
                       # mérito exibido: avaliação PRÓPRIA (vaca genotipada) > proxy da progênie
                       "iqgg": dam_deps.get(IQGG_ID) or dam.get("iqgg"),
                       "fazenda_origem": dam.get("fazenda_origem"), "uf": dam.get("uf"),
                       "municipio": dam.get("municipio"),
                       "deps": {k: dam_deps.get(TRAIT_BY_KEY[k][0]) for k in keys},
                       "n_filhos": dam["n_filhos"], "pai_nome": dam.get("pai_nome")},
            "traits": keys, "trait_labels": trait_labels, "trait_label": trait_labels[keys[0]],
            "candidatos": len(cands), "excluidos_parentesco": excluidos,
            "arroba": (external_apis.boi_gordo() or {}).get("valor"),  # @ usada no ganho/cria
            "recomendacoes": pool[:max(1, min(top, 30))],
        }
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Busca de animais (touros/matrizes) para os seletores do cruzamento livre
# ---------------------------------------------------------------------------
@app.get("/api/animais/busca")
def animais_busca(sexo: str = "M", q: str | None = None, raca: str | None = None,
                        tipo: str | None = None, uf: str | None = None, limit: int = 30):
    try:
        cond = ["r.sexo = %(sexo)s"]
        params: dict = {"sexo": sexo.upper(), "iqgg": IQGG_ID, "limit": min(limit, 100)}
        if raca:
            cond.append("ra.sigla = %(raca)s"); params["raca"] = raca.upper()
        if uf:
            cond.append("r.uf = %(uf)s"); params["uf"] = uf.upper()
        if tipo and _racas_por_finalidade(tipo):
            cond.append("r.raca_id IN %(apt)s"); params["apt"] = _racas_por_finalidade(tipo)
        if q:
            cond.append("(r.nome ILIKE %(q)s OR r.registro ILIKE %(q)s)"); params["q"] = f"%{q}%"
        return query(
            f"""
            SELECT r.id, r.nome, r.registro, r.raca_id, ra.sigla AS raca_sigla, ra.nome AS raca, r.sexo,
                   r.fazenda_origem, r.uf, r.municipio,
                   (SELECT MAX(valor) FROM mercado.avaliacao a
                      WHERE a.reprodutor_id = r.id AND a.caracteristica_id = %(iqgg)s) AS iqgg,
                   (SELECT MIN(preco_dose_brl) FROM mercado.touro_oferta o
                      WHERE o.reprodutor_id = r.id) AS preco_dose
            FROM mercado.reprodutor r JOIN catalogo.raca ra ON ra.id = r.raca_id
            WHERE {' AND '.join(cond)}
            ORDER BY iqgg DESC NULLS LAST, r.nome
            LIMIT %(limit)s
            """, params)
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Cruzamento livre: qualquer touro × qualquer vaca -> bezerro previsto + parentesco
# ---------------------------------------------------------------------------
def _num(v):
    """Coerção segura p/ float (DB devolve Decimal); None se não der."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_MEDIA_RACA_IQGG: dict = {}  # cache {raca_id: IQGg médio da raça} p/ o "lift" da matriz


def _media_iqgg_raca(raca_id, cur=None):
    """IQGg médio da raça (baseline p/ medir o quanto a matriz puxa a combinação).
    Cacheado por raça — escala difere muito entre raças (Nelore ~50 vs Girolando ~2000).
    `cur`: quando chamado de dentro de uma transação, passar o cursor dela evita pegar
    uma 2ª conexão do pool (risco de deadlock/exaustão). Cache invalidado na escrita
    via _invalida_media_raca()."""
    if raca_id not in _MEDIA_RACA_IQGG:
        sql = """
            SELECT ROUND(AVG(v)::numeric, 2) AS m FROM (
              SELECT MAX(a.valor) AS v FROM mercado.avaliacao a
              JOIN mercado.reprodutor rr ON rr.id = a.reprodutor_id
              WHERE a.caracteristica_id = %(iq)s AND rr.raca_id = %(rid)s
              GROUP BY a.reprodutor_id) s
            """
        params = {"iq": IQGG_ID, "rid": raca_id}
        if cur is not None:
            cur.execute(sql, params)
            row = cur.fetchone()
            m = row["m"] if row else None
        else:
            r = query(sql, params)
            m = r[0]["m"] if r else None
        _MEDIA_RACA_IQGG[raca_id] = float(m) if m is not None else None
    return _MEDIA_RACA_IQGG[raca_id]


def _invalida_media_raca(raca_id):
    """Esquece o baseline cacheado da raça após gravar avaliação nova (senão o 'lift'
    e a estimativa de mérito da matriz usam média desatualizada)."""
    _MEDIA_RACA_IQGG.pop(raca_id, None)


async def _monetizacao(touro, vaca, calf):
    """Bloco canal-aware (v1): canal DOSE com economia real (preço + valor/cria + ROI),
    EMBRIÃO e ANIMAL VIVO como 'informar preço'. Discriminador: o quanto a matriz puxa
    a combinação (lift sobre a média da raça) -> sinaliza quando o embrião faz sentido."""
    arroba = (await run_in_threadpool(external_apis.boi_gordo) or {}).get("valor")
    oferta = query(
        "SELECT MIN(preco_dose_brl) AS p, MIN(preco_dose_sexado_m) AS ps "
        "FROM mercado.touro_oferta WHERE reprodutor_id = %(id)s", {"id": touro["id"]})
    preco = _num(oferta[0]["p"]) if oferta else None
    preco_sx = _num(oferta[0]["ps"]) if oferta else None
    pd_touro = _num(touro["_deps"].get(5))
    valor_cria = round(pd_touro * arroba / 30, 2) if (pd_touro and pd_touro > 0 and arroba) else None
    roi = round(valor_cria / preco, 1) if (valor_cria and preco) else None
    lucro = round(valor_cria - preco, 2) if (valor_cria is not None and preco) else None

    vaca_iqgg = _num(vaca["_deps"].get(IQGG_ID))
    media = _num(_media_iqgg_raca(vaca["raca_id"]))
    lift = round(vaca_iqgg - media, 2) if (vaca_iqgg is not None and media is not None) else None
    combo = bool(lift is not None and lift > 0)

    dose = {"tipo": "dose", "label": "Dose (sêmen do touro)",
            "status": "ok" if preco else "sem_preco",
            "preco": preco, "preco_sexado": preco_sx,
            "valor_cria": valor_cria, "roi": roi, "lucro": lucro,
            "nota": "Escala, ticket baixo, recorrente — o comprador faz a própria cruza."}
    emb = {"tipo": "embriao", "label": "Embrião (FIV/TE desta cruza)", "status": "informar_preco",
           "nota": ("A combinação agrega (matriz acima da média) — cadastre o preço do embrião para travar a dupla."
                    if combo else "Cadastre o preço do embrião para avaliar a venda da combinação.")}
    vivo = {"tipo": "animal_vivo", "label": "Animal vivo (touro / matriz)", "status": "informar_preco",
            "nota": "Cadastre o valor de venda para comparar com a renda recorrente de dose/embrião (custo de oportunidade)."}

    if not preco:
        recomendado = "cadastrar_preco"
        racional = ("Sem preço de dose cadastrado para este touro. Integre o catálogo da central "
                    "para ativar a análise de monetização (dose/embrião/animal vivo).")
    elif roi is not None and roi >= 1.0:
        # dose se paga sozinha -> é o canal-cavalo (escala + recorrência)
        recomendado = "dose"
        racional = (f"<b>Dose</b> se paga sozinha: R${preco:.0f} → <b>+R${valor_cria:.0f}/cria</b> "
                    f"(ROI <b>{roi:.1f}×</b>) — canal direto, escalável e recorrente.")
    elif combo:
        # dose não fecha no ROI puro, mas a combinação é elite -> embrião é o canal certo
        recomendado = "embriao"
        roi_txt = f" (ROI {roi:.1f}×)" if roi is not None else ""
        racional = (f"A dose a R${preco:.0f} não se paga só no peso da cria{roi_txt}. O valor está na "
                    f"<b>combinação elite</b> (matriz <b>+{lift:.1f} IQGg acima da média</b>): venda como "
                    "<b>embrião</b> ou <b>animal vivo</b>; a dose vira porta de entrada / volume.")
    else:
        # sem prêmio de combinação: dose mesmo, no valor absoluto + escala de lote
        recomendado = "dose"
        roi_txt = f" (ROI {roi:.1f}×)" if roi is not None else ""
        racional = (f"<b>Dose</b> a R${preco:.0f}, <b>+R${valor_cria:.0f}/cria</b>{roi_txt}. "
                    f"Em 30 matrizes, +R${valor_cria*30:.0f} agregados na bezerrada." if valor_cria
                    else f"<b>Dose</b> a R${preco:.0f}.")

    return {"recomendado": recomendado, "racional": racional,
            "combinacao": {"lift_vaca": lift, "media_raca": media, "valiosa": combo},
            "canais": [dose, emb, vivo]}


@app.get("/api/cruzamento")
async def cruzamento(touro_id: int, vaca_id: int, traits: str | None = None):
    try:
        # A previsão do bezerro é biológica e existe para TODAS as características —
        # não depende da prioridade escolhida (essa governa só a sugestão de touro).
        # IQGg sai sempre separado (mid(IQGG_ID)); aqui ficam as demais, sem duplicar "geral".
        keys = [k for k, _cid, _lbl in TRAITS_MENU if k != "geral"]
        trait_ids = [TRAIT_BY_KEY[k][0] for k in keys]
        # id 5 = peso à desmama (PD): base do valor econômico por cria (canal dose)
        all_ids = tuple(dict.fromkeys([IQGG_ID, 5] + trait_ids))

        def fetch(aid):
            rows = query(
                """
                SELECT r.id, r.nome, r.registro, r.sexo, r.raca_id, ra.sigla AS raca_sigla, ra.nome AS raca,
                       r.pai_registro, r.mae_registro, r.avo_materno_registro, r.pai_id, r.mae_id,
                       r.fazenda_origem, r.uf, r.municipio
                FROM mercado.reprodutor r JOIN catalogo.raca ra ON ra.id = r.raca_id WHERE r.id = %(id)s
                """, {"id": aid})
            if not rows:
                return None
            a = rows[0]
            # avaliação PRÓPRIA do animal (touro sempre; vaca genotipada do rebanho real)
            deps = query(
                """
                SELECT caracteristica_id AS cid, MAX(valor) AS v FROM mercado.avaliacao
                WHERE reprodutor_id = %(id)s AND caracteristica_id IN %(ids)s GROUP BY caracteristica_id
                """, {"id": aid, "ids": all_ids})
            if not deps and a["sexo"] == "F":
                # matriz sem avaliação própria -> proxy = média da progênie
                deps = query(
                    """
                    SELECT a.caracteristica_id AS cid, ROUND(AVG(a.valor), 2) AS v
                    FROM mercado.reprodutor f JOIN mercado.avaliacao a ON a.reprodutor_id = f.id
                    WHERE f.mae_id = %(id)s AND a.caracteristica_id IN %(ids)s GROUP BY a.caracteristica_id
                    """, {"id": aid, "ids": all_ids})
            a["_deps"] = {d["cid"]: d["v"] for d in deps}
            return a

        touro, vaca = fetch(touro_id), fetch(vaca_id)
        if not touro or not vaca:
            return {"error": "Animal não encontrado"}
        label, sev = _relacao(touro, vaca)

        def mid(cid):
            tv, vv = touro["_deps"].get(cid), vaca["_deps"].get(cid)
            # cria = média 50/50 das DEPs. Se SÓ um dos pais tem a DEP, o lado
            # ausente entra como 0 (= média da raça, já que DEP é desvio); a cria
            # ainda regride pra metade. Só fica None quando NENHUM dos pais tem.
            if tv is None and vv is None:
                return {"touro": tv, "vaca": vv, "cria": None, "vs_touro": None, "vs_vaca": None}
            cria = 0.5 * ((tv or 0) + (vv or 0))
            return {"touro": tv, "vaca": vv, "cria": round(cria, 2),
                    # delta só faz sentido contra um genitor que realmente tem a DEP
                    "vs_touro": round(cria - tv, 2) if tv is not None else None,
                    "vs_vaca": round(cria - vv, 2) if vv is not None else None}

        def card(a):
            return {"id": a["id"], "nome": a["nome"], "registro": a["registro"],
                    "raca": a["raca"], "raca_sigla": a["raca_sigla"], "iqgg": a["_deps"].get(IQGG_ID),
                    "fazenda_origem": a.get("fazenda_origem"), "uf": a.get("uf"),
                    "municipio": a.get("municipio")}

        calf = {"iqgg": mid(IQGG_ID),
                "traits": {k: mid(TRAIT_BY_KEY[k][0]) for k in keys},
                "trait_labels": {k: TRAIT_BY_KEY[k][1] for k in keys}}
        return {
            "touro": card(touro), "vaca": card(vaca),
            "relacao": {"label": label, "severidade": sev, "bloqueio": sev == "bloqueio"},
            "f1": touro["raca_id"] != vaca["raca_id"],
            "calf": calf,
            "monetizacao": await _monetizacao(touro, vaca, calf),
        }
    except Exception as e:
        return _error(e)


@app.get("/api/cruzamento/pdf")
async def cruzamento_pdf(touro_id: int, vaca_id: int, traits: str | None = None):
    """Parecer PDF de um cruzamento Touro × Vaca = Bezerro (reusa /api/cruzamento)."""
    cruz = await cruzamento(touro_id, vaca_id, traits)
    if "error" in cruz:
        return cruz
    # fichas completas dos genitores p/ anexar ao parecer (reusa os endpoints existentes).
    # touro_detalhe/matriz_detalhe são def síncronas (rodam no threadpool) -> sem await.
    touro_ficha = touro_detalhe(touro_id)
    matriz_ficha = matriz_detalhe(vaca_id)
    pdf_bytes = await run_in_threadpool(
        gerar_parecer_cruzamento, cruz,
        touro_ficha if isinstance(touro_ficha, dict) and "error" not in touro_ficha else None,
        matriz_ficha if isinstance(matriz_ficha, dict) and "error" not in matriz_ficha else None,
    )
    t = (cruz["touro"]["nome"] or "touro").split()[0]
    v = (cruz["vaca"]["nome"] or "vaca").split()[0]
    fname = f"acasalamento_{t}_x_{v}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ---------------------------------------------------------------------------
# Multi-raça: todas as raças com reprodutores + flags de dado disponível
# ---------------------------------------------------------------------------
@app.get("/api/racas/todas")
def racas_todas():
    try:
        # Pré-agrega cada contagem separadamente p/ evitar a explosão de linhas
        # do JOIN reprodutor×avaliacao×oferta (era ~989k linhas / 880ms -> ~10ms).
        return query(
            """
            SELECT ra.id, ra.sigla, ra.nome,
                   rc.cnt AS reprodutores,
                   COALESCE(ac.cnt, 0) AS com_avaliacao,
                   COALESCE(oc.cnt, 0) AS com_oferta
            FROM catalogo.raca ra
            JOIN (
                SELECT raca_id, COUNT(*) AS cnt
                FROM mercado.reprodutor
                WHERE sexo = 'M' OR sexo IS NULL
                GROUP BY raca_id
            ) rc ON rc.raca_id = ra.id
            LEFT JOIN (
                SELECT r.raca_id, COUNT(DISTINCT a.reprodutor_id) AS cnt
                FROM mercado.avaliacao a
                JOIN mercado.reprodutor r ON r.id = a.reprodutor_id
                GROUP BY r.raca_id
            ) ac ON ac.raca_id = ra.id
            LEFT JOIN (
                SELECT r.raca_id, COUNT(DISTINCT o.reprodutor_id) AS cnt
                FROM mercado.touro_oferta o
                JOIN mercado.reprodutor r ON r.id = o.reprodutor_id
                GROUP BY r.raca_id
            ) oc ON oc.raca_id = ra.id
            ORDER BY reprodutores DESC
            """
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Grupos de aptidão (corte / leite / reprodução) — quais têm dado real
# ---------------------------------------------------------------------------
@app.get("/api/grupos")
def grupos():
    try:
        return query(
            """
            SELECT c.grupo, c.tipo,
                   COUNT(DISTINCT c.id) AS total,
                   COUNT(DISTINCT c.id) FILTER (WHERE av.n > 0) AS com_dados,
                   COALESCE(SUM(av.n), 0) AS total_avaliacoes,
                   json_agg(json_build_object(
                       'id', c.id, 'sigla', c.sigla, 'nome', c.nome,
                       'tem_dado', COALESCE(av.n, 0) > 0
                   ) ORDER BY c.id) AS caracteristicas
            FROM catalogo.caracteristica c
            LEFT JOIN (
                SELECT caracteristica_id, COUNT(*) AS n
                FROM mercado.avaliacao GROUP BY 1
            ) av ON av.caracteristica_id = c.id
            WHERE c.aplicavel_especies = 'BOV' AND c.grupo IS NOT NULL
            GROUP BY c.grupo, c.tipo
            ORDER BY com_dados DESC, total DESC
            """
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Marketplace — Oferta × Demanda
# ---------------------------------------------------------------------------
SEGMENTO_CNAE = {"corte": "0151201", "leite": "0151202"}


# colunas ordenáveis da lista de leads -> nome real (whitelist: nunca interpola
# string crua do cliente no SQL).
LEADS_SORT = {"empresa": "nome", "municipio": "municipio", "uf": "uf", "porte": "porte", "score": "score"}
# score = nº de canais de contato confirmados (decisor + email + telefone + whatsapp(celular inferido) + linkedin)
_LEADS_SCORE = ("((decisor IS NOT NULL AND decisor<>'')::int "
                "+ (email IS NOT NULL AND email<>'')::int "
                "+ (telefone_1 IS NOT NULL AND telefone_1<>'')::int "
                "+ (whatsapp_rfb IS NOT NULL)::int "
                "+ (linkedin IS NOT NULL AND linkedin<>'')::int)")


def _leads_rows(uf, segmento, limit, offset=0, sort=None, order="asc"):
    """Linhas de leads (uma por empresa) paginadas. `sort` (whitelist) reordena;
    default = score (contatos completos) desc. Tiebreaker cnpj p/ ordem estável."""
    cnae = SEGMENTO_CNAE.get(segmento, "0151201")
    col = LEADS_SORT.get(sort)
    if col:
        dir_sql = "DESC" if str(order).lower() == "desc" else "ASC"
        order_sql = f"ORDER BY {col} {dir_sql} NULLS LAST, cnpj ASC"
    else:
        order_sql = "ORDER BY score DESC, capital_social DESC NULLS LAST, cnpj ASC"
    # DISTINCT ON (cnpj_basico): uma linha por empresa (JBJ etc. têm dezenas de filiais),
    # mantendo o estabelecimento mais "contactável". whatsapp_rfb = celular inferido do tel RFB.
    return query(
        f"""
        SELECT *, {_LEADS_SCORE} AS score FROM (
            SELECT DISTINCT ON (e.cnpj_basico)
                   COALESCE(NULLIF(em.razao_social, ''), e.nome_fantasia, '(produtor rural)') AS nome,
                   e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
                   m.nome AS municipio, e.uf,
                   e.ddd_1, e.telefone_1, e.correio_eletronico AS email,
                   prospeccao.cel_whats(e.ddd_1||e.telefone_1) AS whatsapp_rfb,
                   NULLIF(TRIM(CONCAT_WS(', ', NULLIF(e.logradouro,''), NULLIF(e.bairro,''))), '') AS endereco,
                   em.porte, em.capital_social,
                   ld.decisor_top AS decisor, ld.tipo AS tipo_lead,
                   ld.situacao_viva, ld.linkedin
            FROM cnpj.estabelecimento_rural e
            JOIN referencia.municipio m ON m.codigo_tom = e.municipio::int
            LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico = e.cnpj_basico
            LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico = e.cnpj_basico
            WHERE e.cnae_fiscal_principal = %(cnae)s
              AND e.situacao_cadastral = '02'
              AND (%(uf)s IS NULL OR e.uf = %(uf)s)
            ORDER BY e.cnpj_basico,
                     (e.correio_eletronico IS NOT NULL) DESC,
                     (e.telefone_1 IS NOT NULL) DESC
        ) sub
        """ + order_sql + """
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"cnae": cnae, "uf": uf, "limit": limit, "offset": offset},
    )


def _leads_total(uf, segmento):
    """Total de empresas distintas no conjunto filtrado (espelha o FROM/WHERE da lista)."""
    cnae = SEGMENTO_CNAE.get(segmento, "0151201")
    rows = query(
        """
        SELECT COUNT(*) AS total FROM (
            SELECT DISTINCT e.cnpj_basico
            FROM cnpj.estabelecimento_rural e
            JOIN referencia.municipio m ON m.codigo_tom = e.municipio::int
            WHERE e.cnae_fiscal_principal = %(cnae)s
              AND e.situacao_cadastral = '02'
              AND (%(uf)s IS NULL OR e.uf = %(uf)s)
        ) x
        """,
        {"cnae": cnae, "uf": uf},
    )
    return rows[0]["total"] if rows else 0


# ---------------------------------------------------------------------------
# FAZENDAS — página de mercado #1 (lead DB: decisor + canais + porte). master_montesiao.
# ---------------------------------------------------------------------------
FAZ_COLS = ("prioridade","nome_fazenda","razao","cnpj_completo","uf","municipio","decisor",
    "operador_jovem","n_decisores","dono_n_fazendas","capital_mi","sinal_genetico","touros_nelore",
    "whatsapp","whats_alta_conf","celular","instagram","followers","porte_digital","email","email_tier",
    "telefone_rfb","dominio","linkedin","canal_recomendado","cnpj_basico")
FAZ_SORT = {"prioridade":"prioridade","capital":"capital_mi","touros":"touros_nelore",
    "followers":"followers","nome":"nome_fazenda","uf":"uf"}

def _faz_where(uf, sinal, canal, q):
    w=["TRUE"]; p={}
    if uf: w.append("uf=%(uf)s"); p["uf"]=uf.upper()
    if sinal: w.append("sinal_genetico=%(sinal)s"); p["sinal"]=sinal
    if canal: w.append("canal_recomendado=%(canal)s"); p["canal"]=canal
    if q:
        w.append("(nome_fazenda ILIKE %(q)s OR razao ILIKE %(q)s OR COALESCE(decisor,'') ILIKE %(q)s OR municipio ILIKE %(q)s)")
        p["q"]=f"%{q}%"
    return " AND ".join(w), p

@app.get("/fazendas", response_class=HTMLResponse)
def fazendas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    resp = templates.TemplateResponse("fazendas.html",
        {"request": request, "user": user, "active": "fazendas", "app_version": APP_VERSION})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/tecnica", response_class=HTMLResponse)
def tecnica_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    resp = templates.TemplateResponse("tecnica.html",
        {"request": request, "user": user, "active": "tecnica", "app_version": APP_VERSION})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/api/farms")
def api_fazendas(uf:str=None, sinal:str=None, canal:str=None, q:str=None,
                 page:int=1, page_size:int=50, sort:str="prioridade", order:str="asc"):
    try:
        page=max(1,page); page_size=min(max(page_size,1),100); off=(page-1)*page_size
        where,p=_faz_where(uf,sinal,canal,q)
        col=FAZ_SORT.get(sort,"prioridade"); od="DESC" if order=="desc" else "ASC"
        rows=query(f"SELECT {','.join(FAZ_COLS)} FROM prospeccao.fazenda_nacional WHERE {where} "
                   f"ORDER BY {col} {od} NULLS LAST, touros_nelore DESC NULLS LAST LIMIT %(lim)s OFFSET %(off)s",
                   {**p,"lim":page_size,"off":off})
        total=scalar(f"SELECT count(*) FROM prospeccao.fazenda_nacional WHERE {where}", p)
        kpi=query(f"SELECT count(*) n, count(*) FILTER (WHERE whatsapp IS NOT NULL) wa, "
                  f"count(*) FILTER (WHERE email IS NOT NULL) em, count(*) FILTER (WHERE instagram IS NOT NULL) ig "
                  f"FROM prospeccao.fazenda_nacional WHERE {where}", p)[0]
        return {"rows":rows,"total":total,"page":page,"page_size":page_size,
                "total_pages":max(1,(total+page_size-1)//page_size),"kpi":kpi}
    except Exception as e:
        return _error(e)

@app.get("/api/farms/export")
def api_fazendas_export(request: Request, uf:str=None, sinal:str=None, canal:str=None, q:str=None):
    """Export GATED: teto de 2000 linhas, marca d'água (usuário) e AUDITORIA. Dado é valioso —
    sem dump infinito do banco."""
    try:
        import io, csv
        EXPORT_CAP=2000
        where,p=_faz_where(uf,sinal,canal,q)
        rows=query(f"SELECT {','.join(FAZ_COLS)} FROM prospeccao.fazenda_nacional WHERE {where} "
                   f"ORDER BY prioridade, touros_nelore DESC NULLS LAST LIMIT {EXPORT_CAP}", p)
        who=(get_current_user(request) or {}).get('sub','?')
        audit(request, "export_fazendas", f"uf={uf} sinal={sinal} canal={canal} q={q}", len(rows))
        buf=io.StringIO()
        buf.write(f"# WiNS Hub Agro - export confidencial - usuario={who} - linhas={len(rows)} (teto {EXPORT_CAP})\n")
        w=csv.DictWriter(buf, fieldnames=list(FAZ_COLS)); w.writeheader()
        for r in rows: w.writerow(r)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition":"attachment; filename=fazendas_wins.csv"})
    except Exception as e:
        return _error(e)


@app.get("/api/leads")
def leads(uf: str = None, segmento: str = "corte", page: int = 1,
                page_size: int = 100, sort: str = None, order: str = "asc"):
    """Compradores potenciais paginados (CNAE corte/leite) com contato.
    Paginação NO SERVIDOR (LIMIT/OFFSET) — a base tem ~180 mil criadores.
    Ordenação opcional por coluna whitelisted (sort/order)."""
    try:
        page = max(1, page)
        page_size = min(max(page_size, 1), 200)
        offset = (page - 1) * page_size
        rows = _leads_rows(uf, segmento, page_size, offset, sort, order)
        total = _leads_total(uf, segmento)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "leads": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    except Exception as e:
        return _error(e)


@app.get("/api/marketplace")
def marketplace(uf: str = None, segmento: str = "corte"):
    """Painel oferta×demanda por UF: criadores (demanda), rebanho/desertos e melhores touros (oferta)."""
    try:
        cnae = SEGMENTO_CNAE.get(segmento, "0151201")
        # criadores = EMPRESAS únicas ativas (1 linha por cnpj_basico), MESMA régua da
        # lista paginada (_leads_rows/_leads_total): dedup por cnpj_basico + join município.
        # Com UF selecionada, "criadores" bate exatamente com o total da lista.
        demanda = query(
            """
            SELECT uf,
                   COUNT(*) AS criadores,
                   COUNT(*) FILTER (WHERE email IS NOT NULL) AS com_email,
                   COUNT(*) FILTER (WHERE telefone_1 IS NOT NULL) AS com_telefone
            FROM (
                SELECT DISTINCT ON (e.cnpj_basico)
                       e.uf, e.correio_eletronico AS email, e.telefone_1
                FROM cnpj.estabelecimento_rural e
                JOIN referencia.municipio m ON m.codigo_tom = e.municipio::int
                WHERE e.cnae_fiscal_principal = %(cnae)s
                  AND e.situacao_cadastral = '02'
                  AND (%(uf)s IS NULL OR e.uf = %(uf)s)
                ORDER BY e.cnpj_basico,
                         (e.correio_eletronico IS NOT NULL) DESC,
                         (e.telefone_1 IS NOT NULL) DESC
            ) sub
            GROUP BY uf
            ORDER BY criadores DESC
            """,
            {"cnae": cnae, "uf": uf},
        )
        rebanho = query(
            """
            SELECT uf,
                   SUM(bovinos) AS rebanho,
                   COUNT(*) FILTER (WHERE classificacao_vet = 'DESERTO VET') AS desertos_vet,
                   COUNT(*) AS municipios
            FROM prospeccao.v_white_space_pecuaria
            WHERE (%(uf)s IS NULL OR uf = %(uf)s)
            GROUP BY uf
            ORDER BY rebanho DESC
            """,
            {"uf": uf},
        )
        # melhor oferta por touro (menor preço) já ordenada por IQGg e limitada no SQL
        oferta_top = query(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (r.id) r.id, r.nome, c.nome AS central,
                       r.fazenda_origem, o.preco_dose_brl AS preco_dose, iq.valor AS iqgg
                FROM mercado.reprodutor r
                JOIN mercado.touro_oferta o ON o.reprodutor_id = r.id
                JOIN catalogo.central c ON c.id = o.central_id
                JOIN (
                    SELECT reprodutor_id, MAX(valor) AS valor
                    FROM mercado.avaliacao WHERE caracteristica_id = %(iqgg)s
                    GROUP BY reprodutor_id
                ) iq ON iq.reprodutor_id = r.id
                WHERE o.preco_dose_brl > 0
                  AND r.raca_id IN %(racas_apt)s   -- só touros coerentes com o segmento
                ORDER BY r.id, o.preco_dose_brl ASC
            ) sub
            ORDER BY iqgg DESC NULLS LAST
            LIMIT 10
            """,
            {"iqgg": IQGG_ID, "racas_apt": _racas_por_finalidade(segmento) or (0,)},  # nunca IN ()
        )
        return {
            "segmento": segmento,
            "uf": uf,
            "demanda": demanda,
            "rebanho": rebanho,
            "oferta_top": oferta_top,
        }
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Mapa — municípios georreferenciados (rebanho + cobertura vet)
# ---------------------------------------------------------------------------
@app.get("/api/map")
def mapa(uf: str = None, min_bovinos: int = 20000):
    try:
        return query(
            """
            SELECT nome AS municipio, uf,
                   latitude AS lat, longitude AS lng,
                   bovinos, cnpj_vet, classificacao_vet
            FROM prospeccao.v_white_space_pecuaria
            WHERE bovinos >= %(mb)s
              AND latitude IS NOT NULL
              AND (%(uf)s IS NULL OR uf = %(uf)s)
            ORDER BY bovinos DESC
            LIMIT 1500
            """,
            {"mb": min_bovinos, "uf": uf},
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Demanda & Expansão — inteligência de mercado a partir de dados antes ociosos:
#   PPM/IBGE (rebanho por município, 2020-2023) -> tendência
#   MapBiomas (pastagem por município) + PPM     -> taxa de lotação
#   CNPJ sócios                                   -> grandes grupos (multi-fazenda)
# ---------------------------------------------------------------------------
@app.get("/api/demanda/tendencia")
def demanda_tendencia(uf: str = None, limit: int = 200, min_reb: int = 30000):
    """Municípios por crescimento de rebanho bovino 2020->2023 (com lat/long p/ mapa)."""
    try:
        return query(
            """
            WITH t AS (
                SELECT codigo_ibge_mun,
                    MAX(efetivo_cabecas) FILTER (WHERE ano_referencia = 2020) AS c20,
                    MAX(efetivo_cabecas) FILTER (WHERE ano_referencia = 2024) AS c24
                FROM prospeccao.ppm_municipio
                WHERE especie_codigo = 'BOV'
                GROUP BY codigo_ibge_mun
            )
            SELECT m.nome AS municipio, m.uf,
                   m.latitude AS lat, m.longitude AS lng,
                   t.c24 AS rebanho, t.c20 AS rebanho_2020,
                   ROUND(100.0 * (t.c24 - t.c20) / NULLIF(t.c20, 0), 1) AS crescimento_pct
            FROM t
            JOIN referencia.municipio m ON m.codigo_ibge = t.codigo_ibge_mun::int
            WHERE t.c20 > 0 AND t.c24 >= %(min_reb)s
              AND (%(uf)s IS NULL OR m.uf = %(uf)s)
            ORDER BY crescimento_pct DESC
            LIMIT %(limit)s
            """,
            {"uf": uf, "limit": min(limit, 1500), "min_reb": min_reb},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/demanda/lotacao")
def demanda_lotacao(uf: str = None, limit: int = 50,
                          min_ha: int = 20000, min_cab: int = 20000):
    """Taxa de lotação (cabeças/ha) cruzando rebanho (PPM) x pastagem (MapBiomas).
    Menor lotação + muita pastagem = pasto ocioso -> potencial de expansão do rebanho."""
    try:
        return query(
            """
            WITH past AS (
                SELECT lower(municipio) AS m, state_acronym AS uf, SUM(area_ha) AS ha
                FROM cobertura.mapbiomas_municipio
                WHERE class_level_2 = '3.1. Pasture' AND ano = 2024
                GROUP BY 1, 2
            ),
            herd AS (
                SELECT lower(m.nome) AS nm, m.uf,
                       m.latitude AS lat, m.longitude AS lng, m.nome AS nome,
                       MAX(p.efetivo_cabecas) AS cab
                FROM prospeccao.ppm_municipio p
                JOIN referencia.municipio m ON m.codigo_ibge = p.codigo_ibge_mun::int
                WHERE p.especie_codigo = 'BOV' AND p.ano_referencia = 2024
                GROUP BY 1, 2, 3, 4, 5
            )
            SELECT h.nome AS municipio, h.uf, h.lat, h.lng,
                   h.cab AS rebanho, ROUND(pa.ha) AS pastagem_ha,
                   ROUND(h.cab / NULLIF(pa.ha, 0), 2) AS lotacao
            FROM herd h
            JOIN past pa ON pa.m = h.nm AND pa.uf = h.uf
            WHERE pa.ha > %(min_ha)s AND h.cab > %(min_cab)s
              AND (%(uf)s IS NULL OR h.uf = %(uf)s)
            ORDER BY lotacao ASC
            LIMIT %(limit)s
            """,
            {"uf": uf, "limit": min(limit, 2000),
             "min_ha": min_ha, "min_cab": min_cab},
        )
    except Exception as e:
        return _error(e)


def _territorio_dados(uf):
    """Agrega a inteligência comercial de um estado (panorama, municípios prioritários
    = Desertos Vet por rebanho, e grandes grupos). Base do relatório territorial."""
    panorama = query(
        """
        SELECT
          (SELECT SUM(efetivo_cabecas) FROM prospeccao.ppm_municipio
             WHERE uf=%(uf)s AND ano_referencia=2024 AND especie_codigo='BOV') AS rebanho_2024,
          (SELECT SUM(efetivo_cabecas) FROM prospeccao.ppm_municipio
             WHERE uf=%(uf)s AND ano_referencia=2020 AND especie_codigo='BOV') AS rebanho_2020,
          (SELECT COUNT(*) FROM prospeccao.v_white_space_pecuaria WHERE uf=%(uf)s) AS municipios,
          (SELECT COUNT(*) FROM prospeccao.v_white_space_pecuaria
             WHERE uf=%(uf)s AND classificacao_vet='DESERTO VET') AS desertos_vet,
          -- COUNT(DISTINCT cnpj_basico): conta EMPRESAS, não filiais (um grupo com 30
          -- filiais = 1 criador), igual à régua dos leads/marketplace. Senão o número
          -- "criadores" do relatório territorial fica inflado vs. o resto da app.
          (SELECT COUNT(DISTINCT cnpj_basico) FROM cnpj.estabelecimento_rural
             WHERE uf=%(uf)s AND situacao_cadastral='02' AND cnae_fiscal_principal='0151201') AS criadores_corte,
          (SELECT COUNT(DISTINCT cnpj_basico) FROM cnpj.estabelecimento_rural
             WHERE uf=%(uf)s AND situacao_cadastral='02' AND cnae_fiscal_principal='0151202') AS criadores_leite,
          (SELECT COUNT(DISTINCT cnpj_basico) FROM cnpj.estabelecimento_rural
             WHERE uf=%(uf)s AND situacao_cadastral='02'
               AND cnae_fiscal_principal IN ('0151201','0151202')
               AND (telefone_1 IS NOT NULL OR correio_eletronico IS NOT NULL)) AS com_contato
        """,
        {"uf": uf},
    )[0]
    prioritarios = query(
        """
        SELECT nome AS municipio, bovinos, cnpj_vet
        FROM prospeccao.v_white_space_pecuaria
        WHERE uf=%(uf)s AND classificacao_vet='DESERTO VET'
        ORDER BY bovinos DESC LIMIT 15
        """,
        {"uf": uf},
    )
    grupos = query(
        """
        SELECT s.nome_socio AS socio, COUNT(DISTINCT s.cnpj_basico) AS fazendas
        FROM cnpj.socio_rural s
        JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico = s.cnpj_basico
        WHERE e.uf=%(uf)s AND s.nome_socio IS NOT NULL
        GROUP BY s.nome_socio HAVING COUNT(DISTINCT s.cnpj_basico) >= 3
        ORDER BY fazendas DESC LIMIT 10
        """,
        {"uf": uf},
    )
    return {"uf": uf, "panorama": panorama, "prioritarios": prioritarios,
            "grandes_grupos": grupos}


@app.get("/api/territorio")
def territorio(uf: str = "TO"):
    """Relatório territorial de um estado para a prospecção (panorama + alvos)."""
    try:
        return _territorio_dados((uf or "TO").upper())
    except Exception as e:
        return _error(e)


@app.get("/api/territorio/pdf")
async def territorio_pdf(uf: str = "TO"):
    """Relatório territorial executivo em PDF (para apresentação comercial)."""
    try:
        uf = (uf or "TO").upper()
        dados = _territorio_dados(uf)
        pdf_bytes = await run_in_threadpool(gerar_relatorio_territorial, uf, dados)
        data_str = datetime.now().strftime("%Y%m%d")
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition":
                     f"attachment; filename=relatorio_territorial_{uf}_{data_str}.pdf"},
        )
    except Exception as e:
        return _error(e)


_WHALES_CACHE = {}


@app.get("/api/demanda/whales")
def demanda_whales(uf: str = None, limit: int = 40):
    """Sócios que controlam várias empresas rurais (grandes grupos = alvo B2B premium).
    Cacheado: a base CNPJ é estática entre ingestões."""
    try:
        key = uf or "BR"
        if key not in _WHALES_CACHE:
            _WHALES_CACHE[key] = query(
                """
                SELECT s.nome_socio AS socio,
                       COUNT(DISTINCT s.cnpj_basico) AS fazendas,
                       string_agg(DISTINCT e.uf, ', ' ORDER BY e.uf) AS ufs
                FROM cnpj.socio_rural s
                JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico = s.cnpj_basico
                WHERE s.nome_socio IS NOT NULL
                  AND (%(uf)s IS NULL OR e.uf = %(uf)s)
                GROUP BY s.nome_socio
                HAVING COUNT(DISTINCT s.cnpj_basico) >= 5
                ORDER BY fazendas DESC
                LIMIT 200
                """,
                {"uf": uf},
            )
        return _WHALES_CACHE[key][: min(limit, 200)]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Dados abertos via API externa (IBGE/SIDRA, BrasilAPI, Banco Central)
# ---------------------------------------------------------------------------
@app.get("/api/externo/leite")
async def externo_leite():
    """Produção de leite por UF (IBGE/SIDRA). Dimensão LEITE real, lado produção."""
    try:
        return await run_in_threadpool(external_apis.producao_leite_uf)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/rebanho")
async def externo_rebanho():
    """Efetivo de bovinos por UF (IBGE/SIDRA)."""
    try:
        return await run_in_threadpool(external_apis.rebanho_bovino_uf)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/indicadores")
async def externo_indicadores():
    """Indicadores de mercado (dólar, Selic) via Banco Central."""
    try:
        return await run_in_threadpool(external_apis.indicadores)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/boi")
async def externo_boi():
    """Cotação do boi gordo (Indicador ESALQ/B3, R$/@)."""
    try:
        return await run_in_threadpool(external_apis.boi_gordo)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/leite-preco")
async def externo_leite_preco():
    """Preço do leite ao produtor (CEPEA, R$/litro, média Brasil)."""
    try:
        return await run_in_threadpool(external_apis.leite_preco)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/graos")
async def externo_graos():
    """Milho e soja (R$/saca)."""
    try:
        return await run_in_threadpool(external_apis.graos)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/abate")
async def externo_abate():
    """Abate de bovinos por UF, último trimestre (IBGE/SIDRA)."""
    try:
        return await run_in_threadpool(external_apis.abate_bovino_uf)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/cnpj/{numero}")
async def externo_cnpj(numero: str):
    """Consulta CNPJ em tempo real (BrasilAPI) — enriquecimento de lead."""
    try:
        return await run_in_threadpool(external_apis.cnpj, numero)
    except Exception as e:
        return _error(e)


@app.get("/api/externo/leite/mapa")
async def externo_leite_mapa(uf: str = None, min_litros: int = 5000):
    """Produção de leite por município (IBGE/SIDRA) + lat/long do banco — para o mapa."""
    try:
        dados = await run_in_threadpool(external_apis.producao_leite_municipios)
        # coords vêm do nosso referencia.municipio (codigo_ibge)
        coords = {
            str(r["codigo_ibge"]): r
            for r in query(
                "SELECT codigo_ibge, uf, latitude, longitude FROM referencia.municipio "
                "WHERE latitude IS NOT NULL"
            )
        }
        out = []
        for d in dados:
            if d["leite_mil_litros"] < min_litros:
                continue
            c = coords.get(str(d["codigo_ibge"]))
            if not c:
                continue
            if uf and c["uf"] != uf:
                continue
            out.append({
                "municipio": d["nome"], "uf": c["uf"],
                "lat": float(c["latitude"]), "lng": float(c["longitude"]),
                "leite_mil_litros": d["leite_mil_litros"],
            })
        out.sort(key=lambda o: o["leite_mil_litros"], reverse=True)
        return out[:1500]
    except Exception as e:
        return _error(e)


@app.get("/api/externo/valor/mapa")
async def externo_valor_mapa(uf: str = None, min_valor: int = 10000):
    """Valor da produção animal por município (IBGE/SIDRA, Mil Reais) + lat/long — mapa de R$."""
    try:
        dados = await run_in_threadpool(external_apis.valor_producao_municipios)
        coords = {
            str(r["codigo_ibge"]): r
            for r in query(
                "SELECT codigo_ibge, uf, latitude, longitude FROM referencia.municipio "
                "WHERE latitude IS NOT NULL"
            )
        }
        out = []
        for d in dados:
            if d["valor_mil_reais"] < min_valor:
                continue
            c = coords.get(str(d["codigo_ibge"]))
            if not c:
                continue
            if uf and c["uf"] != uf:
                continue
            out.append({
                "municipio": d["nome"], "uf": c["uf"],
                "lat": float(c["latitude"]), "lng": float(c["longitude"]),
                "valor_mil_reais": d["valor_mil_reais"],
            })
        out.sort(key=lambda o: o["valor_mil_reais"], reverse=True)
        return out[:1500]
    except Exception as e:
        return _error(e)


@app.get("/api/leads/csv")
def leads_csv(request: Request, uf: str = None, segmento: str = "corte", limit: int = 200000):
    """Exporta o CONJUNTO FILTRADO de leads (não só a página) em CSV para CRM.
    Cap 200 mil: cobre o corte nacional inteiro (~146 mil empresas) já com decisor."""
    base = _leads_rows(uf, segmento, min(limit, 200000), 0)
    if isinstance(base, dict):  # erro
        return base
    # trilha de auditoria do export de PII (LGPD): quem, o quê, quanto, de onde.
    _user = get_current_user(request) or {}
    logger.warning("AUDIT export CSV leads: user=%s uf=%s segmento=%s linhas=%s ip=%s",
                   _user.get("sub", "?"), uf, segmento, len(base),
                   request.headers.get("x-real-ip") or (request.client.host if request.client else "?"))
    import csv as _csv

    buf = io.StringIO()
    # decisor/tipo_lead na frente: o que o vendedor da Monte Sião precisa primeiro
    # (vem de prospeccao.lead_decisor, QSA da Receita ao vivo). email/situacao = contexto.
    cols = ["score", "nome", "decisor", "tipo_lead", "linkedin", "municipio", "uf",
            "ddd_1", "telefone_1", "whatsapp_rfb", "email", "situacao_viva", "cnpj",
            "endereco", "porte", "capital_social"]
    w = _csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for row in base:
        w.writerow(row)
    buf.seek(0)
    data_str = datetime.now().strftime("%Y%m%d")
    seg = segmento + (f"_{uf}" if uf else "")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=leads_{seg}_{data_str}.csv"
        },
    )


# ===================== FILA DE PROSPECÇÃO (ICP genético + contato do decisor) =====================
# celular inferido do telefone-sede via a mesma função dos técnicos (DDI 55 + 6/7/8/9 + 9º dígito)
_PROS_ZAP_RFB = "prospeccao.cel_whats(telefone)"
# WhatsApp recuperado via Serper(decisor+fazenda)/link-externo do IG — só alta confiança (DDD bate UF, ou wa.me/linktree)
_PROS_ZAP_IG = ("(SELECT z.whatsapp FROM prospeccao.cabanha_zap z WHERE z.cnpj=v_fila_prospeccao.cnpj "
                "AND z.whatsapp IS NOT NULL AND (z.uf_match OR z.fonte IN ('wa.me','extlink')))")
# operador jovem que toca a fazenda (filho/administrador 31-50) — quem atende, ≠ patriarca registrado
_PROS_OPERADOR = ("(SELECT cc.nome FROM prospeccao.contato_candidatos cc "
                  "WHERE cc.cnpj_basico=v_fila_prospeccao.cnpj AND cc.faixa BETWEEN 3 AND 5 "
                  "ORDER BY cc.score_alcancavel DESC, cc.faixa LIMIT 1)")
# melhor e-mail VERIFICADO do Hunter (operador jovem primeiro, senão decisor) — só valid/accept_all
_PROS_EMAIL_HUNTER = ("COALESCE("
   "(SELECT ho.email_operador FROM prospeccao.hunter_operador ho WHERE ho.cnpj_basico=v_fila_prospeccao.cnpj "
   "AND ho.email_operador IS NOT NULL AND ho.verif_status IN ('valid','accept_all') LIMIT 1),"
   "(SELECT he.email_decisor FROM prospeccao.hunter_email he WHERE he.cnpj_basico=v_fila_prospeccao.cnpj "
   "AND he.email_decisor IS NOT NULL AND he.verif_status IN ('valid','accept_all') LIMIT 1))")
_PROS_EMAIL_HUNTER_V = ("COALESCE("
   "(SELECT ho.verif_status FROM prospeccao.hunter_operador ho WHERE ho.cnpj_basico=v_fila_prospeccao.cnpj "
   "AND ho.email_operador IS NOT NULL AND ho.verif_status IN ('valid','accept_all') LIMIT 1),"
   "(SELECT he.verif_status FROM prospeccao.hunter_email he WHERE he.cnpj_basico=v_fila_prospeccao.cnpj "
   "AND he.email_decisor IS NOT NULL AND he.verif_status IN ('valid','accept_all') LIMIT 1))")
# melhor canal de abordagem (cascata): WhatsApp > Instagram > e-mail > telefone
_PROS_CANAL = (f"CASE WHEN (whatsapp IS NOT NULL AND whatsapp<>'') OR {_PROS_ZAP_RFB} IS NOT NULL OR {_PROS_ZAP_IG} IS NOT NULL THEN 'whatsapp' "
               "WHEN instagram IS NOT NULL AND instagram<>'' THEN 'instagram' "
               "WHEN email IS NOT NULL AND email<>'' THEN 'email' "
               "WHEN telefone IS NOT NULL AND telefone<>'' THEN 'telefone' ELSE 'nenhum' END")
# score = nº de canais confirmados (decisor + email + whatsapp(confirmado/celular-sede/IG-web) + telefone + instagram + linkedin)
_PROS_SCORE = ("((decisor IS NOT NULL AND decisor <> '')::int "
               f"+ ((email IS NOT NULL AND email <> '') OR {_PROS_EMAIL_HUNTER} IS NOT NULL)::int "
               f"+ ((whatsapp IS NOT NULL AND whatsapp <> '') OR {_PROS_ZAP_RFB} IS NOT NULL OR {_PROS_ZAP_IG} IS NOT NULL)::int "
               "+ (telefone IS NOT NULL AND telefone <> '')::int "
               "+ (instagram IS NOT NULL AND instagram <> '')::int "
               "+ (linkedin IS NOT NULL AND linkedin <> '')::int)")
_PROS_COLS = ("tier, cabanha AS fazenda, fazenda AS razao_social, decisor, uf, municipio, nelore, "
              "email, email_origem, whatsapp, telefone, instagram, linkedin, cnpj, "
              f"{_PROS_OPERADOR} AS operador, {_PROS_EMAIL_HUNTER} AS email_hunter, {_PROS_EMAIL_HUNTER_V} AS email_hunter_v, "
              f"{_PROS_ZAP_RFB} AS whatsapp_rfb, {_PROS_ZAP_IG} AS whatsapp_ig, {_PROS_CANAL} AS melhor_canal, {_PROS_SCORE} AS score")
_PROS_ORDER = (f"ORDER BY {_PROS_SCORE} DESC, (whatsapp IS NOT NULL) DESC, "
               "(email_origem='decisor') DESC, (tier='ALTA') DESC, nelore DESC NULLS LAST")
_PROS_SORT = {"score": _PROS_SCORE, "fazenda": "COALESCE(cabanha,fazenda)", "decisor": "decisor",
              "uf": "uf", "nelore": "nelore", "email": "email", "whatsapp": "whatsapp",
              "instagram": "instagram", "telefone": "telefone"}


def _pros_order(sort, order):
    col = _PROS_SORT.get(sort)
    if not col:
        return _PROS_ORDER
    dir_sql = "DESC" if str(order).lower() == "desc" else "ASC"
    return f"ORDER BY {col} {dir_sql} NULLS LAST, COALESCE(cabanha,fazenda) ASC"


def _pros_where(uf, canal, q, params):
    w = ["ativo"]
    if uf:
        w.append("uf = %(uf)s"); params["uf"] = uf
    if canal == "whatsapp":
        w.append(f"(whatsapp IS NOT NULL OR {_PROS_ZAP_RFB} IS NOT NULL OR {_PROS_ZAP_IG} IS NOT NULL)")
    elif canal == "email_decisor":
        w.append("email_origem = 'decisor'")
    elif canal == "instagram":
        w.append("instagram IS NOT NULL")
    if q:
        w.append("(fazenda ILIKE %(q)s OR decisor ILIKE %(q)s OR cabanha ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    return " AND ".join(w)


@app.get("/api/prospeccao/stats")
def prospeccao_stats():
    """KPIs da fila de prospecção (ICP genético validado e vivo)."""
    return query(
        f"""SELECT count(*) AS total, count(whatsapp) AS com_whatsapp,
                  count(*) FILTER (WHERE whatsapp IS NULL AND {_PROS_ZAP_RFB} IS NOT NULL) AS com_celular_rfb,
                  count(*) FILTER (WHERE whatsapp IS NULL AND {_PROS_ZAP_RFB} IS NULL AND {_PROS_ZAP_IG} IS NOT NULL) AS com_whatsapp_ig,
                  count(*) FILTER (WHERE email_origem='decisor') AS email_decisor,
                  count(instagram) AS com_instagram, count(*) FILTER (WHERE tier='ALTA') AS alta
           FROM prospeccao.v_fila_prospeccao WHERE ativo"""
    )


@app.get("/api/prospeccao")
def prospeccao(uf: str = None, canal: str = None, q: str = None, page: int = 1,
               page_size: int = 50, sort: str = None, order: str = "asc"):
    """Fila de prospecção: ICP genético com decisor + melhor contato por canal."""
    params = {}
    where = _pros_where(uf, canal, q, params)
    tot = query(f"SELECT count(*) AS n FROM prospeccao.v_fila_prospeccao WHERE {where}", params)
    if isinstance(tot, dict):
        return tot
    total = tot[0]["n"]
    ps = min(max(page_size, 1), 200); page = max(page, 1)
    rows = query(
        f"SELECT {_PROS_COLS} FROM prospeccao.v_fila_prospeccao WHERE {where} "
        f"{_pros_order(sort, order)} LIMIT %(lim)s OFFSET %(off)s",
        {**params, "lim": ps, "off": (page - 1) * ps},
    )
    if isinstance(rows, dict):
        return rows
    return {"rows": rows, "total": total, "total_pages": max(1, (total + ps - 1) // ps)}


@app.get("/api/prospeccao/csv")
def prospeccao_csv(uf: str = None, canal: str = None, q: str = None):
    """Exporta a fila filtrada (não só a página) em CSV."""
    params = {}
    where = _pros_where(uf, canal, q, params)
    rows = query(f"SELECT {_PROS_COLS} FROM prospeccao.v_fila_prospeccao WHERE {where} {_PROS_ORDER} LIMIT 5000", params)
    if isinstance(rows, dict):
        return rows
    import csv as _csv
    buf = io.StringIO()
    cols = ["score", "melhor_canal", "tier", "fazenda", "razao_social", "decisor", "uf", "municipio", "nelore",
            "email", "email_origem", "whatsapp", "whatsapp_rfb", "whatsapp_ig", "telefone", "instagram", "linkedin", "cnpj"]
    w = _csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=fila_prospeccao.csv"})


# ===================== CANAL TÉCNICO (veterinário / zootecnista) =====================
# Profissão COERENTE = sinal textual do Serper reforçado pelo sufixo do CRMV (/Z=zootecnista, /V=vet).
# A fila mostra só dado coerente: estabelecimentos de CNAE veterinário (categoria conhecida) e
# tiers acionáveis de corte — fora o ruído urbano (U) e pet (E).
_TEC_PROF = ("COALESCE(NULLIF(profissao,''), "
             "CASE crmv_cat WHEN 'Z' THEN 'zootecnista' WHEN 'V' THEN 'veterinario' END)")
# celular INFERIDO do telefone da Receita via prospeccao.cel_whats(): tira DDI 55, aceita
# assinante 6/7/8/9 (fixo é 2-5), insere o 9º dígito nos antigos de 8 díg → 11 díg WhatsApp-able.
_TEC_ZAP_RFB = "prospeccao.cel_whats(tel_melhor)"
# WhatsApp/telefone PUBLICADO achado no Serper (#3, prospeccao.tecnico_zap) — número REAL da
# empresa (não a reconstrução do RFB). Prioridade sobre o RFB inferido.
_TEC_ZAP_PUB = "(SELECT z.whatsapp FROM prospeccao.tecnico_zap z WHERE z.cnpj14=v_tecnico_fazenda_ui.cnpj14)"
_TEC_TEL_GOOGLE = "(SELECT z.tel_google FROM prospeccao.tecnico_zap z WHERE z.cnpj14=v_tecnico_fazenda_ui.cnpj14)"
# RESGATE (skill check-data-before-external): a view pega 1 estabelecimento por CNPJ, mas e-mail/tel
# podem estar em OUTRO estabelecimento do mesmo cnpj_basico — recupera o melhor entre todos (+126 email/+115 tel).
_TEC_EMAIL_ANY = ("(SELECT max(NULLIF(ev.correio_eletronico,'')) FROM cnpj.estabelecimento_vet ev "
                  "WHERE ev.cnpj_basico=v_tecnico_fazenda_ui.cnpj_basico AND ev.correio_eletronico ~* '@')")
_TEC_TEL_ANY = ("(SELECT max(NULLIF(ev.ddd_1,'')||NULLIF(ev.telefone_1,'')) FROM cnpj.estabelecimento_vet ev "
                "WHERE ev.cnpj_basico=v_tecnico_fazenda_ui.cnpj_basico AND NULLIF(ev.telefone_1,'') IS NOT NULL)")
_TEC_EMAIL = f"COALESCE(email_receita, {_TEC_EMAIL_ANY})"
_TEC_TEL = f"COALESCE(tel_melhor, {_TEC_TEL_ANY})"
# score = nº de canais de contato confirmados (nome real + tel + whatsapp/cel(confirmado/publicado OU celular-RFB) + email + instagram + CRMV)
_TEC_SCORE = ("((nome !~ '^[0-9]' AND nome <> '(sem nome fantasia)')::int "
              f"+ ({_TEC_TEL} IS NOT NULL)::int "
              f"+ (COALESCE(whatsapp,celular) IS NOT NULL OR {_TEC_ZAP_PUB} IS NOT NULL OR {_TEC_ZAP_RFB} IS NOT NULL)::int "
              f"+ ({_TEC_EMAIL} IS NOT NULL)::int "
              "+ (instagram IS NOT NULL)::int "
              "+ COALESCE(crmv_confiavel,false)::int)")
_TEC_COLS = (f"nome, {_TEC_PROF} AS profissao, categoria, tier, municipio, uf, "
             f"{_TEC_TEL} AS telefone, whatsapp, celular, instagram, {_TEC_EMAIL} AS email, site, "
             f"{_TEC_ZAP_RFB} AS whatsapp_rfb, {_TEC_ZAP_PUB} AS zap_pub, {_TEC_TEL_GOOGLE} AS tel_google, "
             # CNAE principal do estabelecimento (matriz) — código bruto p/ o front formatar/descrever
             "(SELECT ev.cnae_fiscal_principal FROM cnpj.estabelecimento_vet ev "
             " WHERE ev.cnpj_basico = v_tecnico_fazenda_ui.cnpj_basico ORDER BY ev.cnpj_ordem LIMIT 1) AS cnae, "
             "crmv_uf, crmv, crmv_cat, crmv_confiavel, sinal_corte, cnpj14 AS cnpj, "
             # vínculo técnico↔fazenda: posse real (C1) + valor-canal por proximidade (C3)
             "tem_fazenda_propria, n_fazendas_posse, fazendas_posse, "
             "bovinos_100km, fazendas_100km, score_canal, "
             # fazendas REAIS (CAR/SICAR, >=100ha) no raio do técnico — coordenada real, não centroide
             "fazendas_real_50km, ha_real_50km, "
             f"{_TEC_SCORE} AS score")
# Fila "agropecuária nível Brasil": todo técnico voltado à pecuária — vet/zootec
# classificado em tier de gado (A/B/C/D corte) OU estabelecimento de CNAE pecuário
# (apoio à pecuária, inseminação, reprodução) em QUALQUER tier (resgata os que o
# heurístico de tier jogou em urbano/pet, ex. Lagoa da Serra, AZ Assessoria Pecuária).
# Fora só o veterinária urbano/pet sem sinal de gado (clínica de cidade/animal de estimação).
_TEC_BASE = ("FROM prospeccao.v_tecnico_fazenda_ui WHERE nome !~ '^[0-9]' AND ("
             "(categoria IS NOT NULL AND tier IN ('A-inseminador','B-corte-alto','C-corte-medio','D-corte-baixo')) "
             "OR categoria IN ('apoio_pecuaria','inseminacao','repro_secundario'))")
_TEC_ORDER = (f"ORDER BY {_TEC_SCORE} DESC, crmv_confiavel DESC NULLS LAST, "
              "(COALESCE(whatsapp,celular) IS NOT NULL) DESC, "
              "(sinal_corte IN ('corte','corte+pet')) DESC, nome")
# colunas ordenáveis pelo cabeçalho (chave do front -> expressão SQL); tiebreaker nome
_TEC_SORT = {"score": _TEC_SCORE, "nome": "nome", "profissao": "profissao", "atividade": "categoria",
             "tier": "tier", "uf": "uf", "telefone": "telefone",
             "whatsapp": "COALESCE(whatsapp,celular)", "instagram": "instagram",
             "crmv": "crmv_confiavel", "sinal": "sinal_corte",
             "fazenda": "tem_fazenda_propria", "canal": "score_canal", "rebanho": "bovinos_100km",
             "fazreal": "fazendas_real_50km"}


def _tec_where(uf, prof, canal, q, params):
    w = []
    if uf:
        w.append("uf = %(uf)s"); params["uf"] = uf
    if prof == "zootecnista":
        w.append("(profissao='zootecnista' OR crmv_cat='Z')")
    elif prof == "veterinario":
        w.append("(profissao='veterinario' OR crmv_cat='V')")
    if canal == "whatsapp":
        w.append(f"(COALESCE(whatsapp,celular) IS NOT NULL OR {_TEC_ZAP_PUB} IS NOT NULL OR {_TEC_ZAP_RFB} IS NOT NULL)")
    elif canal == "whatsapp_pub":     # só o WhatsApp PUBLICADO achado (número real, não reconstrução)
        w.append(f"{_TEC_ZAP_PUB} IS NOT NULL")
    elif canal == "crmv":
        w.append("crmv_confiavel")
    elif canal == "instagram":
        w.append("instagram IS NOT NULL")
    elif canal == "fazenda":          # vet/zootec que POSSUI CNPJ de gado (vínculo real)
        w.append("tem_fazenda_propria")
    elif canal == "canal_alto":       # top-20% por rebanho ao alcance (valor de canal)
        w.append("score_canal >= 80")
    if q:
        w.append("(nome ILIKE %(q)s OR municipio ILIKE %(q)s)"); params["q"] = f"%{q}%"
    return (" AND " + " AND ".join(w)) if w else ""


@app.get("/api/tecnicos/stats")
def tecnicos_stats():
    """KPIs do canal técnico (vet/zootec) — fila coerente."""
    return query(
        f"""SELECT count(*) AS total,
               count(*) FILTER (WHERE {_TEC_PROF}='veterinario') AS veterinarios,
               count(*) FILTER (WHERE {_TEC_PROF}='zootecnista') AS zootecnistas,
               count(*) FILTER (WHERE COALESCE(whatsapp,celular) IS NOT NULL OR {_TEC_ZAP_PUB} IS NOT NULL) AS com_whatsapp,
               count(*) FILTER (WHERE COALESCE(whatsapp,celular) IS NULL AND {_TEC_ZAP_PUB} IS NULL AND {_TEC_ZAP_RFB} IS NOT NULL) AS com_celular_rfb,
               count(*) FILTER (WHERE crmv_confiavel) AS com_crmv,
               count(*) FILTER (WHERE tem_fazenda_propria) AS com_fazenda,
               count(*) FILTER (WHERE score_canal >= 80) AS canal_alto
           {_TEC_BASE}""")


def _tec_order(sort, order):
    col = _TEC_SORT.get(sort)
    if not col:
        return _TEC_ORDER
    dir_sql = "DESC" if str(order).lower() == "desc" else "ASC"
    return f"ORDER BY {col} {dir_sql} NULLS LAST, nome ASC"


@app.get("/api/tecnicos")
def tecnicos(uf: str = None, prof: str = None, canal: str = None, q: str = None,
             page: int = 1, page_size: int = 50, sort: str = None, order: str = "asc"):
    """Fila do canal técnico: vet/zootecnista com nome, categoria, tier, contato e CRMV."""
    params = {}
    where = _tec_where(uf, prof, canal, q, params)
    tot = query(f"SELECT count(*) AS n {_TEC_BASE}{where}", params)
    if isinstance(tot, dict):
        return tot
    total = tot[0]["n"]
    ps = min(max(page_size, 1), 200); page = max(page, 1)
    rows = query(f"SELECT {_TEC_COLS} {_TEC_BASE}{where} {_tec_order(sort, order)} LIMIT %(lim)s OFFSET %(off)s",
                 {**params, "lim": ps, "off": (page - 1) * ps})
    if isinstance(rows, dict):
        return rows
    return {"rows": rows, "total": total, "total_pages": max(1, (total + ps - 1) // ps)}


@app.get("/api/tecnicos/csv")
def tecnicos_csv(uf: str = None, prof: str = None, canal: str = None, q: str = None):
    """Exporta a fila técnica filtrada (não só a página) em CSV."""
    params = {}
    where = _tec_where(uf, prof, canal, q, params)
    rows = query(f"SELECT {_TEC_COLS} {_TEC_BASE}{where} {_TEC_ORDER} LIMIT 20000", params)
    if isinstance(rows, dict):
        return rows
    import csv as _csv
    buf = io.StringIO()
    cols = ["score", "nome", "profissao", "categoria", "cnae", "tier", "municipio", "uf", "telefone",
            "whatsapp", "celular", "zap_pub", "tel_google", "whatsapp_rfb", "instagram", "email", "site", "crmv_uf", "crmv", "crmv_cat",
            "crmv_confiavel", "sinal_corte", "tem_fazenda_propria", "n_fazendas_posse", "fazendas_posse",
            "bovinos_100km", "fazendas_100km", "score_canal", "fazendas_real_50km", "ha_real_50km", "cnpj"]
    w = _csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=tecnicos.csv"})


# fórmula haversine (km) reutilizável: distância entre o centroide do técnico e a fazenda CAR
_HAVERSINE_KM = (
    "6371*acos(least(1,greatest(-1, "
    "sin(radians(%(lat)s))*sin(radians(i.latitude))+"
    "cos(radians(%(lat)s))*cos(radians(i.latitude))*cos(radians(i.longitude-%(lon)s)))))")


@app.get("/api/tecnicos/fazendas")
def tecnicos_fazendas(cnpj: str, raio: float = 50, area_min: float = 100, limit: int = 400):
    """Fazendas CAR concretas (cod_imovel, área, distância) no raio do técnico — drill-down/mapa.
    O técnico é geolocalizado no centroide do município (mv_tecnico_geo); as fazendas vêm da
    base CAR nacional (prospeccao.imovel_rural, ≥area_min ha)."""
    geo = query("SELECT nome, mun, uf, lat, lon FROM prospeccao.mv_tecnico_geo WHERE cnpj14=%(c)s LIMIT 1",
                {"c": cnpj})
    if isinstance(geo, dict):
        return geo
    if not geo:
        return {"tecnico": None, "fazendas": [], "total": 0}
    g = geo[0]
    import math
    dlat = float(raio) / 111.0 + 0.02
    dlon = float(raio) / (111.0 * max(0.2, math.cos(math.radians(float(g["lat"]))))) + 0.02
    p = {"lat": g["lat"], "lon": g["lon"], "raio": raio, "amin": area_min, "lim": min(max(limit, 1), 2000),
         "latlo": float(g["lat"]) - dlat, "lathi": float(g["lat"]) + dlat,
         "lonlo": float(g["lon"]) - dlon, "lonhi": float(g["lon"]) + dlon}
    rows = query(
        f"""SELECT i.codigo_car, i.municipio, i.uf, i.area_total_ha,
                   i.latitude, i.longitude, round(({_HAVERSINE_KM})::numeric,1) AS km
            FROM prospeccao.imovel_rural i
            WHERE i.fonte_principal='SICAR' AND i.area_total_ha >= %(amin)s
              AND i.latitude BETWEEN %(latlo)s AND %(lathi)s
              AND i.longitude BETWEEN %(lonlo)s AND %(lonhi)s
              AND ({_HAVERSINE_KM}) <= %(raio)s
            ORDER BY km ASC LIMIT %(lim)s""", p)
    if isinstance(rows, dict):
        return rows
    return {"tecnico": {"nome": g["nome"], "municipio": g["mun"], "uf": g["uf"],
                        "lat": g["lat"], "lon": g["lon"]},
            "fazendas": rows, "total": len(rows),
            "ha_total": round(sum(float(r["area_total_ha"] or 0) for r in rows))}


def _ndvi_anual(lat, lon):
    """Média anual do NDVI (0-1) via INPE Brazil Data Cube WTSS (MODIS mod13q1, grátis, sem auth).
    Proxy de vigor de pasto: ~0.7 verde/vigoroso, ~0.4 seco/degradado. None se falhar/nodata."""
    try:
        import urllib.request
        import json as _json
        url = ("https://data.inpe.br/bdc/wtss/v4/time_series?coverage=mod13q1-6.1&attributes=NDVI"
               f"&latitude={float(lat)}&longitude={float(lon)}&start_date=2023-06-01&end_date=2024-06-01")
        with urllib.request.urlopen(url, timeout=30) as r:
            d = _json.load(r)
        vals = [v for v in d["result"]["attributes"][0]["values"] if v is not None and v > 0]
        return round(sum(vals) / len(vals) / 10000.0, 3) if vals else None
    except Exception:
        return None


class NdviReq(BaseModel):
    pontos: list = []   # [{codigo_car, lat, lon}]


@app.post("/api/fazendas/ndvi")
def fazendas_ndvi(req: NdviReq):
    """NDVI anual (vigor de pasto) das fazendas pedidas. Cache em imovel_rural.ndvi_medio_12m;
    o que falta busca no WTSS (paralelo) e persiste. Subset sob demanda — 8,3M por API é inviável."""
    import concurrent.futures as _fut
    pts = (req.pontos or [])[:30]
    cars = [p.get("codigo_car") for p in pts if p.get("codigo_car")]
    out = {}
    if cars:
        cached = query("SELECT codigo_car, ndvi_medio_12m FROM prospeccao.imovel_rural "
                       "WHERE codigo_car = ANY(%(c)s) AND ndvi_medio_12m IS NOT NULL", {"c": cars})
        if isinstance(cached, list):
            out = {r["codigo_car"]: r["ndvi_medio_12m"] for r in cached}
    todo = [p for p in pts if p.get("codigo_car") not in out and p.get("lat") and p.get("lon")]

    def work(p):
        return (p.get("codigo_car"), _ndvi_anual(p["lat"], p["lon"]))
    with _fut.ThreadPoolExecutor(max_workers=8) as ex:
        for car, n in ex.map(work, todo):
            if n is not None:
                out[car] = n
                if car:
                    query("UPDATE prospeccao.imovel_rural SET ndvi_medio_12m=%(n)s "
                          "WHERE codigo_car=%(c)s RETURNING 1", {"n": n, "c": car})
    return {"ndvi": out}


@app.get("/api/leads/enriquecido")
async def leads_enriquecido(uf: str = None, segmento: str = "corte", top: int = 5):
    """Leads + enriquecimento automático (BrasilAPI) dos `top` mais contactáveis."""
    try:
        base = _leads_rows(uf, segmento, 50, 0)
        if isinstance(base, dict):  # erro
            return base
        # enriquecimento em PARALELO: cada CNPJ tem timeout de ~15s; em série isso
        # somava até ~150s. Com gather roda tudo concorrente (no threadpool).
        alvos = [l for l in base[: min(top, 10)] if l.get("cnpj")]
        infos = await asyncio.gather(
            *[run_in_threadpool(external_apis.cnpj, l["cnpj"]) for l in alvos],
            return_exceptions=True,
        )
        for lead, info in zip(alvos, infos):
            if isinstance(info, dict) and not info.get("error"):
                lead["enriquecido"] = {
                    "situacao": info.get("situacao"),
                    "abertura": info.get("abertura"),
                    "socios": len(info.get("socios") or []),
                    "capital_social": info.get("capital_social"),
                }
        return base
    except Exception as e:
        return _error(e)


# ===========================================================================
# WiNS Campo — captura de campo (offline-first, PWA em /campo).
# Escreve em fazenda.* e ESPELHA a fêmea no catálogo (mesma lógica do
# load_rebanho_cliente.py) para ela entrar no acasalamento ao vivo. Todos os
# writes são idempotentes por `uuid` (replay seguro do outbox quando o link cai).
# ===========================================================================
from contextlib import contextmanager

# coluna do índice genômico próprio -> caracteristica_id (igual ao loader)
_GENOMICO = {"iqgg": 20, "gpd": 8, "aol": 16, "pes": 12, "mar": 18}


@contextmanager
def _tx():
    """Transação de escrita via pool: commit no sucesso, rollback no erro."""
    pool = _get_pool()
    conn = pool.getconn()
    closed = False
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            closed = True
        raise
    finally:
        try:
            pool.putconn(conn, close=closed)
        except Exception:
            pass


def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


class ClienteIn(BaseModel):
    razao_social: str
    uf: str | None = None
    municipio: str | None = None
    cnpj: str | None = None


class GrupoIn(BaseModel):
    cliente_id: int
    nome: str
    tipo: str | None = "contemporaneo"
    data_inicio: str | None = None


class AnimalIn(BaseModel):
    uuid: str
    cliente_id: int
    sexo: str
    nome: str | None = None
    brinco: str | None = None
    eid: str | None = None
    sisbov: str | None = None
    registro: str | None = None
    raca_id: int | None = None
    composicao_racial: str | None = None
    data_nascimento: str | None = None
    categoria: str | None = None
    grupo_id: int | None = None
    peso_kg: float | None = None
    escore_corporal: float | None = None
    obs: str | None = None
    iqgg: float | None = None
    gpd: float | None = None
    aol: float | None = None
    pes: float | None = None
    mar: float | None = None
    catalogo_id: int | None = None      # ponte: vincula ao reprodutor REAL do catálogo
    pai_catalogo_id: int | None = None  # ponte pelo pai: vincula o touro real (genética + consanguinidade)
    cruzamento_id: int | None = None    # Brief A/F1: bezerro nascido DESTE cruzamento (fecha o loop)
    data_captura: str | None = None     # data em que o registro foi capturado no campo (replay
                                        # offline dias depois não desloca a 1ª pesagem p/ hoje)


class PesagemIn(BaseModel):
    uuid: str
    animal_id: int
    data_medicao: str | None = None
    peso_kg: float | None = None
    escore_corporal: float | None = None
    altura_cm: float | None = None
    grupo_id: int | None = None
    origem: str | None = "manual"
    dispositivo: str | None = None
    obs: str | None = None


class SanitarioIn(BaseModel):
    uuid: str
    tipo: str
    animal_id: int | None = None
    grupo_id: int | None = None
    produto: str | None = None
    data_evento: str | None = None
    proxima_dose: str | None = None
    dose: str | None = None
    via: str | None = None
    responsavel: str | None = None
    obs: str | None = None
    origem_lembrete_id: int | None = None  # se veio da Agenda: fecha o lembrete de origem


class ConcluirLembreteIn(BaseModel):
    id: int


class CruzamentoIn(BaseModel):                 # Feature 2/6
    uuid: str
    cliente_id: int
    vaca_id: int
    touro_id: int | None = None
    touro_nome: str | None = None
    data_cruzamento: str | None = None
    ganho_cria: float | None = None
    prog_iqgg: float | None = None
    prenhez_est: int | None = None
    registrado_por: str | None = "mari"


class DGIn(BaseModel):                          # Brief A — diagnóstico de gestação
    uuid: str                                   # plumbing do outbox (update é idempotente por natureza)
    cruzamento_id: int
    resultado: str                              # prenhe | vazia
    data_dg: str | None = None
    dg_por: str | None = "mari"


class EstacaoIn(BaseModel):                     # Brief B — estação de monta
    uuid: str
    cliente_id: int
    nome: str
    tipo: str | None = "iatf"
    protocolo: str | None = None
    data_inicio: str | None = None


class IatfLoteIn(BaseModel):                    # Brief B — IATF em lote
    uuid: str                                   # uuid do lote (cada matriz vira uuid-{vaca_id})
    estacao_id: int
    cliente_id: int
    touro_id: int
    touro_nome: str | None = None
    grupo_id: int | None = None                 # None = todas as matrizes ativas da fazenda
    data: str | None = None


class ProtocoloIn(BaseModel):                   # Brief B/F1 — protocolo IATF vira agenda
    uuid: str
    estacao_id: int
    cliente_id: int
    grupo_id: int                               # protocolo é aplicado a um LOTE específico
    data_d0: str | None = None


class VendaIn(BaseModel):                       # Feature 4
    uuid: str
    cliente_id: int | None = None
    municipio: str | None = None
    uf: str | None = None
    touro_id: int | None = None
    touro_nome: str | None = None
    data_venda: str | None = None
    tipo: str | None = "semen"                  # semen | embriao | animal
    quantidade: int | None = 1
    valor_unitario: float | None = None
    registrado_por: str | None = "mari"


class AnimalStatusIn(BaseModel):
    animal_id: int
    status: str | None = None              # ativo | descarte | vendido | morto
    eh_doadora: bool | None = None
    motivo_descarte: str | None = None
    data_saida: str | None = None


class MovimentacaoIn(BaseModel):
    uuid: str
    cliente_id: int
    tipo: str                       # entrada | saida | transferencia | nascimento | morte | abate
    data_evento: str | None = None
    gta_numero: str | None = None
    origem: str | None = None
    destino: str | None = None
    finalidade: str | None = None
    quantidade: int | None = None
    obs: str | None = None


# --- validação das capturas de campo (offline manda dado solto; barrar lixo) ---
_TIPO_SANITARIO_OK = {"vacina", "vermífugo", "vermifugo", "medicamento", "exame", "suplemento", "outro"}
_TIPO_MOV_OK = {"entrada", "saida", "saída", "transferencia", "transferência",
                "nascimento", "morte", "abate"}
_STATUS_ANIMAL_OK = {"ativo", "descarte", "vendido", "morto"}


def _cap(s, n=200):
    """Normaliza string: trim + corta no limite; vazio -> None."""
    if not isinstance(s, str):
        return s
    s = s.strip()
    return s[:n] if s else None


def _valida_pesagem(req) -> str | None:
    if req.peso_kg is not None and not (0 < req.peso_kg <= 2000):
        return "peso deve estar entre 0 e 2000 kg"
    if req.escore_corporal is not None and not (1 <= req.escore_corporal <= 9):
        return "escore corporal deve estar entre 1 e 9"
    if req.altura_cm is not None and not (0 < req.altura_cm <= 250):
        return "altura deve estar entre 0 e 250 cm"
    if req.peso_kg is None and req.escore_corporal is None and req.altura_cm is None:
        return "informe ao menos peso, escore ou altura"
    return None


@app.get("/campo", response_class=HTMLResponse)
def campo_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    resp = templates.TemplateResponse("campo.html", {"request": request, "user": user, "app_version": APP_VERSION})
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"  # shell nunca cacheado (mata downgrade do app/WebView)
    return resp


@app.get("/baixar/campo.apk")
def baixar_apk(request: Request):
    """Download do APK (wrapper do app de campo). Exige sessão desde 11/06 (pós-demo):
    o middleware só gateia /api/*, então o check é manual aqui. Quem não está logado
    cai no /login e baixa depois de entrar."""
    if not get_current_user(request):
        return RedirectResponse("/login")
    return FileResponse(
        "frontend/dl/WiNS_Campo.apk",
        media_type="application/vnd.android.package-archive",
        filename="WiNS_Campo.apk",
    )


@app.get("/api/campo/racas")
def campo_racas():
    try:
        return query("SELECT id, sigla, nome FROM catalogo.raca WHERE id IS NOT NULL ORDER BY nome")
    except Exception as e:
        return _error(e)


@app.get("/api/campo/clientes")
def campo_clientes():
    try:
        return query(
            """SELECT c.id, c.razao_social, c.uf, c.municipio,
                      (SELECT count(*) FROM fazenda.animal a WHERE a.cliente_id = c.id) AS n_animais
               FROM fazenda.cliente c ORDER BY c.razao_social""")
    except Exception as e:
        return _error(e)


@app.get("/api/campo/catalogo")
def campo_catalogo(request: Request):
    """Catálogo p/ o cruzamento do app (offline-first): touros do Monte Sião (central 24)
    com DEPs + preço + a arroba + as constantes de prenhez. O app guarda isto no
    localStorage e CALCULA o bezerro previsto no próprio celular (sem rede) — só o PDF
    final precisa de conexão. As vacas vêm do rebanho da fazenda (já sincronizado) ou da
    busca online do catálogo; não bulk-sincronizamos as 45k matrizes."""
    try:
        touros = query(
            f"""
            SELECT r.id, r.nome, r.registro, ra.sigla AS raca_sigla, ra.nome AS raca,
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
            GROUP BY r.id, r.nome, r.registro, ra.sigla, ra.nome
            ORDER BY MAX(a.valor) FILTER (WHERE a.caracteristica_id = {IQGG_ID}) DESC NULLS LAST
            """, {"central": MONTE_SIAO_CENTRAL_ID})
        arroba = (external_apis.boi_gordo() or {}).get("valor")
        for t in touros:
            t["prenhez_est"] = _prenhez_est(t.get("pes"))
            pd = t.get("pd")
            t["ganho_cria"] = round(float(pd) * arroba / 30) if (pd and pd > 0 and arroba) else None
        return {"touros": touros, "arroba": arroba,
                "prenhez_base": PRENHEZ_BASE, "prenhez_coef": PRENHEZ_COEF}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/catalogo/busca")
def campo_catalogo_busca(q: str, sexo: str | None = None, limit: int = 15):
    """Busca um animal nos 104k registros do catálogo (por nome OU registro) p/ a
    PONTE: ao cadastrar no campo, vincula a vaca ao registro real e traz pedigree/genética."""
    try:
        q = (q or "").strip()
        if len(q) < 2:
            return []
        cond = ["(r.nome ILIKE %(q)s OR r.registro ILIKE %(q)s)"]
        params = {"q": f"%{q}%", "lim": min(max(limit, 1), 30)}
        if sexo in ("M", "F"):
            cond.append("r.sexo = %(sx)s"); params["sx"] = sexo
        # pd(5)/pes(12)/preço entram p/ o touro buscado também render ganho/cria e prenhez
        # no cruzamento do app (não só os 12 do Monte Sião). Aditivo — não quebra a ponte.
        rows = query(
            f"""SELECT r.id, r.nome, r.registro, r.sexo, r.raca_id, ra.sigla AS raca_sigla, ra.nome AS raca,
                       r.fazenda_origem, r.pai_nome, r.pai_registro,
                       MAX(CASE WHEN a.caracteristica_id = 20 THEN a.valor END) AS iqgg,
                       MAX(CASE WHEN a.caracteristica_id = 8  THEN a.valor END) AS gpd,
                       MAX(CASE WHEN a.caracteristica_id = 16 THEN a.valor END) AS aol,
                       MAX(CASE WHEN a.caracteristica_id = 5  THEN a.valor END) AS pd,
                       MAX(CASE WHEN a.caracteristica_id = 12 THEN a.valor END) AS pes,
                       (SELECT MIN(preco_dose_brl) FROM mercado.touro_oferta o
                          WHERE o.reprodutor_id = r.id AND o.preco_dose_brl > 0) AS preco_dose
                  FROM mercado.reprodutor r
                  JOIN catalogo.raca ra ON ra.id = r.raca_id
                  LEFT JOIN mercado.avaliacao a ON a.reprodutor_id = r.id
                        AND a.caracteristica_id IN (20, 8, 16, 5, 12)
                 WHERE {' AND '.join(cond)}
                 GROUP BY r.id, r.nome, r.registro, r.sexo, r.raca_id, ra.sigla, ra.nome,
                          r.fazenda_origem, r.pai_nome, r.pai_registro
                 ORDER BY (MAX(CASE WHEN a.caracteristica_id = 20 THEN a.valor END)) DESC NULLS LAST, r.nome
                 LIMIT %(lim)s""",
            params)
        # ganho/cria do touro buscado (mesma fórmula do catálogo) p/ a tela do app
        if sexo == "M" and rows:
            arroba = (external_apis.boi_gordo() or {}).get("valor")
            for t in rows:
                pd = t.get("pd")
                t["ganho_cria"] = round(float(pd) * arroba / 30) if (pd and pd > 0 and arroba) else None
                t["prenhez_est"] = _prenhez_est(t.get("pes"))
        return rows
    except Exception as e:
        return _error(e)


def _ocr_brinco(image_bytes: bytes) -> list:
    """OCR do número do brinco a partir de uma foto (Fase 2). Pré-processa com Pillow
    (cinza, contraste, upscale) e roda Tesseract com whitelist de dígitos. Devolve
    candidatos (mais longos primeiro) — a UI faz o usuário CONFIRMAR (nunca confia cego)."""
    import re as _re
    import pytesseract
    from PIL import Image, ImageOps
    # trava contra "decompression bomb" (imagem pequena que expande p/ giga-pixels)
    Image.MAX_IMAGE_PIXELS = 40_000_000   # ~40MP, folgado p/ foto de celular
    img = Image.open(io.BytesIO(image_bytes))
    img.verify()                          # rejeita arquivo malformado antes de decodificar
    img = Image.open(io.BytesIO(image_bytes))  # verify() consome o stream; reabre p/ usar
    if img.mode != "L":
        img = img.convert("L")
    w, h = img.size
    if max(w, h) < 1200:                       # upscale fotos pequenas ajuda muito o OCR
        s = 1200.0 / max(w, h)
        img = img.resize((int(w * s), int(h * s)))
    img = ImageOps.autocontrast(img)
    cands = []
    # passe 1: só dígitos (brinco visual costuma ser numérico)
    for psm in ("11", "7", "6"):
        txt = pytesseract.image_to_string(
            img, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789")
        for n in _re.findall(r"\d{1,8}", txt):
            if n not in cands:
                cands.append(n)
    # passe 2: alfanumérico (brincos com prefixo de letra)
    txt2 = pytesseract.image_to_string(img, config="--psm 11")
    for t in _re.findall(r"[A-Za-z0-9]{2,12}", txt2):
        t = t.upper()
        if any(c.isdigit() for c in t) and t not in cands:
            cands.append(t)
    cands.sort(key=len, reverse=True)
    return cands[:6]


@app.post("/api/campo/ocr/brinco")
async def campo_ocr_brinco(foto: UploadFile = File(...)):
    """Lê o número do brinco de uma foto (câmera do app). Retorna candidatos p/ o usuário escolher."""
    try:
        # só aceita imagem (o cliente comprime p/ JPEG antes de enviar)
        ctype = (foto.content_type or "").lower()
        if ctype and not ctype.startswith("image/"):
            return {"error": "envie uma imagem (JPEG/PNG)"}
        data = await foto.read()
        if not data:
            return {"error": "foto vazia"}
        if len(data) > 12_000_000:
            return {"error": "imagem muito grande (máx 12MB)"}
        cands = await run_in_threadpool(_ocr_brinco, data)
        return {"candidatos": cands}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/cliente")
def campo_cliente(req: ClienteIn):
    try:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.cliente WHERE razao_social = %(r)s",
                        {"r": req.razao_social})
            row = cur.fetchone()
            if row:
                return {"id": row["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.cliente (razao_social, uf, municipio, cnpj, criado_em)
                   VALUES (%(r)s,%(uf)s,%(m)s,%(c)s, now()) RETURNING id""",
                {"r": req.razao_social, "uf": req.uf, "m": req.municipio, "c": req.cnpj})
            return {"id": cur.fetchone()["id"], "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/grupos")
def campo_grupos(cliente_id: int):
    try:
        return query(
            """SELECT id, nome, tipo, data_inicio FROM fazenda.grupo_manejo
               WHERE cliente_id = %(c)s ORDER BY criado_em DESC""", {"c": cliente_id})
    except Exception as e:
        return _error(e)


@app.post("/api/campo/grupo")
def campo_grupo(req: GrupoIn):
    try:
        with _tx() as conn:
            cur = _cur(conn)
            # idempotência por (cliente, nome): retry/duplo-toque devolve o lote existente
            # em vez de criar duplicata (única escrita do campo que não tinha uuid).
            cur.execute(
                """SELECT id FROM fazenda.grupo_manejo
                    WHERE cliente_id = %(c)s AND lower(trim(nome)) = lower(trim(%(n)s))""",
                {"c": req.cliente_id, "n": req.nome})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.grupo_manejo (cliente_id, nome, tipo, data_inicio, criado_em)
                   VALUES (%(c)s,%(n)s,%(t)s,%(d)s, now()) RETURNING id""",
                {"c": req.cliente_id, "n": req.nome, "t": req.tipo, "d": req.data_inicio or None})
            return {"id": cur.fetchone()["id"], "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/resumo")
def campo_resumo(cliente_id: int):
    try:
        return query(
            """SELECT
                 (SELECT count(*) FROM fazenda.animal WHERE cliente_id = %(c)s) AS animais,
                 (SELECT count(*) FROM fazenda.animal WHERE cliente_id = %(c)s AND sexo = 'F') AS femeas,
                 (SELECT count(*) FROM fazenda.medicao m JOIN fazenda.animal a ON a.id = m.animal_id
                    WHERE a.cliente_id = %(c)s) AS pesagens,
                 (SELECT count(*) FROM fazenda.grupo_manejo WHERE cliente_id = %(c)s) AS grupos""",
            {"c": cliente_id})[0]
    except Exception as e:
        return _error(e)


@app.get("/api/campo/animais")
def campo_animais(cliente_id: int):
    try:
        return query(
            """SELECT a.id, a.nome, a.brinco, a.eid, a.sexo, a.peso_atual_kg, a.escore_corporal,
                      ra.sigla AS raca, a.reprodutor_espelho_id,
                      COALESCE(a.status, 'ativo') AS status, a.eh_doadora, a.motivo_descarte,
                      (SELECT max(data_medicao) FROM fazenda.medicao m WHERE m.animal_id = a.id) AS ultima_medicao,
                      -- IQGg próprio (espelho genotipado) p/ a vaca entrar no cálculo offline do cruzamento
                      (SELECT MAX(av.valor) FROM mercado.avaliacao av
                         WHERE av.reprodutor_id = a.reprodutor_espelho_id AND av.caracteristica_id = 20) AS iqgg
               FROM fazenda.animal a LEFT JOIN catalogo.raca ra ON ra.id = a.raca_id
               WHERE a.cliente_id = %(c)s
               ORDER BY (COALESCE(a.status,'ativo') <> 'ativo'), a.coletado_em DESC LIMIT 500""",
            {"c": cliente_id})
    except Exception as e:
        return _error(e)


@app.post("/api/campo/animal/status")
def campo_animal_status(req: AnimalStatusIn):
    """Marca descarte/venda/morte (ciclo de vida) e/ou doadora de uma fêmea.
    Reativar (status=ativo) limpa motivo/data de saída."""
    try:
        sets, params = [], {"a": req.animal_id}
        if req.status is not None:
            st = req.status.lower()
            if st not in _STATUS_ANIMAL_OK:
                return {"error": "status inválido"}
            sets.append("status = %(st)s"); params["st"] = st
            if st == "ativo":
                sets.append("data_saida = NULL")
                sets.append("motivo_descarte = NULL")
            else:
                sets.append("data_saida = COALESCE(%(ds)s::date, current_date)")
                params["ds"] = req.data_saida or None
                sets.append("motivo_descarte = %(mt)s")
                params["mt"] = _cap(req.motivo_descarte, 120)
        if req.eh_doadora is not None:
            sets.append("eh_doadora = %(dd)s"); params["dd"] = bool(req.eh_doadora)
        if not sets:
            return {"error": "nada a atualizar"}
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(f"UPDATE fazenda.animal SET {', '.join(sets)} WHERE id = %(a)s RETURNING id", params)
            row = cur.fetchone()
            return {"id": row["id"], "ok": True} if row else {"error": "animal não encontrado"}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/animal")
def campo_animal(req: AnimalIn):
    try:
        sexo = (req.sexo or "").upper()[:1]
        if sexo not in ("M", "F"):
            return {"error": "sexo deve ser M ou F"}
        if req.peso_kg is not None and not (0 < req.peso_kg <= 2000):
            return {"error": "peso deve estar entre 0 e 2000 kg"}
        if req.escore_corporal is not None and not (1 <= req.escore_corporal <= 9):
            return {"error": "escore corporal deve estar entre 1 e 9"}
        req.nome = _cap(req.nome, 120)
        req.brinco = _cap(req.brinco, 40)
        req.sisbov = _cap(req.sisbov, 20)
        req.categoria = _cap(req.categoria, 60)
        req.obs = _cap(req.obs, 500)
        with _tx() as conn:
            cur = _cur(conn)
            # idempotência: uuid já cadastrado -> devolve o mesmo registro
            cur.execute("SELECT id, reprodutor_espelho_id FROM fazenda.animal WHERE uuid = %(u)s",
                        {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"animal_id": ex["id"], "reprodutor_id": ex["reprodutor_espelho_id"], "novo": False}

            reg = req.registro
            cur.execute(
                """INSERT INTO fazenda.animal
                     (cliente_id, brinco, eid, sisbov, registro_associacao, nome, especie_codigo,
                      raca_id, composicao_racial, sexo, data_nascimento, categoria, status,
                      grupo_id, peso_atual_kg, escore_corporal, obs, uuid, cruzamento_id, coletado_em)
                   VALUES (%(cli)s,%(br)s,%(eid)s,%(sis)s,%(reg)s,%(nome)s,'BOV',
                      %(raca)s,%(comp)s,%(sexo)s,%(nasc)s,%(cat)s,'ativo',
                      %(grp)s,%(peso)s,%(ecc)s,%(obs)s,%(uuid)s,%(cruz)s, now()) RETURNING id""",
                {"cli": req.cliente_id, "br": req.brinco, "eid": req.eid, "sis": req.sisbov,
                 "reg": reg, "nome": req.nome, "raca": req.raca_id, "comp": req.composicao_racial,
                 "sexo": sexo, "nasc": req.data_nascimento or None, "cat": req.categoria,
                 "grp": req.grupo_id, "peso": req.peso_kg, "ecc": req.escore_corporal,
                 "obs": req.obs, "uuid": req.uuid, "cruz": req.cruzamento_id})
            animal_id = cur.fetchone()["id"]

            # Brief A/F1: bezerro de um cruzamento registrado herda o touro como pai (pedigree automático)
            if req.cruzamento_id and not req.pai_catalogo_id:
                cur.execute("SELECT touro_id FROM fazenda.cruzamento WHERE id = %(c)s", {"c": req.cruzamento_id})
                crow = cur.fetchone()
                if crow and crow.get("touro_id"):
                    req.pai_catalogo_id = crow["touro_id"]

            # pai (touro) escolhido na busca -> vincula o pai REAL e guarda sua genética
            pai = None
            if req.pai_catalogo_id:
                # lê com o cursor da própria transação (NÃO query(), que pegaria 2ª conexão do pool)
                cur.execute(
                    """SELECT r.id, r.nome, r.registro,
                              MAX(CASE WHEN a.caracteristica_id = 20 THEN a.valor END) AS iqgg
                         FROM mercado.reprodutor r
                         LEFT JOIN mercado.avaliacao a ON a.reprodutor_id = r.id AND a.caracteristica_id = 20
                        WHERE r.id = %(id)s GROUP BY r.id, r.nome, r.registro""",
                    {"id": req.pai_catalogo_id})
                prow = cur.fetchall()
                pai = prow[0] if prow else None
                if pai:
                    cur.execute(
                        """UPDATE fazenda.animal
                             SET pai_reprodutor_id = %(p)s, pai_nome_externo = %(n)s,
                                 pai_registro_externo = %(reg)s
                           WHERE id = %(a)s""",
                        {"p": pai["id"], "n": pai.get("nome"), "reg": pai.get("registro"), "a": animal_id})

            # primeira pesagem do cadastro também vira histórico em medicao
            if req.peso_kg is not None or req.escore_corporal is not None:
                cur.execute(
                    """INSERT INTO fazenda.medicao
                         (animal_id, data_medicao, peso_kg, escore_corporal, grupo_id, origem, medido_em)
                       VALUES (%(a)s, COALESCE(%(d)s::date, current_date), %(p)s, %(e)s, %(g)s, 'manual', now())""",
                    {"a": animal_id, "p": req.peso_kg, "e": req.escore_corporal, "g": req.grupo_id,
                     "d": req.data_captura or None})

            reprodutor_id = None
            # 1) PONTE: animal escolhido na busca do catálogo -> vincula ao registro REAL
            #    (traz pedigree/genética de verdade; não cria espelho duplicado)
            if req.catalogo_id:
                cur.execute("SELECT id FROM mercado.reprodutor WHERE id = %(c)s", {"c": req.catalogo_id})
                if cur.fetchone():
                    reprodutor_id = req.catalogo_id
                    cur.execute("UPDATE fazenda.animal SET reprodutor_espelho_id=%(r)s WHERE id=%(a)s",
                                {"r": reprodutor_id, "a": animal_id})
            # 2) senão, espelha a fêmea no catálogo p/ entrar no acasalamento (igual ao loader)
            elif sexo == "F" and req.raca_id is not None:
                # sufixo do uuid no registro auto-gerado: dois animais distintos com o MESMO
                # brinco+raça na mesma fazenda (erro de digitação / re-cadastro) ganham espelhos
                # SEPARADOS em vez de o 2º sobrescrever a genética do 1º via ON CONFLICT.
                # (replay do outbox já é deduplicado antes, pela checagem de uuid no topo.)
                registro_m = reg or (f"FZ{req.cliente_id}-{req.brinco}-{req.uuid[:6]}" if req.brinco
                                     else f"FZ{req.cliente_id}-U{req.uuid[:8]}")
                cur.execute("SELECT razao_social, uf, municipio FROM fazenda.cliente WHERE id = %(c)s",
                            {"c": req.cliente_id})
                cli = cur.fetchone() or {}
                prog = f"fazenda_{req.cliente_id}"
                campos = {"reg": registro_m, "nome": req.nome or registro_m, "raca": req.raca_id,
                          "faz": cli.get("razao_social"), "uf": cli.get("uf"), "mun": cli.get("municipio"),
                          "pai_reg": (pai.get("registro") if pai else None),
                          "pai_nome": (pai.get("nome") if pai else None),
                          "ref": f"Rebanho {cli.get('razao_social')}", "prog": prog}
                # registro REAL pode colidir com animal do catálogo (104k) ou de outra fazenda.
                # Nesse caso VINCULA (mesma semântica da ponte catalogo_id) — nunca renomear/
                # repedigrear/regravar avaliação de um animal que não é espelho DESTA fazenda.
                cur.execute(
                    "SELECT id, fonte_programa FROM mercado.reprodutor WHERE registro=%(reg)s AND raca_id=%(raca)s",
                    {"reg": registro_m, "raca": req.raca_id})
                exist = cur.fetchone()
                espelho_proprio = False
                if exist and exist.get("fonte_programa") == prog:
                    # re-cadastro/correção do espelho da própria fazenda: atualiza no lugar
                    reprodutor_id = exist["id"]
                    espelho_proprio = True
                    cur.execute(
                        """UPDATE mercado.reprodutor
                              SET nome=%(nome)s, fazenda_origem=%(faz)s, uf=%(uf)s, municipio=%(mun)s,
                                  pai_registro=%(pai_reg)s, pai_nome=%(pai_nome)s
                            WHERE id=%(id)s""", {**campos, "id": reprodutor_id})
                elif exist:
                    reprodutor_id = exist["id"]  # animal real do catálogo -> só vincula
                else:
                    cur.execute(
                        """INSERT INTO mercado.reprodutor
                             (registro, nome, especie_codigo, raca_id, sexo, fazenda_origem, uf, municipio,
                              pai_registro, pai_nome, fonte_referencia, fonte_programa, coletado_em)
                           VALUES (%(reg)s,%(nome)s,'BOV',%(raca)s,'F',%(faz)s,%(uf)s,%(mun)s,
                              %(pai_reg)s,%(pai_nome)s,%(ref)s,%(prog)s, now())
                           ON CONFLICT (registro, raca_id) DO NOTHING
                           RETURNING id""", campos)
                    row = cur.fetchone()
                    if row:
                        reprodutor_id = row["id"]
                        espelho_proprio = True
                    else:
                        # corrida: outro insert ganhou entre o SELECT e o INSERT -> vincula
                        cur.execute(
                            "SELECT id FROM mercado.reprodutor WHERE registro=%(reg)s AND raca_id=%(raca)s",
                            {"reg": registro_m, "raca": req.raca_id})
                        reprodutor_id = cur.fetchone()["id"]

                # índices genômicos próprios da vaca -> avaliacao (regrava)
                # SÓ no espelho da própria fazenda — animal real do catálogo mantém a
                # avaliação genômica oficial intacta.
                idx = {k: getattr(req, k) for k in _GENOMICO if getattr(req, k) is not None}
                if not espelho_proprio:
                    pass
                elif idx:
                    cur.execute(
                        "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%(r)s AND caracteristica_id = ANY(%(ids)s)",
                        {"r": reprodutor_id, "ids": [_GENOMICO[k] for k in idx]})
                    for k, v in idx.items():
                        cur.execute(
                            """INSERT INTO mercado.avaliacao
                                 (reprodutor_id, caracteristica_id, valor, eh_genomica, coletado_em)
                               VALUES (%(r)s,%(c)s,%(v)s,true, now())""",
                            {"r": reprodutor_id, "c": _GENOMICO[k], "v": v})
                # mérito ESTIMADO pela média de parentesco (média da raça + metade do pai),
                # quando a vaca não foi genotipada mas o pai é conhecido. eh_genomica=false (é estimativa).
                elif pai and pai.get("iqgg") is not None:
                    raca_mean = _media_iqgg_raca(req.raca_id, cur=cur) or 0
                    dam_est = round(0.5 * float(raca_mean) + 0.5 * float(pai["iqgg"]), 2)
                    cur.execute("DELETE FROM mercado.avaliacao WHERE reprodutor_id=%(r)s AND caracteristica_id=20",
                                {"r": reprodutor_id})
                    cur.execute(
                        """INSERT INTO mercado.avaliacao (reprodutor_id, caracteristica_id, valor, eh_genomica, coletado_em)
                           VALUES (%(r)s, 20, %(v)s, false, now())""",
                        {"r": reprodutor_id, "v": dam_est})

                # gravamos avaliação nova p/ esta raça -> baseline cacheado ficou velho
                if espelho_proprio and (idx or (pai and pai.get("iqgg") is not None)):
                    _invalida_media_raca(req.raca_id)

                cur.execute("UPDATE fazenda.animal SET reprodutor_espelho_id=%(r)s WHERE id=%(a)s",
                            {"r": reprodutor_id, "a": animal_id})

            return {"animal_id": animal_id, "reprodutor_id": reprodutor_id, "novo": True}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/cruzamento")
def campo_cruzamento(req: CruzamentoIn):
    """Registra um acasalamento efetivado no campo (Feature 2). Idempotente por uuid
    (replay seguro do outbox). Alimenta o gráfico de evolução genética (Feature 6)."""
    try:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id, estacao_monta FROM fazenda.cruzamento WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "estacao_monta": ex["estacao_monta"], "novo": False}
            # espelho da vaca (liga o cruzamento à genética da matriz), se já espelhada
            cur.execute("SELECT reprodutor_espelho_id FROM fazenda.animal WHERE id = %(a)s", {"a": req.vaca_id})
            arow = cur.fetchone()
            vaca_espelho = arow["reprodutor_espelho_id"] if arow else None
            # data + estação de monta (semestre) calculadas no banco, num único INSERT
            cur.execute(
                """INSERT INTO fazenda.cruzamento
                     (uuid, cliente_id, vaca_id, vaca_espelho_id, touro_id, touro_nome,
                      data_cruzamento, estacao_monta, ganho_cria, prog_iqgg, prenhez_est,
                      registrado_por, coletado_em)
                   SELECT %(u)s,%(cli)s,%(v)s,%(ve)s,%(t)s,%(tn)s, d.dt,
                          EXTRACT(YEAR FROM d.dt)::int || '-' ||
                            CASE WHEN EXTRACT(MONTH FROM d.dt) <= 6 THEN '1' ELSE '2' END,
                          %(g)s,%(pi)s,%(pe)s,%(rp)s, now()
                     FROM (SELECT COALESCE(%(dt)s::date, current_date) AS dt) d
                   RETURNING id, estacao_monta""",
                {"u": req.uuid, "cli": req.cliente_id, "v": req.vaca_id, "ve": vaca_espelho,
                 "t": req.touro_id, "tn": _cap(req.touro_nome, 120), "dt": req.data_cruzamento or None,
                 "g": req.ganho_cria, "pi": req.prog_iqgg, "pe": req.prenhez_est,
                 "rp": req.registrado_por or "mari"})
            row = cur.fetchone()
            return {"id": row["id"], "estacao_monta": row["estacao_monta"], "novo": True}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/cruzamento/dg")
def campo_cruzamento_dg(req: DGIn):
    """Registra o diagnóstico de gestação de um cruzamento (Brief A — o REALIZADO da
    previsão de prenhez). UPDATE idempotente por natureza (regravar o mesmo valor é seguro)."""
    try:
        res = (req.resultado or "").lower()
        if res not in ("prenhe", "vazia", "pendente"):
            return {"error": "resultado deve ser 'prenhe' ou 'vazia'"}
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE fazenda.cruzamento
                     SET resultado = %(r)s,
                         data_dg = COALESCE(%(d)s::date, current_date),
                         dg_por = %(por)s
                   WHERE id = %(id)s RETURNING id, resultado""",
                {"r": res, "d": req.data_dg or None, "por": req.dg_por or "mari", "id": req.cruzamento_id})
            row = cur.fetchone()
            if not row:
                return {"error": "cruzamento não encontrado"}
            return {"id": row["id"], "resultado": row["resultado"], "ok": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/cruzamento/pendentes-dg")
def campo_dg_pendentes(cliente_id: int):
    """Cruzamentos aguardando diagnóstico de gestação (resultado='pendente')."""
    try:
        rows = query(
            """SELECT c.id, c.touro_nome, c.data_cruzamento,
                      (current_date - c.data_cruzamento) AS dias,
                      a.nome AS vaca_nome, a.brinco
                 FROM fazenda.cruzamento c
                 LEFT JOIN fazenda.animal a ON a.id = c.vaca_id
                WHERE c.cliente_id = %(c)s AND COALESCE(c.resultado, 'pendente') = 'pendente'
                ORDER BY c.data_cruzamento ASC""",
            {"c": cliente_id})
        return {"pendentes": rows}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/cruzamento/prenhes")
def campo_cruzamento_prenhes(cliente_id: int):
    """Cruzamentos confirmados PRENHE ainda sem bezerro registrado (Brief A/F1) — p/ vincular
    o nascimento ao cruzamento no cadastro do animal."""
    try:
        rows = query(
            """SELECT c.id, c.touro_nome, c.data_cruzamento,
                      a.nome AS vaca_nome, a.brinco
                 FROM fazenda.cruzamento c
                 LEFT JOIN fazenda.animal a ON a.id = c.vaca_id
                WHERE c.cliente_id = %(c)s AND c.resultado = 'prenhe'
                  AND NOT EXISTS (SELECT 1 FROM fazenda.animal f WHERE f.cruzamento_id = c.id)
                ORDER BY c.data_cruzamento ASC""",
            {"c": cliente_id})
        return {"prenhes": rows}
    except Exception as e:
        return _error(e)


@app.get("/api/aprendizado/peso")
def aprendizado_peso(cliente_id: int = None):
    """Ganho REALIZADO (Brief A/F1): peso médio dos bezerros nascidos de cada touro
    (ligados via cruzamento_id) — a 2ª dimensão do previsto × realizado."""
    try:
        cond = "f.peso_atual_kg IS NOT NULL"
        p = {}
        if cliente_id:
            cond += " AND c.cliente_id = %(c)s"
            p["c"] = cliente_id
        por_touro = query(
            f"""SELECT c.touro_id, c.touro_nome,
                       COUNT(f.id) AS n_filhos,
                       ROUND(AVG(f.peso_atual_kg)) AS peso_medio
                 FROM fazenda.cruzamento c
                 JOIN fazenda.animal f ON f.cruzamento_id = c.id
                WHERE {cond}
                GROUP BY c.touro_id, c.touro_nome
                ORDER BY peso_medio DESC NULLS LAST""", p)
        return {"por_touro": por_touro, "tem_dados": len(por_touro) > 0}
    except Exception as e:
        return _error(e)


@app.get("/api/aprendizado/prenhez")
def aprendizado_prenhez(cliente_id: int = None):
    """Reconciliação previsto × realizado de prenhez (Brief A — o motor aprendendo).
    Por touro + agregado, com sugestão de calibração do BASE via shrinkage p/ o prior."""
    try:
        cond = "c.resultado IN ('prenhe','vazia')"
        p = {}
        if cliente_id:
            cond += " AND c.cliente_id = %(c)s"
            p["c"] = cliente_id
        por_touro = query(
            f"""SELECT c.touro_id, c.touro_nome,
                       COUNT(*) AS n,
                       COUNT(*) FILTER (WHERE c.resultado='prenhe') AS prenhes,
                       ROUND(100.0*COUNT(*) FILTER (WHERE c.resultado='prenhe')/NULLIF(COUNT(*),0)) AS prenhez_real,
                       ROUND(AVG(c.prenhez_est)) AS prenhez_prev
                 FROM fazenda.cruzamento c
                WHERE {cond}
                GROUP BY c.touro_id, c.touro_nome
                ORDER BY n DESC, prenhez_real DESC NULLS LAST""", p)
        overall = query(
            f"""SELECT COUNT(*) AS n,
                       ROUND(100.0*COUNT(*) FILTER (WHERE c.resultado='prenhe')/NULLIF(COUNT(*),0)) AS prenhez_real,
                       ROUND(AVG(c.prenhez_est)) AS prenhez_prev
                 FROM fazenda.cruzamento c WHERE {cond}""", p)
        o = overall[0] if overall else {}
        n = o.get("n") or 0
        calib = None
        if n and o.get("prenhez_real") is not None and o.get("prenhez_prev") is not None:
            k = 20  # peso do prior: até ~20 DGs confia mais no chute (não persegue ruído)
            ajuste = (o["prenhez_real"] - o["prenhez_prev"])
            base_sugerida = round(PRENHEZ_BASE + (n / (n + k)) * ajuste)
            calib = {"base_atual": PRENHEZ_BASE, "base_sugerida": base_sugerida,
                     "confianca": "alta" if n >= 30 else ("média" if n >= 10 else "baixa")}
        return {"por_touro": por_touro, "overall": o, "calibracao": calib}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/estacao")
def campo_estacao(req: EstacaoIn):
    """Cria uma estação de monta (Brief B). Idempotente por uuid."""
    try:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.estacao_monta WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.estacao_monta (uuid, cliente_id, nome, tipo, protocolo, data_inicio, coletado_em)
                   VALUES (%(u)s,%(c)s,%(n)s,%(t)s,%(p)s, COALESCE(%(d)s::date, current_date), now()) RETURNING id""",
                {"u": req.uuid, "c": req.cliente_id, "n": _cap(req.nome, 80), "t": (req.tipo or "iatf"),
                 "p": _cap(req.protocolo, 60), "d": req.data_inicio or None})
            return {"id": cur.fetchone()["id"], "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/estacoes")
def campo_estacoes(cliente_id: int):
    """Lista as estações de monta da fazenda + nº de matrizes já inseminadas em cada."""
    try:
        return {"estacoes": query(
            """SELECT e.id, e.nome, e.tipo, e.protocolo, e.data_inicio, e.status,
                      (SELECT COUNT(*) FROM fazenda.cruzamento c WHERE c.estacao_id = e.id) AS inseminadas
                 FROM fazenda.estacao_monta e
                WHERE e.cliente_id = %(c)s
                ORDER BY e.data_inicio DESC NULLS LAST, e.id DESC""",
            {"c": cliente_id})}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/estacao/iatf")
def campo_estacao_iatf(req: IatfLoteIn):
    """IATF em lote (Brief B): cria 1 cruzamento por matriz do lote × touro escolhido, num
    único INSERT, com snapshot da previsão (= alimenta o flywheel em escala). Idempotente
    (uuid por matriz = uuid_lote-vaca_id; ON CONFLICT não duplica em replay do outbox)."""
    try:
        # HTTP externo ANTES da transação: um fetch lento da arroba (até 20s) não pode
        # segurar a transação (e os locks) abertos.
        arroba = (external_apis.boi_gordo() or {}).get("valor")
        with _tx() as conn:
            cur = _cur(conn)
            # genética do touro (1 query) -> ganho/cria e prenhez são touro-dirigidos
            cur.execute(
                f"""SELECT MAX(valor) FILTER (WHERE caracteristica_id={PD_ID})   AS pd,
                           MAX(valor) FILTER (WHERE caracteristica_id={PES_ID})  AS pes,
                           MAX(valor) FILTER (WHERE caracteristica_id={IQGG_ID}) AS iqgg
                    FROM mercado.avaliacao WHERE reprodutor_id = %(t)s""", {"t": req.touro_id})
            g = cur.fetchone() or {}
            pd, pes, tiqgg = g.get("pd"), g.get("pes"), g.get("iqgg")
            ganho = round(float(pd) * arroba / 30) if (pd and pd > 0 and arroba) else None
            prenhez = _prenhez_est(pes)
            # prog_iqgg é midparent (precisa do IQGg de cada matriz) -> calculado no próprio INSERT
            cur.execute(
                """INSERT INTO fazenda.cruzamento
                     (uuid, cliente_id, estacao_id, vaca_id, vaca_espelho_id, touro_id, touro_nome,
                      data_cruzamento, estacao_monta, ganho_cria, prog_iqgg, prenhez_est, registrado_por, coletado_em)
                   SELECT %(batch)s || '-' || a.id, %(cli)s, %(est)s, a.id, a.reprodutor_espelho_id,
                          %(tid)s, %(tn)s, d.dt,
                          EXTRACT(YEAR FROM d.dt)::int || '-' ||
                            CASE WHEN EXTRACT(MONTH FROM d.dt) <= 6 THEN '1' ELSE '2' END,
                          %(ganho)s,
                          CASE WHEN %(tiqgg)s IS NOT NULL AND vi.iqgg IS NOT NULL
                               THEN ROUND((0.5*(%(tiqgg)s + vi.iqgg))::numeric, 2) END,
                          %(prenhez)s, 'mari', now()
                     FROM fazenda.animal a
                     LEFT JOIN LATERAL (
                        SELECT MAX(av.valor) AS iqgg FROM mercado.avaliacao av
                        WHERE av.reprodutor_id = a.reprodutor_espelho_id AND av.caracteristica_id = %(iq)s
                     ) vi ON true
                     CROSS JOIN (SELECT COALESCE(%(dt)s::date, current_date) AS dt) d
                    WHERE a.cliente_id = %(cli)s AND a.sexo = 'F'
                      AND COALESCE(a.status,'ativo') = 'ativo'
                      AND (%(grupo)s IS NULL OR a.grupo_id = %(grupo)s)
                   ON CONFLICT (uuid) DO NOTHING
                   RETURNING id""",
                {"batch": req.uuid, "cli": req.cliente_id, "est": req.estacao_id, "tid": req.touro_id,
                 "tn": _cap(req.touro_nome, 120), "ganho": ganho, "tiqgg": tiqgg, "prenhez": prenhez,
                 "iq": IQGG_ID, "dt": req.data or None, "grupo": req.grupo_id})
            n = len(cur.fetchall())
            return {"inseminadas": n, "ganho_cria": ganho, "prenhez_est": prenhez, "ok": True}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/estacao/protocolo")
def campo_estacao_protocolo(req: ProtocoloIn):
    """Brief B/F1: aplica o protocolo IATF a um lote, gerando os passos (D0→DG) como
    eventos de agenda do lote (reusa fazenda.evento_sanitario). Idempotente por estação+lote."""
    try:
        if not req.grupo_id:
            return {"error": "selecione um lote (grupo) para o protocolo"}
        with _tx() as conn:
            cur = _cur(conn)
            # já aplicado a esta estação+lote? (não duplica a agenda)
            cur.execute(
                """SELECT COUNT(*) AS n FROM fazenda.evento_sanitario
                    WHERE estacao_id = %(e)s AND grupo_id = %(g)s AND tipo = 'protocolo'""",
                {"e": req.estacao_id, "g": req.grupo_id})
            if (cur.fetchone() or {}).get("n"):
                return {"ok": True, "passos": 0, "ja_aplicado": True}
            n = 0
            for dia, nome in PROTOCOLO_IATF:
                cur.execute(
                    """INSERT INTO fazenda.evento_sanitario
                         (grupo_id, estacao_id, tipo, produto, data_evento, proxima_dose, uuid, registrado_em)
                       SELECT %(g)s, %(e)s, 'protocolo', %(nome)s, current_date,
                              (COALESCE(%(d0)s::date, current_date) + %(dia)s), gen_random_uuid(), now()""",
                    {"g": req.grupo_id, "e": req.estacao_id, "nome": nome,
                     "d0": req.data_d0 or None, "dia": dia})
                n += 1
            return {"ok": True, "passos": n, "ja_aplicado": False}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/estacao/{estacao_id}/resumo")
def campo_estacao_resumo(estacao_id: int):
    """Resumo da estação: matrizes inseminadas, touros usados, prenhez (quando houver DG)."""
    try:
        r = query(
            """SELECT COUNT(*) AS inseminadas,
                      COUNT(DISTINCT touro_id) AS touros,
                      COUNT(*) FILTER (WHERE resultado IN ('prenhe','vazia')) AS diagnosticadas,
                      COUNT(*) FILTER (WHERE resultado='prenhe') AS prenhes,
                      ROUND(100.0*COUNT(*) FILTER (WHERE resultado='prenhe')
                            / NULLIF(COUNT(*) FILTER (WHERE resultado IN ('prenhe','vazia')),0)) AS prenhez_real
                 FROM fazenda.cruzamento WHERE estacao_id = %(e)s""", {"e": estacao_id})
        por_touro = query(
            """SELECT touro_nome, COUNT(*) AS inseminadas,
                      COUNT(*) FILTER (WHERE resultado='prenhe') AS prenhes
                 FROM fazenda.cruzamento WHERE estacao_id = %(e)s
                GROUP BY touro_nome ORDER BY inseminadas DESC""", {"e": estacao_id})
        return {"resumo": (r[0] if r else {}), "por_touro": por_touro}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/venda")
def campo_venda(req: VendaIn):
    """Registra uma venda de genética (Feature 4). Idempotente por uuid. Município/UF
    herdados do cadastro da fazenda quando não informados."""
    try:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.venda WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            mun, uf = req.municipio, (req.uf or "").upper()[:2] or None
            if req.cliente_id and not (mun and uf):
                cur.execute("SELECT municipio, uf FROM fazenda.cliente WHERE id = %(c)s", {"c": req.cliente_id})
                c = cur.fetchone() or {}
                mun = mun or c.get("municipio")
                uf = uf or c.get("uf")
            cur.execute(
                """INSERT INTO fazenda.venda
                     (uuid, cliente_id, municipio, uf, touro_id, touro_nome, data_venda,
                      tipo, quantidade, valor_unitario, registrado_por, coletado_em)
                   VALUES (%(u)s,%(cli)s,%(mun)s,%(uf)s,%(t)s,%(tn)s,
                      COALESCE(%(dt)s::date, current_date),
                      %(tipo)s,%(q)s,%(vu)s,%(rp)s, now()) RETURNING id""",
                {"u": req.uuid, "cli": req.cliente_id, "mun": _cap(mun, 100), "uf": uf,
                 "t": req.touro_id, "tn": _cap(req.touro_nome, 120), "dt": req.data_venda or None,
                 "tipo": (req.tipo or "semen"), "q": req.quantidade or 1,
                 "vu": req.valor_unitario, "rp": req.registrado_por or "mari"})
            return {"id": cur.fetchone()["id"], "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/painel-vendas")
def painel_vendas(uf: str = None, touro_id: int = None, desde: str = None, ate: str = None):
    """Inteligência de território de vendas (Feature 4, Hub admin): resumo + ranking por
    município e por touro. Filtros: uf, touro_id, período (desde/ate)."""
    try:
        cond = ["1=1"]
        p = {}
        if uf:
            cond.append("UPPER(uf) = %(uf)s"); p["uf"] = uf.upper()
        if touro_id:
            cond.append("touro_id = %(t)s"); p["t"] = touro_id
        if desde:
            cond.append("data_venda >= %(d)s"); p["d"] = desde
        if ate:
            cond.append("data_venda <= %(a)s"); p["a"] = ate
        w = " AND ".join(cond)
        resumo = query(
            f"""SELECT COALESCE(SUM(quantidade),0) AS unidades,
                       COALESCE(SUM(quantidade*COALESCE(valor_unitario,0)),0) AS receita,
                       COUNT(DISTINCT (uf||'|'||COALESCE(municipio,''))) AS municipios,
                       COUNT(*) AS transacoes
                FROM fazenda.venda WHERE {w}""", p)
        por_municipio = query(
            f"""SELECT municipio, uf, SUM(quantidade) AS unidades,
                       SUM(quantidade*COALESCE(valor_unitario,0)) AS receita
                FROM fazenda.venda WHERE {w}
                GROUP BY municipio, uf ORDER BY unidades DESC NULLS LAST LIMIT 50""", p)
        por_touro = query(
            f"""SELECT touro_nome, SUM(quantidade) AS unidades,
                       SUM(quantidade*COALESCE(valor_unitario,0)) AS receita
                FROM fazenda.venda WHERE {w}
                GROUP BY touro_nome ORDER BY unidades DESC NULLS LAST LIMIT 50""", p)
        return {"resumo": (resumo[0] if resumo else {}),
                "por_municipio": por_municipio, "por_touro": por_touro}
    except Exception as e:
        return _error(e)


@app.get("/api/fazenda/{cliente_id}/evolucao-genetica")
def fazenda_evolucao_genetica(cliente_id: int):
    """Série temporal do IQGg/ganho médio das progênies por estação de monta (Feature 6).
    Prova visual da melhora genética do rebanho. Vazio até a 1ª safra registrada."""
    try:
        rows = query(
            """SELECT estacao_monta,
                      COUNT(*) AS n,
                      ROUND(AVG(prog_iqgg)::numeric, 1)  AS iqgg_medio,
                      ROUND(AVG(ganho_cria)::numeric, 0) AS ganho_medio
                 FROM fazenda.cruzamento
                WHERE cliente_id = %(c)s AND prog_iqgg IS NOT NULL
                GROUP BY estacao_monta
                ORDER BY estacao_monta""",
            {"c": cliente_id})
        return {"serie": rows, "tem_dados": len(rows) > 0}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/pesagem")
def campo_pesagem(req: PesagemIn):
    try:
        err = _valida_pesagem(req)
        if err:
            return {"error": err}
        req.obs = _cap(req.obs, 500)
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.medicao WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.medicao
                     (animal_id, data_medicao, peso_kg, escore_corporal, altura_cm, grupo_id,
                      origem, dispositivo, medido_em, obs, uuid)
                   VALUES (%(a)s, COALESCE(%(d)s::date, current_date), %(p)s, %(e)s, %(alt)s, %(g)s,
                      %(orig)s, %(disp)s, now(), %(obs)s, %(u)s) RETURNING id""",
                {"a": req.animal_id, "d": req.data_medicao or None, "p": req.peso_kg,
                 "e": req.escore_corporal, "alt": req.altura_cm, "g": req.grupo_id,
                 "orig": req.origem or "manual", "disp": req.dispositivo, "obs": req.obs, "u": req.uuid})
            mid = cur.fetchone()["id"]
            # snapshot do animal só atualiza se ESTA medição é a mais recente — replay
            # fora de ordem do outbox (pesagem antiga sincronizada depois) não pode
            # sobrescrever o peso/escore atual com valor velho.
            eh_recente = """NOT EXISTS (
                  SELECT 1 FROM fazenda.medicao m2
                   WHERE m2.animal_id = %(a)s AND m2.id <> %(m)s
                     AND m2.{col} IS NOT NULL AND m2.data_medicao > (
                         SELECT data_medicao FROM fazenda.medicao WHERE id = %(m)s))"""
            if req.peso_kg is not None:
                cur.execute(
                    "UPDATE fazenda.animal SET peso_atual_kg=%(p)s WHERE id=%(a)s AND "
                    + eh_recente.format(col="peso_kg"),
                    {"p": req.peso_kg, "a": req.animal_id, "m": mid})
            if req.escore_corporal is not None:
                cur.execute(
                    "UPDATE fazenda.animal SET escore_corporal=%(e)s WHERE id=%(a)s AND "
                    + eh_recente.format(col="escore_corporal"),
                    {"e": req.escore_corporal, "a": req.animal_id, "m": mid})
            return {"id": mid, "novo": True}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/sanitario")
def campo_sanitario(req: SanitarioIn):
    try:
        if not req.animal_id and not req.grupo_id:
            return {"error": "informe animal_id ou grupo_id"}
        if (req.tipo or "").lower() not in _TIPO_SANITARIO_OK:
            return {"error": "tipo sanitário inválido"}
        req.produto = _cap(req.produto, 150)
        req.dose = _cap(req.dose, 40)
        req.via = _cap(req.via, 30)
        req.responsavel = _cap(req.responsavel, 120)
        req.obs = _cap(req.obs, 500)
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.evento_sanitario WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.evento_sanitario
                     (animal_id, grupo_id, tipo, produto, data_evento, proxima_dose, dose, via,
                      responsavel, obs, uuid, registrado_em)
                   VALUES (%(a)s,%(g)s,%(t)s,%(prod)s, COALESCE(%(d)s::date, current_date),
                      %(prox)s::date, %(dose)s,%(via)s,%(resp)s,%(obs)s,%(u)s, now()) RETURNING id""",
                {"a": req.animal_id, "g": req.grupo_id, "t": req.tipo, "prod": req.produto,
                 "d": req.data_evento or None, "prox": req.proxima_dose or None, "dose": req.dose,
                 "via": req.via, "resp": req.responsavel, "obs": req.obs, "u": req.uuid})
            new_id = cur.fetchone()["id"]
            # se a aplicação veio de um lembrete da Agenda, fecha o lembrete de origem
            if req.origem_lembrete_id:
                cur.execute(
                    """UPDATE fazenda.evento_sanitario
                         SET lembrete_concluido = true, lembrete_concluido_em = now()
                       WHERE id = %(lid)s AND lembrete_concluido = false""",
                    {"lid": req.origem_lembrete_id})
            return {"id": new_id, "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/agenda")
def campo_agenda(cliente_id: int, dias: int = 30):
    """Lembretes sanitários pendentes (proxima_dose definida, ainda não cumprida).
    Inclui TODOS os atrasados + os que vencem nos próximos `dias`. Ordenado por urgência."""
    try:
        # leitura pura -> usa o caminho autocommit (query), não a transação de escrita
        rows = query(
                """SELECT e.id, e.animal_id, e.grupo_id, e.tipo, e.produto, e.dose, e.via,
                          e.proxima_dose, (e.proxima_dose - current_date) AS dias,
                          a.nome AS animal_nome, a.brinco, ra.sigla AS raca_sigla,
                          g.nome AS lote_nome
                     FROM fazenda.evento_sanitario e
                     LEFT JOIN fazenda.animal a ON a.id = e.animal_id
                     LEFT JOIN catalogo.raca ra ON ra.id = a.raca_id
                     LEFT JOIN fazenda.grupo_manejo g ON g.id = e.grupo_id
                    WHERE e.proxima_dose IS NOT NULL
                      AND e.lembrete_concluido = false
                      AND COALESCE(a.cliente_id, g.cliente_id) = %(c)s
                      AND e.proxima_dose <= current_date + %(d)s
                    ORDER BY e.proxima_dose ASC, e.id ASC""",
                {"c": cliente_id, "d": dias})
        itens = []
        n_atrasado = n_hoje = n_prox = 0
        for r in rows:
                d = r["dias"]
                status = "atrasado" if d < 0 else ("hoje" if d == 0 else "proximo")
                if status == "atrasado": n_atrasado += 1
                elif status == "hoje": n_hoje += 1
                else: n_prox += 1
                itens.append({
                    "id": r["id"], "animal_id": r["animal_id"], "grupo_id": r["grupo_id"],
                    "alvo": r["animal_nome"] or r["brinco"] or (r["lote_nome"] and ("Lote " + r["lote_nome"]))
                            or (r["animal_id"] and ("#" + str(r["animal_id"]))) or "—",
                    "is_lote": r["animal_id"] is None and r["grupo_id"] is not None,
                    "raca_sigla": r["raca_sigla"], "tipo": r["tipo"], "produto": r["produto"],
                    "dose": r["dose"], "via": r["via"],
                    "proxima_dose": r["proxima_dose"].isoformat() if r["proxima_dose"] else None,
                    "dias": d, "status": status,
                })
        return {"itens": itens, "resumo": {"atrasado": n_atrasado, "hoje": n_hoje,
                "proximo": n_prox, "total": len(itens)}}
    except Exception as e:
        return _error(e)


@app.post("/api/campo/agenda/concluir")
def campo_agenda_concluir(req: ConcluirLembreteIn):
    """Dispensa um lembrete sem registrar nova aplicação (some da agenda)."""
    try:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE fazenda.evento_sanitario
                     SET lembrete_concluido = true, lembrete_concluido_em = now()
                   WHERE id = %(id)s RETURNING id""",
                {"id": req.id})
            row = cur.fetchone()
            return {"id": row["id"], "ok": True} if row else {"error": "lembrete não encontrado"}
    except Exception as e:
        return _error(e)


_PRIORIDADE_LABEL = {
    "geral": "Geral (IQGg)", "crescimento": "Crescimento (GPD)", "carcaca": "Carcaça (AOL)",
    "precocidade": "Precocidade (PES)", "fertilidade": "Fertilidade (HP)",
}


@app.get("/api/campo/cotacao/pdf")
async def campo_cotacao_pdf(matriz_id: int, prioridade: str = "geral",
                            cliente_id: int | None = None, top: int = 8,
                            n_doses: int | None = None, touro_id: int | None = None):
    """Cotação de sêmen em PDF a partir do acasalamento ao vivo da matriz (tela Cruzar).
    Reusa a lógica de /api/acasalamento e renderiza um documento comercial p/ o produtor.
    Se `touro_id` (touro escolhido na tela), a cotação lidera por ele e mantém os demais como alternativas."""
    try:
        res = acasalamento(matriz_id, prioridade=prioridade, top=top)  # def síncrona -> sem await
        if not res or res.get("error"):
            return JSONResponse({"error": (res or {}).get("error", "matriz não encontrada")}, status_code=404)
        if touro_id:
            recs = res.get("recomendacoes") or []
            escolhido = [r for r in recs if r.get("id") == touro_id]
            if escolhido:
                res["recomendacoes"] = escolhido + [r for r in recs if r.get("id") != touro_id]
        cliente = None
        if cliente_id:
            rows = query("SELECT razao_social, uf, municipio FROM fazenda.cliente WHERE id = %(id)s",
                         {"id": cliente_id})
            cliente = rows[0] if rows else None
        pdf_bytes = await run_in_threadpool(
            gerar_cotacao_acasalamento, res["matriz"], res["recomendacoes"], cliente,
            _PRIORIDADE_LABEL.get(prioridade, prioridade.capitalize()), n_doses)
        vaca = res["matriz"].get("nome") or res["matriz"].get("registro") or matriz_id
        slug = "".join(c if c.isalnum() else "_" for c in str(vaca))[:40]
        fname = f"cotacao_semen_{slug}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={fname}"})
    except Exception as e:
        return _error(e)


@app.get("/api/campo/auditoria")
def campo_auditoria(cliente_id: int):
    """Auditoria genética do rebanho: fêmeas do cliente avaliadas (via espelho no
    catálogo) contra a média da própria raça. Aponta gargalos, ranking e quem genotipar."""
    try:
        rows = query(
            """SELECT a.id, a.nome, a.brinco, a.raca_id, ra.sigla AS raca_sigla,
                      MAX(CASE WHEN av.caracteristica_id = 20 THEN av.valor END) AS iqgg,
                      MAX(CASE WHEN av.caracteristica_id = 8  THEN av.valor END) AS gpd,
                      MAX(CASE WHEN av.caracteristica_id = 16 THEN av.valor END) AS aol,
                      MAX(CASE WHEN av.caracteristica_id = 12 THEN av.valor END) AS pes,
                      MAX(CASE WHEN av.caracteristica_id = 18 THEN av.valor END) AS mar,
                      bool_or(av.eh_genomica) FILTER (WHERE av.caracteristica_id = 20) AS iqgg_genomica,
                      a.reprodutor_espelho_id
                 FROM fazenda.animal a
                 LEFT JOIN catalogo.raca ra ON ra.id = a.raca_id
                 LEFT JOIN mercado.avaliacao av ON av.reprodutor_id = a.reprodutor_espelho_id
                       AND av.caracteristica_id IN (20, 8, 16, 12, 18)
                WHERE a.cliente_id = %(c)s AND a.sexo = 'F'
                GROUP BY a.id, a.nome, a.brinco, a.raca_id, ra.sigla, a.reprodutor_espelho_id""",
            {"c": cliente_id})
        tot = query(
            """SELECT count(*) FILTER (WHERE sexo = 'F') AS femeas, count(*) AS total
                 FROM fazenda.animal WHERE cliente_id = %(c)s""", {"c": cliente_id})[0]

        genot = [r for r in rows if r.get("iqgg") is not None]
        nao = [r for r in rows if r.get("iqgg") is None]

        # raça predominante entre as genotipadas (p/ benchmark de exibição)
        from collections import Counter
        raca_cnt = Counter(r["raca_id"] for r in genot if r.get("raca_id"))
        raca_pred = raca_cnt.most_common(1)[0][0] if raca_cnt else None
        media_raca = _media_iqgg_raca(raca_pred) if raca_pred else None
        raca_pred_sigla = next((r["raca_sigla"] for r in genot if r["raca_id"] == raca_pred), None)

        for r in genot:
            m = _media_iqgg_raca(r["raca_id"])
            r["media_raca"] = m
            r["lift"] = round(r["iqgg"] - m, 2) if (m is not None) else None

        def _avg(key, src=genot):
            vals = [r[key] for r in src if r.get(key) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        iqggs = sorted(r["iqgg"] for r in genot)
        stats = {}
        if iqggs:
            n = len(iqggs)
            stats = {
                "media": round(sum(iqggs) / n, 2),
                "mediana": iqggs[n // 2] if n % 2 else round((iqggs[n // 2 - 1] + iqggs[n // 2]) / 2, 2),
                "melhor": iqggs[-1], "pior": iqggs[0],
                "media_raca": media_raca,
                "lift_medio": _avg("lift"),
                "acima_da_raca": sum(1 for r in genot if (r.get("lift") or 0) > 0),
            }

        # ranking: melhor -> pior; quartil inferior = prioridade de acasalamento corretivo
        genot.sort(key=lambda r: r["iqgg"], reverse=True)
        n = len(genot)
        import math
        corte = math.ceil(n * 0.75)  # índice a partir do qual entra no quartil inferior
        ranking = []
        for i, r in enumerate(genot):
            ranking.append({
                "id": r["id"], "nome": r.get("nome"), "brinco": r.get("brinco"),
                "raca_sigla": r.get("raca_sigla"), "iqgg": r["iqgg"],
                "gpd": r.get("gpd"), "aol": r.get("aol"),
                "lift": r.get("lift"), "media_raca": r.get("media_raca"),
                "reprodutor_espelho_id": r.get("reprodutor_espelho_id"),
                "genomica": bool(r.get("iqgg_genomica")),  # False = mérito estimado pelo pai
                "prioridade_corretiva": (n >= 4 and i >= corte),
            })

        # gargalos: características em que o rebanho está abaixo (lift negativo no IQGg
        # já é o sinal-mestre; aqui sinalizamos a média de cada traço p/ leitura rápida)
        traits = {k: _avg(k) for k in ("gpd", "aol", "pes", "mar")}

        return {
            "resumo": {
                "total": tot["total"], "femeas": tot["femeas"],
                "genotipadas": len(genot), "nao_genotipadas": len(nao),
                "pct_genotipadas": round(100 * len(genot) / tot["femeas"]) if tot["femeas"] else 0,
            },
            "iqgg": stats, "raca_predominante": raca_pred_sigla, "traits": traits,
            "ranking": ranking,
            "a_genotipar": [{"id": r["id"], "nome": r.get("nome"), "brinco": r.get("brinco"),
                             "raca_sigla": r.get("raca_sigla")} for r in nao],
        }
    except Exception as e:
        return _error(e)


@app.post("/api/campo/movimentacao")
def campo_movimentacao(req: MovimentacaoIn):
    """Registra movimentação/GTA (entrada, saída, transferência…). Idempotente por uuid."""
    try:
        if (req.tipo or "").lower() not in _TIPO_MOV_OK:
            return {"error": "tipo de movimentação inválido"}
        if req.quantidade is not None and not (0 < req.quantidade <= 100000):
            return {"error": "quantidade fora da faixa"}
        gta = _cap(req.gta_numero, 30)
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute("SELECT id FROM fazenda.movimentacao WHERE uuid = %(u)s", {"u": req.uuid})
            ex = cur.fetchone()
            if ex:
                return {"id": ex["id"], "novo": False}
            cur.execute(
                """INSERT INTO fazenda.movimentacao
                     (cliente_id, tipo, data_evento, gta_numero, origem, destino,
                      finalidade, quantidade, obs, uuid, registrado_em)
                   VALUES (%(c)s, %(t)s, COALESCE(%(d)s::date, current_date), %(gta)s, %(o)s, %(dest)s,
                      %(fin)s, %(q)s, %(obs)s, %(u)s, now()) RETURNING id""",
                {"c": req.cliente_id, "t": req.tipo.lower(), "d": req.data_evento or None,
                 "gta": gta, "o": _cap(req.origem), "dest": _cap(req.destino),
                 "fin": _cap(req.finalidade, 60), "q": req.quantidade, "obs": _cap(req.obs, 500),
                 "u": req.uuid})
            return {"id": cur.fetchone()["id"], "novo": True}
    except Exception as e:
        return _error(e)


@app.get("/api/campo/briefing/pdf")
async def campo_briefing_pdf(movimentacao_id: int):
    """Briefing de chegada (PDF) de um lote recebido — detalhes da entrada + protocolo de recepção."""
    try:
        rows = query(
            """SELECT m.id, m.cliente_id, m.tipo, m.data_evento, m.gta_numero, m.origem,
                      m.destino, m.finalidade, m.quantidade, m.obs,
                      c.razao_social, c.uf, c.municipio
                 FROM fazenda.movimentacao m JOIN fazenda.cliente c ON c.id = m.cliente_id
                WHERE m.id = %(id)s""", {"id": movimentacao_id})
        if not rows:
            return JSONResponse({"error": "movimentação não encontrada"}, status_code=404)
        m = rows[0]
        cliente = {"razao_social": m.get("razao_social"), "uf": m.get("uf"), "municipio": m.get("municipio")}
        pdf_bytes = await run_in_threadpool(gerar_briefing_chegada, m, cliente)
        fname = f"briefing_chegada_{movimentacao_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={fname}"})
    except Exception as e:
        return _error(e)


@app.get("/api/campo/movimentacoes")
def campo_movimentacoes(cliente_id: int, limit: int = 50):
    try:
        return query(
            """SELECT id, tipo, data_evento, gta_numero, origem, destino, finalidade,
                      quantidade, obs
                 FROM fazenda.movimentacao
                WHERE cliente_id = %(c)s
                ORDER BY data_evento DESC, id DESC LIMIT %(l)s""",
            {"c": cliente_id, "l": min(limit, 200)})
    except Exception as e:
        return _error(e)
