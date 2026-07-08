"""ci-api — backend mínimo do Cliente Inteligente (Fase 2, Tier 1).

Capacidades:
  - Contas leves (telefone + senha → token de sessão).
  - Backup na nuvem: o app cifra o blob NO CLIENTE (AES-GCM via WebCrypto) e sobe
    o ciphertext em base64. O servidor guarda BYTES OPACOS — nunca vê os dados.
  - Publicar cardápio: o app gera o HTML estático e o servidor o grava em
    /loja/<slug>/index.html (servido pelo nginx). Pedido do cliente final volta por wa.me.

Sem dependência de SMS/Cloud API. SQLite + filesystem. Isolamento por token→conta.
"""
import os, re, time, json, datetime, secrets, hashlib, sqlite3
from pathlib import Path
import argon2
from fastapi import FastAPI, HTTPException, Header, Request, Body
from fastapi.responses import PlainTextResponse

DATA = os.environ.get("CI_DATA", "/data")
LOJAS = os.environ.get("CI_LOJAS", "/data/lojas")
DB = os.path.join(DATA, "ci.db")
BACKUPS = os.path.join(DATA, "backups")
MASTER_APP_SEED = Path(os.environ.get("CI_MASTER_APP_SEED", os.path.join(DATA, "master_app_seed.json")))
for d in (DATA, LOJAS, BACKUPS):
    os.makedirs(d, exist_ok=True)

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{2,39}$')
MAX_BACKUP = 6_000_000   # ~6 MB de ciphertext
MAX_HTML   = 2_000_000


def db():
    # synchronous=NORMAL é mais rápido em WAL mantendo integridade. timeout evita travamentos.
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=5000")
    return c


def init_db():
    # Define WAL persistente no cabeçalho do BD uma única vez no boot
    c = sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.commit()
    c.close()

    c = db()
    c.executescript("""
      CREATE TABLE IF NOT EXISTS contas(
        id TEXT PRIMARY KEY, fone TEXT UNIQUE, slug TEXT UNIQUE,
        salt TEXT, pass_hash TEXT, criado TEXT);
      CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY, conta_id TEXT, criado TEXT);
      CREATE TABLE IF NOT EXISTS estabelecimento_claims(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id TEXT NOT NULL,
        place_id TEXT NOT NULL,
        claim_slug TEXT,
        nome_comercial TEXT,
        segmento TEXT,
        telefone TEXT,
        endereco TEXT,
        status TEXT DEFAULT 'claimed',
        origem TEXT DEFAULT 'onepage_claim',
        created_at TEXT,
        updated_at TEXT,
        UNIQUE(conta_id, place_id)
      );
      CREATE INDEX IF NOT EXISTS idx_sessions_expira ON sessions(expira);
      CREATE INDEX IF NOT EXISTS idx_estabelecimento_claims_place_id ON estabelecimento_claims(place_id);
      CREATE INDEX IF NOT EXISTS idx_estabelecimento_claims_conta_id ON estabelecimento_claims(conta_id);
    """)
    # Recuperação por código (Onda 1): rec_wrap = chave AES embrulhada pelo código de
    # recuperação (cliente); rec_hash = PBKDF2 do código (p/ autorizar o reset). O servidor
    # NUNCA vê o código nem a chave — zero-knowledge preservado. Migração idempotente.
    for col in ("rec_hash", "rec_wrap"):
        try:
            c.execute(f"ALTER TABLE contas ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    # Versão do backup p/ optimistic concurrency (auto-sync multi-dispositivo)
    try:
        c.execute("ALTER TABLE contas ADD COLUMN backup_ver INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Expiração de sessão (revogável). Sessões antigas ficam com expira NULL = válidas.
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN expira TEXT")
    except sqlite3.OperationalError:
        pass
    for col in ("admin_note", "verified_at", "rejected_at"):
        try:
            c.execute(f"ALTER TABLE estabelecimento_claims ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    c.commit(); c.close()


init_db()


_ph = argon2.PasswordHasher()          # Argon2id (defaults seguros)
SESSAO_DIAS = 60                       # validade do token de sessão
SAFE_CLAIM_FIELDS = (
    "place_id",
    "slug_app",
    "nome_comercial",
    "segmento",
    "familia_segmento",
    "telefone",
    "endereco",
    "latitude",
    "longitude",
    "modulos_recomendados",
    "oferta_recomendada",
    "app_claim_url",
    "seed_config",
)
CLAIM_PROHIBITED_KEYS = {
    "cnpj",
    "cnpj_status",
    "cnpj_confidence",
    "cnpj_candidates_json",
    "razao_social",
    "nome_fantasia",
    "score",
    "score_digital",
    "score_dor",
    "score_comercial",
    "lead_tier",
    "tier",
    "prioridade",
    "dor",
    "dor_dominante",
    "reclamacoes",
    "pitch",
    "pitch_presencial",
    "mensagem_whatsapp",
    "risco",
    "legal_risk",
    "nivel_confianca_interno",
    "nivel_confianca_publico",
}
_claim_seed_cache = {"mtime": None, "rows": None, "source": str(MASTER_APP_SEED)}


def hash_senha_pbkdf2(senha, salt):    # esquema LEGADO (contas antigas)
    return hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 120000).hex()


def verify_senha(stored, senha, salt):
    """Confere a senha. Argon2id p/ contas novas; PBKDF2 (tempo constante) p/ legado."""
    if not stored:
        return False
    if stored.startswith("$argon2"):
        try:
            _ph.verify(stored, senha); return True
        except Exception:
            return False
    return secrets.compare_digest(stored, hash_senha_pbkdf2(senha, salt))


def _admin_token() -> str:
    env = os.environ.get("CI_ADMIN_TOKEN", "").strip()
    if env:
        return env
    for p in (os.path.join(DATA, "admin_token.txt"), "/root/wins_agro_v1/ci-data/admin_token.txt"):
        try:
            t = open(p).read().strip()
            if t:
                return t
        except OSError:
            continue
    t = secrets.token_urlsafe(32)
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "admin_token.txt"), "w") as f:
        f.write(t)
    return t


