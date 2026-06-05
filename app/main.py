from fastapi import FastAPI, Request, Response, Form
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
from pdf_generator import gerar_parecer_pdf
import external_apis
import psycopg2
import psycopg2.extras
from psycopg2 import pool as pgpool
import logging
import io
import os

logger = logging.getLogger("wins_agro")

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")


@app.middleware("http")
async def request_pipeline(request: Request, call_next):
    """Exige sessão válida em /api/* (dados sensíveis/PII) e aplica cache longo
    nos assets versionados de /static/vendor/."""
    path = request.url.path
    if path.startswith("/api/"):
        token = request.cookies.get("access_token")
        if not token or decode_token(token) is None:
            return JSONResponse({"error": "Não autenticado"}, status_code=401)
    response = await call_next(request)
    if path.startswith("/static/vendor/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        "frontend/sw.js", media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.webmanifest")
async def manifest():
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
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "***SENHA-PG-REMOVIDA(rotacionada-jun08)***"),
}

# IQGg = Índice de Qualificação Genética Genômica (Básico) — catalogo.caracteristica.id = 20
IQGG_ID = 20

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


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_token(token)


# ---------------------------------------------------------------------------
# Auth / pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(response: Response, email: str = Form(...), password: str = Form(...)):
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
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp


# ---------------------------------------------------------------------------
# API — data endpoints
# ---------------------------------------------------------------------------
@app.get("/api/stats")
async def stats():
    try:
        # uma única ida ao banco (era 6 conexões/queries separadas)
        return query(
            """
            SELECT
              (SELECT COUNT(*) FROM mercado.reprodutor)            AS reprodutores,
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


@app.get("/api/ufs")
async def ufs():
    try:
        rows = query(
            "SELECT DISTINCT uf FROM prospeccao.v_white_space_pecuaria "
            "WHERE uf IS NOT NULL ORDER BY uf"
        )
        return [r["uf"] for r in rows]
    except Exception as e:
        return _error(e)


@app.get("/api/racas")
async def racas():
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
async def whitespace(uf: str = None):
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
async def arbitragem(raca: int = None):
    try:
        return query(
            """
            SELECT r.nome AS nome_touro, r.registro,
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
            ORDER BY preco_por_iqgg ASC NULLS LAST
            LIMIT 50
            """,
            {"iqgg": IQGG_ID, "raca": raca},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/centrais")
async def centrais():
    try:
        return query(
            """
            SELECT c.nome AS central,
                   COUNT(DISTINCT tc.reprodutor_id) AS total_touros,
                   COUNT(DISTINCT o.id) AS total_ofertas,
                   ROUND(AVG(o.preco_dose_brl)::numeric, 2) AS preco_medio
            FROM catalogo.central c
            LEFT JOIN mercado.touro_central tc ON tc.central_id = c.id
            LEFT JOIN mercado.touro_oferta o ON o.central_id = c.id
            GROUP BY c.id, c.nome
            ORDER BY total_touros DESC
            """
        )
    except Exception as e:
        return _error(e)


@app.get("/api/fazendas")
async def fazendas():
    try:
        return query(
            """
            SELECT r.fazenda_origem,
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
            GROUP BY r.fazenda_origem
            HAVING COUNT(*) >= 3
            ORDER BY total_reprodutores DESC
            LIMIT 20
            """,
            {"iqgg": IQGG_ID},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/caracteristicas")
async def caracteristicas():
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
        }
        # DISTINCT ON (r.id) -> um único registro por touro (touro_central pode
        # repetir o touro em várias centrais). Score independe da central.
        rows = query(
            """
            WITH deps AS (
                SELECT reprodutor_id,
                    MAX(CASE WHEN caracteristica_id = %(iqgg)s THEN valor END) AS iqgg,
                    MAX(CASE WHEN caracteristica_id = %(dep_id)s THEN valor END) AS dep_prioritaria,
                    MAX(CASE WHEN caracteristica_id = 5 THEN valor END) AS peso_dep
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
            maximos AS (
                -- normalização POR RAÇA: escalas de índice diferem entre raças
                -- (IQGg zebu ~40-70, PTA Leite girolando ~500-2300, marmoreio wagyu ~1-3)
                SELECT rr.raca_id, MAX(d.iqgg) AS max_iqgg, MAX(d.dep_prioritaria) AS max_dep
                FROM deps d JOIN mercado.reprodutor rr ON rr.id = d.reprodutor_id
                GROUP BY rr.raca_id
            )
            SELECT * FROM (
                SELECT DISTINCT ON (r.id)
                    r.id, r.nome, r.registro, ra.nome AS raca, c.nome AS central,
                    r.fazenda_origem,
                    (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) AS preco_dose,
                    d.iqgg, d.dep_prioritaria, d.peso_dep,
                    ROUND((
                        (d.dep_prioritaria / NULLIF(m.max_dep, 0)) * 0.5 +
                        (d.iqgg / NULLIF(m.max_iqgg, 0)) * 0.3 +
                        CASE
                            WHEN %(orcamento_max)s IS NOT NULL AND %(orcamento_max)s > 0
                                 AND (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) > 0
                            THEN (1 - LEAST(
                                (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END)
                                / %(orcamento_max)s, 1)) * 0.2
                            ELSE 0.2
                        END
                    )::numeric, 4) AS score,
                    CASE
                        WHEN d.iqgg > 0 AND (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) > 0
                        THEN ROUND(((CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) / d.iqgg)::numeric, 2)
                        ELSE NULL
                    END AS preco_por_iqgg
                FROM mercado.reprodutor r
                JOIN catalogo.raca ra ON ra.id = r.raca_id
                JOIN deps d ON d.reprodutor_id = r.id
                LEFT JOIN mercado.touro_central tc ON tc.reprodutor_id = r.id
                LEFT JOIN catalogo.central c ON c.id = tc.central_id
                LEFT JOIN ofertas o ON o.reprodutor_id = r.id
                JOIN maximos m ON m.raca_id = r.raca_id
                WHERE d.iqgg IS NOT NULL
                  AND d.dep_prioritaria IS NOT NULL
                  AND (%(raca_id)s IS NULL OR r.raca_id = %(raca_id)s)
                  -- preço é opcional: sem orçamento, raças sem oferta entram pelo mérito
                  -- genético. COM orçamento definido (modo comercial), só passam os que
                  -- têm preço dentro do teto.
                  AND (%(orcamento_max)s IS NULL OR %(orcamento_max)s = 0
                       OR (CASE WHEN %(sexado)s THEN o.preco_sexado ELSE o.preco_dose END) <= %(orcamento_max)s)
                ORDER BY r.id, c.nome NULLS LAST
            ) sub
            ORDER BY score DESC NULLS LAST
            LIMIT 30
            """,
            params,
        )
        # Valor econômico estimado por bezerro: vantagem de PD (peso à desmama, kg,
        # vs a média da raça) × cotação do boi. Carcaça ~50%, @ = 15 kg ->
        # valor = peso_dep × 0,5 ÷ 15 × R$/@ = peso_dep × preço / 30. É ESTIMATIVA.
        boi = await run_in_threadpool(external_apis.boi_gordo)
        arroba = (boi or {}).get("valor")
        for t in rows:
            pd = t.get("peso_dep")
            t["valor_bezerro"] = (
                round(pd * arroba / 30, 2)
                if (pd is not None and pd > 0 and arroba) else None
            )
        return {
            "total": len(rows),
            "prioridade": req.prioridade,
            "dep_id": dep_id,
            "boi_arroba": arroba,
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

    pdf_bytes = gerar_parecer_pdf(perfil, touros)
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
async def touro_detalhe(touro_id: int):
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
        return touro
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Multi-raça: todas as raças com reprodutores + flags de dado disponível
# ---------------------------------------------------------------------------
@app.get("/api/racas/todas")
async def racas_todas():
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
                FROM mercado.reprodutor GROUP BY raca_id
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
async def grupos():
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


@app.get("/api/leads")
async def leads(uf: str = None, segmento: str = "corte", limit: int = 50):
    """Compradores potenciais: estabelecimentos rurais (CNAE corte/leite) com contato."""
    try:
        cnae = SEGMENTO_CNAE.get(segmento, "0151201")
        # DISTINCT ON (cnpj_basico): uma linha por empresa (JBJ etc. têm dezenas de filiais),
        # mantendo o estabelecimento mais "contactável".
        return query(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (e.cnpj_basico)
                       COALESCE(NULLIF(em.razao_social, ''), e.nome_fantasia, '(produtor rural)') AS nome,
                       e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
                       m.nome AS municipio, e.uf,
                       e.ddd_1, e.telefone_1, e.correio_eletronico AS email,
                       NULLIF(TRIM(CONCAT_WS(', ', NULLIF(e.logradouro,''), NULLIF(e.bairro,''))), '') AS endereco,
                       em.porte, em.capital_social
                FROM cnpj.estabelecimento_rural e
                JOIN referencia.municipio m ON m.codigo_tom = e.municipio::int
                LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico = e.cnpj_basico
                WHERE e.cnae_fiscal_principal = %(cnae)s
                  AND e.situacao_cadastral = '02'
                  AND (%(uf)s IS NULL OR e.uf = %(uf)s)
                ORDER BY e.cnpj_basico,
                         (e.correio_eletronico IS NOT NULL) DESC,
                         (e.telefone_1 IS NOT NULL) DESC
            ) sub
            ORDER BY (email IS NOT NULL) DESC, (telefone_1 IS NOT NULL) DESC,
                     capital_social DESC NULLS LAST
            LIMIT %(limit)s
            """,
            {"cnae": cnae, "uf": uf, "limit": min(limit, 2000)},
        )
    except Exception as e:
        return _error(e)


@app.get("/api/marketplace")
async def marketplace(uf: str = None, segmento: str = "corte"):
    """Painel oferta×demanda por UF: criadores (demanda), rebanho/desertos e melhores touros (oferta)."""
    try:
        cnae = SEGMENTO_CNAE.get(segmento, "0151201")
        demanda = query(
            """
            SELECT e.uf,
                   COUNT(*) AS criadores,
                   COUNT(e.correio_eletronico) AS com_email,
                   COUNT(e.telefone_1) AS com_telefone
            FROM cnpj.estabelecimento_rural e
            WHERE e.cnae_fiscal_principal = %(cnae)s
              AND e.situacao_cadastral = '02'
              AND (%(uf)s IS NULL OR e.uf = %(uf)s)
            GROUP BY e.uf
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
                ORDER BY r.id, o.preco_dose_brl ASC
            ) sub
            ORDER BY iqgg DESC NULLS LAST
            LIMIT 10
            """,
            {"iqgg": IQGG_ID},
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
async def mapa(uf: str = None, min_bovinos: int = 20000):
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
async def demanda_tendencia(uf: str = None, limit: int = 200, min_reb: int = 30000):
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
async def demanda_lotacao(uf: str = None, limit: int = 50):
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
            WHERE pa.ha > 20000 AND h.cab > 20000
              AND (%(uf)s IS NULL OR h.uf = %(uf)s)
            ORDER BY lotacao ASC
            LIMIT %(limit)s
            """,
            {"uf": uf, "limit": min(limit, 200)},
        )
    except Exception as e:
        return _error(e)


_WHALES_CACHE = {}


@app.get("/api/demanda/whales")
async def demanda_whales(uf: str = None, limit: int = 40):
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
async def leads_csv(uf: str = None, segmento: str = "corte", limit: int = 1000):
    """Exporta leads (criadores) em CSV para CRM."""
    base = await leads(uf=uf, segmento=segmento, limit=min(limit, 2000))
    if isinstance(base, dict):  # erro
        return base
    import csv as _csv

    buf = io.StringIO()
    cols = ["nome", "cnpj", "municipio", "uf", "ddd_1", "telefone_1",
            "email", "endereco", "porte", "capital_social"]
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


@app.get("/api/leads/enriquecido")
async def leads_enriquecido(uf: str = None, segmento: str = "corte", top: int = 5):
    """Leads + enriquecimento automático (BrasilAPI) dos `top` mais contactáveis."""
    try:
        base = await leads(uf=uf, segmento=segmento, limit=50)
        if isinstance(base, dict):  # erro
            return base
        for lead in base[: min(top, 10)]:
            if lead.get("cnpj"):
                info = await run_in_threadpool(external_apis.cnpj, lead["cnpj"])
                if not info.get("error"):
                    lead["enriquecido"] = {
                        "situacao": info.get("situacao"),
                        "abertura": info.get("abertura"),
                        "socios": len(info.get("socios") or []),
                        "capital_social": info.get("capital_social"),
                    }
        return base
    except Exception as e:
        return _error(e)
