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
import argon2
from fastapi import FastAPI, HTTPException, Header, Request, Body
from fastapi.responses import PlainTextResponse

DATA = os.environ.get("CI_DATA", "/data")
LOJAS = os.environ.get("CI_LOJAS", "/data/lojas")
DB = os.path.join(DATA, "ci.db")
BACKUPS = os.path.join(DATA, "backups")
for d in (DATA, LOJAS, BACKUPS):
    os.makedirs(d, exist_ok=True)

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{2,39}$')
MAX_BACKUP = 6_000_000   # ~6 MB de ciphertext
MAX_HTML   = 2_000_000


def db():
    # WAL + busy_timeout: evita "database is locked" sob escrita concorrente
    # (vários backups/registros ao mesmo tempo). WAL é persistente; timeout é por conexão.
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    return c


def init_db():
    c = db()
    c.executescript("""
      CREATE TABLE IF NOT EXISTS contas(
        id TEXT PRIMARY KEY, fone TEXT UNIQUE, slug TEXT UNIQUE,
        salt TEXT, pass_hash TEXT, criado TEXT);
      CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY, conta_id TEXT, criado TEXT);
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
    c.commit(); c.close()


init_db()


_ph = argon2.PasswordHasher()          # Argon2id (defaults seguros)
SESSAO_DIAS = 60                       # validade do token de sessão


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


app = FastAPI(title="ci-api")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "ci-api"}


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
        # cardápio é estático; bloqueia injeção de script no HTML publicado
        raise HTTPException(400, "HTML não pode conter <script>")
    d = os.path.join(LOJAS, r["slug"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
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