ADMIN_TOKEN = _admin_token()

ADMIN_STATUS = {"pending_verification", "claimed", "verified", "rejected"}

ADMIN_SAFE_FIELDS = (
    "id", "conta_id", "place_id", "claim_slug", "nome_comercial",
    "segmento", "telefone", "endereco", "status", "origem",
    "created_at", "updated_at", "admin_note", "verified_at", "rejected_at",
)


def _verify_admin(x_admin_token: str = Header(None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "token admin inválido")


def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ts_mais(dias):
    return (datetime.datetime.utcnow() + datetime.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")


def nova_sessao(conta_id):
    token = secrets.token_urlsafe(24)
    c = db()
    c.execute("DELETE FROM sessions WHERE expira IS NOT NULL AND expira < ?", (ts(),))  # limpa expiradas
    c.execute("INSERT INTO sessions(token,conta_id,criado,expira) VALUES(?,?,?,?)",
              (token, conta_id, ts(), ts_mais(SESSAO_DIAS)))
    c.commit(); c.close()
    return token


def conta_do_token(token):
    if not token:
        raise HTTPException(401, "sem token")
    c = db()
    # sessão legada (expira NULL) segue válida; nova expira em SESSAO_DIAS
    r = c.execute(
        "SELECT c.* FROM contas c JOIN sessions s ON s.conta_id=c.id "
        "WHERE s.token=? AND (s.expira IS NULL OR s.expira > ?)",
        (token, ts())).fetchone()
    c.close()
    if not r:
        raise HTTPException(401, "sessão inválida ou expirada — entre de novo")
    return r


def _claim_seed_updated_at() -> str:
    if MASTER_APP_SEED.exists():
        ts = datetime.datetime.fromtimestamp(MASTER_APP_SEED.stat().st_mtime, tz=datetime.timezone.utc)
        return ts.replace(microsecond=0).isoformat()
    return ""


def _load_claim_seed_rows() -> list[dict[str, object]]:
    if not MASTER_APP_SEED.exists():
        raise HTTPException(503, "seed do app indisponível")
    mtime = MASTER_APP_SEED.stat().st_mtime
    if _claim_seed_cache["rows"] is not None and _claim_seed_cache["mtime"] == mtime:
        return _claim_seed_cache["rows"]
    try:
        with MASTER_APP_SEED.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"falha ao ler seed do app: {exc}")
    if not isinstance(data, list):
        raise HTTPException(503, "seed do app inválido")
    rows = [row for row in data if isinstance(row, dict)]
    _claim_seed_cache["mtime"] = mtime
    _claim_seed_cache["rows"] = rows
    return rows


def _safe_claim_seed_payload(row: dict[str, object]) -> dict[str, object]:
    payload = {key: row.get(key) for key in SAFE_CLAIM_FIELDS}
    payload["ok"] = True
    return payload


def _claim_seed_by_place_id(place_id: str) -> dict[str, object]:
    place_id = (place_id or "").strip()
    if not place_id:
        raise HTTPException(400, "place_id obrigatório")
    rows = _load_claim_seed_rows()
    row = next((r for r in rows if str(r.get("place_id", "")).strip() == place_id), None)
    if not row:
        raise HTTPException(404, "seed não encontrado")
    return _safe_claim_seed_payload(row)


def _claim_estabelecimento_table_exists() -> bool:
    c = db()
    try:
        row = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='estabelecimento_claims'"
        ).fetchone()
        return bool(row)
    finally:
        c.close()


def _claim_estabelecimento_total() -> int:
    c = db()
    try:
        row = c.execute("SELECT COUNT(*) AS n FROM estabelecimento_claims").fetchone()
        return int(row["n"] if row else 0)
    finally:
        c.close()


def _claim_estabelecimento_updated_at() -> str:
    c = db()
    try:
        row = c.execute(
            "SELECT MAX(COALESCE(updated_at, created_at)) AS ts FROM estabelecimento_claims"
        ).fetchone()
        return str(row["ts"] or "") if row else ""
    finally:
        c.close()


def _claim_estabelecimento_seed_row(place_id: str) -> dict[str, object]:
    rows = _load_claim_seed_rows()
    row = next((r for r in rows if str(r.get("place_id", "")).strip() == place_id), None)
    if not row:
        raise HTTPException(404, "seed não encontrado")
    return row


def _claim_estabelecimento_safe_payload(row: dict[str, object], status: str) -> dict[str, object]:
    return {
        "ok": True,
        "claimed": True,
        "place_id": row.get("place_id", ""),
        "claim_slug": row.get("claim_slug", ""),
        "nome_comercial": row.get("nome_comercial", ""),
        "segmento": row.get("segmento", ""),
        "telefone": row.get("telefone", ""),
        "endereco": row.get("endereco", ""),
        "status": status,
    }


def _claim_estabelecimento_upsert(conta_id: str, row: dict[str, object], claim_slug: str) -> None:
    c = db()
    try:
        now = ts()
        c.execute(
            """
            INSERT INTO estabelecimento_claims(
                conta_id, place_id, claim_slug, nome_comercial, segmento, telefone, endereco,
                status, origem, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(conta_id, place_id) DO UPDATE SET
                claim_slug=excluded.claim_slug,
                nome_comercial=excluded.nome_comercial,
                segmento=excluded.segmento,
                telefone=excluded.telefone,
                endereco=excluded.endereco,
                status=excluded.status,
                origem=excluded.origem,
                updated_at=excluded.updated_at
            """,
            (
                conta_id,
                str(row.get("place_id", "") or "").strip(),
                claim_slug,
                str(row.get("nome_comercial", "") or "").strip(),
                str(row.get("segmento", "") or "").strip(),
                str(row.get("telefone", "") or "").strip(),
                str(row.get("endereco", "") or "").strip(),
                "claimed",
                "onepage_claim",
                now,
                now,
            ),
        )
        c.commit()
    finally:
        c.close()


app = FastAPI(title="ci-api")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "ci-api"}


@app.get("/api/claim-seed/health")
def claim_seed_health():
    rows = _load_claim_seed_rows()
    return {
        "ok": True,
        "total_seeds": len(rows),
        "source": str(MASTER_APP_SEED),
        "updated_at": _claim_seed_updated_at(),
    }


@app.get("/api/claim-seed")
def claim_seed(place_id: str = "", claim_slug: str = ""):
    return _claim_seed_by_place_id(place_id)


@app.get("/api/claim-estabelecimento/health")
def claim_estabelecimento_health():
    return {
        "ok": True,
        "table_exists": _claim_estabelecimento_table_exists(),
        "total_claims": _claim_estabelecimento_total(),
        "source_seed": str(MASTER_APP_SEED),
        "updated_at": _claim_estabelecimento_updated_at(),
    }


@app.post("/api/claim-estabelecimento")
def claim_estabelecimento(p: dict = Body(...), x_token: str = Header(None)):
    conta = conta_do_token(x_token)
    place_id = str(p.get("place_id", "") or "").strip()
    claim_slug = str(p.get("claim_slug", "") or "").strip()
    if not place_id:
        raise HTTPException(400, "place_id obrigatório")
    if not claim_slug:
        raise HTTPException(400, "claim_slug obrigatório")
    row = _claim_estabelecimento_seed_row(place_id)
    safe = _claim_estabelecimento_safe_payload({**row, "claim_slug": claim_slug}, "claimed")
    _claim_estabelecimento_upsert(str(conta["id"]), safe, claim_slug)
    return safe


@app.get("/api/me/claims")
def me_claims(x_token: str = Header(None)):
    conta = conta_do_token(x_token)
    c = db()
    try:
        rows = c.execute(
            """
            SELECT place_id, claim_slug, nome_comercial, segmento, telefone, endereco,
                   status, origem, created_at, updated_at
            FROM estabelecimento_claims
            WHERE conta_id=?
            ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
            """,
            (str(conta["id"]),),
        ).fetchall()
    finally:
        c.close()
    return {
        "ok": True,
        "claims": [
            {
                "place_id": r["place_id"],
                "claim_slug": r["claim_slug"],
                "nome_comercial": r["nome_comercial"],
                "segmento": r["segmento"],
                "telefone": r["telefone"],
                "endereco": r["endereco"],
                "status": r["status"],
                "origem": r["origem"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ],
    }


@app.post("/api/register")
def register(p: dict = Body(...)):
    fone = re.sub(r'\D', '', p.get("fone", ""))
    senha = p.get("senha", "") or ""
    slug = (p.get("slug", "") or "").lower().strip()
    if len(fone) < 10:
        raise HTTPException(400, "telefone inválido")
    if len(senha) < 8:
        raise HTTPException(400, "senha muito curta (mín. 8)")
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "endereço inválido (use letras, números e hífen)")
    c = db()
    if c.execute("SELECT 1 FROM contas WHERE fone=?", (fone,)).fetchone():
        c.close(); raise HTTPException(409, "telefone já cadastrado — faça login")
    if c.execute("SELECT 1 FROM contas WHERE slug=?", (slug,)).fetchone():
        c.close(); raise HTTPException(409, "esse endereço já está em uso")
    salt = secrets.token_hex(8)
    cid = secrets.token_hex(8)
    c.execute("INSERT INTO contas(id,fone,slug,salt,pass_hash,criado) VALUES(?,?,?,?,?,?)",
              (cid, fone, slug, salt, _ph.hash(senha), ts()))
    c.commit(); c.close()
    return {"token": nova_sessao(cid), "slug": slug, "salt": salt}


@app.post("/api/login")
def login(p: dict = Body(...)):
    fone = re.sub(r'\D', '', p.get("fone", ""))
    senha = p.get("senha", "") or ""
    c = db()
    r = c.execute("SELECT * FROM contas WHERE fone=?", (fone,)).fetchone()
    c.close()
    ok = verify_senha(r["pass_hash"] if r else "", senha, r["salt"] if r else "0" * 16)
    if not r or not ok:
        raise HTTPException(401, "telefone ou senha incorretos")
    # Rehash: migra contas legado (PBKDF2) p/ Argon2id no login bem-sucedido.
    if not r["pass_hash"].startswith("$argon2"):
        c = db()
        c.execute("UPDATE contas SET pass_hash=? WHERE id=?", (_ph.hash(senha), r["id"]))
    c.commit(); c.close()
    return {"token": nova_sessao(r["id"]), "slug": r["slug"], "salt": r["salt"]}


# ---------------------------------------------------------------------------
# Admin — Claims
# ---------------------------------------------------------------------------

def _admin_claim_safe(row) -> dict:
    return {k: row[k] for k in ADMIN_SAFE_FIELDS if k in row.keys()}


@app.get("/api/admin/claims/health")
def admin_claims_health(x_admin_token: str = Header(None)):
    _verify_admin(x_admin_token)
    c = db()
    try:
        exists = bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='estabelecimento_claims'"
        ).fetchone())
        total = int(c.execute("SELECT COUNT(*) AS n FROM estabelecimento_claims").fetchone()["n"])
        por_status = {}
        if exists:
            for r in c.execute(
                "SELECT status, COUNT(*) AS n FROM estabelecimento_claims GROUP BY status"
            ).fetchall():
                por_status[r["status"]] = int(r["n"])
        updated_at = ""
        if exists:
            row = c.execute(
                "SELECT MAX(COALESCE(updated_at, created_at)) AS ts FROM estabelecimento_claims"
            ).fetchone()
            updated_at = str(row["ts"] or "") if row else ""
    finally:
        c.close()
    return {
        "ok": True,
        "table_exists": exists,
        "total_claims": total,
        "por_status": por_status,
        "updated_at": updated_at,
    }


@app.get("/api/admin/claims")
def admin_claims_list(
    x_admin_token: str = Header(None),
    status: str = "",
    q: str = "",
    limit: int = 100,
    offset: int = 0,
):
    _verify_admin(x_admin_token)
    c = db()
    try:
        where, params = [], []
        if status:
            where.append("status = ?")
            params.append(status)
        if q:
            where.append("(nome_comercial LIKE ? OR place_id LIKE ? OR telefone LIKE ?)")
            params.extend([f"%{q}%"] * 3)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = int(c.execute(
            f"SELECT COUNT(*) AS n FROM estabelecimento_claims{clause}", params
        ).fetchone()["n"])
        rows = c.execute(
            f"SELECT * FROM estabelecimento_claims{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    finally:
        c.close()
    return {
        "ok": True,
        "total": total,
        "claims": [_admin_claim_safe(r) for r in rows],
    }


@app.patch("/api/admin/claims/{claim_id}")
def admin_claims_update(claim_id: int, p: dict = Body(...), x_admin_token: str = Header(None)):
    _verify_admin(x_admin_token)
    new_status = (p.get("status") or "").strip()
    admin_note = (p.get("admin_note") or "").strip()
    if new_status not in ADMIN_STATUS:
        raise HTTPException(400, f"status inválido: {new_status}")
    c = db()
    try:
        row = c.execute("SELECT * FROM estabelecimento_claims WHERE id=?", (claim_id,)).fetchone()
        if not row:
            c.close()
            raise HTTPException(404, "claim não encontrado")
        now = ts()
        updates = ["status=?", "updated_at=?", "admin_note=?"]
        params = [new_status, now, admin_note or None]
        if new_status == "verified":
            updates.append("verified_at=?")
            params.append(now)
        elif new_status == "rejected":
            updates.append("rejected_at=?")
            params.append(now)
        params.append(claim_id)
        c.execute(
            f"UPDATE estabelecimento_claims SET {', '.join(updates)} WHERE id=?",
            params,
        )
        c.commit()
        updated = c.execute("SELECT * FROM estabelecimento_claims WHERE id=?", (claim_id,)).fetchone()
    finally:
        c.close()
    return {"ok": True, "claim": _admin_claim_safe(updated)}


@app.post("/api/logout")
def logout(x_token: str = Header(None)):
    """Revoga o token no servidor (não só some no cliente)."""
    if x_token:
        c = db()
        c.execute("DELETE FROM sessions WHERE token=?", (x_token,))
        c.commit(); c.close()
    return {"ok": True}


@app.put("/api/backup")
async def put_backup(request: Request, x_token: str = Header(None),
                     x_base_ver: str = Header(None)):
    r = conta_do_token(x_token)
    blob = await request.body()
    if len(blob) > MAX_BACKUP:
        raise HTTPException(413, "backup grande demais")
    if not blob:
        raise HTTPException(400, "backup vazio")
    path = os.path.join(BACKUPS, r["id"] + ".b64")
    cur_ver = (r["backup_ver"] if "backup_ver" in r.keys() and r["backup_ver"] is not None else 0)
    # Optimistic concurrency: se o cliente diz em qual versão baseou (X-Base-Ver) e a
    # nuvem já avançou (outro aparelho), rejeita com 409 — o cliente baixa antes de
    # sobrescrever. Sem o header (ex.: reset de recuperação), grava direto.
    if x_base_ver is not None and os.path.exists(path):
        try:
            base = int(x_base_ver)
        except ValueError:
            base = -1
        if base != cur_ver:
            raise HTTPException(409, {"msg": "conflito — a nuvem tem uma versão mais nova", "ver": cur_ver})
    # 1 nível de histórico (.prev) como rede contra perda silenciosa
    if os.path.exists(path):
        try:
            os.replace(path, path + ".prev")
        except OSError:
            pass
    with open(path, "wb") as f:
        f.write(blob)
    new_ver = cur_ver + 1
    c = db()
    c.execute("UPDATE contas SET backup_ver=? WHERE id=?", (new_ver, r["id"]))
    c.commit(); c.close()
    return {"ok": True, "bytes": len(blob), "ver": new_ver, "em": ts()}


@app.get("/api/backup")
def get_backup(x_token: str = Header(None)):
    r = conta_do_token(x_token)
    path = os.path.join(BACKUPS, r["id"] + ".b64")
    if not os.path.exists(path):
        raise HTTPException(404, "sem backup na nuvem")
    cur_ver = (r["backup_ver"] if "backup_ver" in r.keys() and r["backup_ver"] is not None else 0)
    return PlainTextResponse(open(path, "r", encoding="utf-8").read(),
                             headers={"X-Backup-Ver": str(cur_ver)})


@app.put("/api/loja")
async def put_loja(request: Request, x_token: str = Header(None)):
    r = conta_do_token(x_token)
    html = (await request.body()).decode("utf-8", "ignore")
    if len(html) > MAX_HTML:
        raise HTTPException(413, "página grande demais")
    if "<script" in html.lower():
        raise HTTPException(400, "HTML não pode conter <script>")
    
    # Sanitização contra XSS: remove handlers inline de eventos (onerror, onclick, etc)
    # e desativa links javascript:... substituindo-os por #.
    html_clean = re.sub(r'(?i)\bon[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', html)
    html_clean = re.sub(r'(?i)\bhref\s*=\s*("[^"]*javascript:[^"]*"|\'[^\']*javascript:[^\']*\'|[^\s>]*javascript:[^\s>]+)', 'href="#"', html_clean)
    
    d = os.path.join(LOJAS, r["slug"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_clean)
    return {"ok": True, "url": f"/loja/{r['slug']}/", "em": ts()}


@app.get("/api/me")
def me(x_token: str = Header(None)):
    r = conta_do_token(x_token)
    pub = os.path.exists(os.path.join(LOJAS, r["slug"], "index.html"))
    bak = os.path.exists(os.path.join(BACKUPS, r["id"] + ".b64"))
    tem_rec = bool(r["rec_wrap"]) if "rec_wrap" in r.keys() else False
    ver = (r["backup_ver"] if "backup_ver" in r.keys() and r["backup_ver"] is not None else 0)
    return {"slug": r["slug"], "fone": r["fone"], "publicado": pub,
            "temBackup": bak, "temRecuperacao": tem_rec, "backupVer": ver}


@app.put("/api/recovery")
def set_recovery(p: dict = Body(...), x_token: str = Header(None)):
    """Grava o código de recuperação (embrulho da chave + hash de autorização).
    Ambos vêm do cliente já derivados; o servidor só armazena bytes opacos."""
    r = conta_do_token(x_token)
    rec_hash = (p.get("rec_hash") or "").strip()
    rec_wrap = (p.get("rec_wrap") or "").strip()
    if not rec_hash or not rec_wrap or len(rec_wrap) > 4000:
        raise HTTPException(400, "recuperação inválida")
    c = db()
    c.execute("UPDATE contas SET rec_hash=?, rec_wrap=? WHERE id=?",
              (rec_hash, rec_wrap, r["id"]))
    c.commit(); c.close()
    return {"ok": True}


@app.get("/api/recovery/info")
def recovery_info(fone: str = ""):
    """Devolve o necessário p/ recuperar SEM senha: salt, o embrulho da chave e o
    backup cifrado. Tudo é opaco sem o código de recuperação (que só o dono tem)."""
    fone = re.sub(r'\D', '', fone or "")
    c = db()
    r = c.execute("SELECT * FROM contas WHERE fone=?", (fone,)).fetchone()
    c.close()
    if not r or not (r["rec_wrap"] if "rec_wrap" in r.keys() else None):
        raise HTTPException(404, "conta sem recuperação configurada")
    path = os.path.join(BACKUPS, r["id"] + ".b64")
    backup = open(path, "r", encoding="utf-8").read() if os.path.exists(path) else None
    return {"salt": r["salt"], "rec_wrap": r["rec_wrap"], "backup": backup}


@app.post("/api/recovery/reset")
def recovery_reset(p: dict = Body(...)):
    """Reset de senha autorizado pelo código de recuperação (rec_hash). O cliente
    decifra o backup com a chave recuperada, escolhe nova senha e reembrulha a chave."""
    fone = re.sub(r'\D', '', p.get("fone", ""))
    rec_hash = (p.get("rec_hash") or "").strip()
    new_senha = p.get("new_senha", "") or ""
    new_rec_wrap = (p.get("new_rec_wrap") or "").strip()
    if len(new_senha) < 8:
        raise HTTPException(400, "senha muito curta (mín. 8)")
    c = db()
    r = c.execute("SELECT * FROM contas WHERE fone=?", (fone,)).fetchone()
    if not r or not (r["rec_hash"] if "rec_hash" in r.keys() else None):
        c.close(); raise HTTPException(404, "conta sem recuperação configurada")
    if not secrets.compare_digest(r["rec_hash"], rec_hash):
        c.close(); raise HTTPException(401, "código de recuperação incorreto")
    c.execute("UPDATE contas SET pass_hash=?, rec_wrap=COALESCE(?, rec_wrap) WHERE id=?",
              (_ph.hash(new_senha), new_rec_wrap or None, r["id"]))
    c.commit(); c.close()
    return {"token": nova_sessao(r["id"]), "slug": r["slug"], "salt": r["salt"]}
