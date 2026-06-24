"""ci-api — backend mínimo do Cliente Inteligente (Fase 2, Tier 1).

Capacidades:
  - Contas leves (telefone + senha → token de sessão).
  - Backup na nuvem: o app cifra o blob NO CLIENTE (AES-GCM via WebCrypto) e sobe
    o ciphertext em base64. O servidor guarda BYTES OPACOS — nunca vê os dados.
  - Publicar cardápio: o app gera o HTML estático e o servidor o grava em
    /loja/<slug>/index.html (servido pelo nginx). Pedido do cliente final volta por wa.me.

Sem dependência de SMS/Cloud API. SQLite + filesystem. Isolamento por token→conta.
"""
import os, re, time, json, secrets, hashlib, sqlite3
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
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
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
    c.commit(); c.close()


init_db()


def hash_senha(senha, salt):
    return hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 120000).hex()


def nova_sessao(conta_id):
    token = secrets.token_urlsafe(24)
    c = db()
    c.execute("INSERT INTO sessions VALUES(?,?,?)", (token, conta_id, ts()))
    c.commit(); c.close()
    return token


def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def conta_do_token(token):
    if not token:
        raise HTTPException(401, "sem token")
    c = db()
    r = c.execute(
        "SELECT c.* FROM contas c JOIN sessions s ON s.conta_id=c.id WHERE s.token=?",
        (token,)).fetchone()
    c.close()
    if not r:
        raise HTTPException(401, "sessão inválida — entre de novo")
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
    if len(senha) < 4:
        raise HTTPException(400, "senha muito curta (mín. 4)")
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "endereço inválido (use letras, números e hífen)")
    c = db()
    if c.execute("SELECT 1 FROM contas WHERE fone=?", (fone,)).fetchone():
        c.close(); raise HTTPException(409, "telefone já cadastrado — faça login")
    if c.execute("SELECT 1 FROM contas WHERE slug=?", (slug,)).fetchone():
        c.close(); raise HTTPException(409, "esse endereço já está em uso")
    salt = secrets.token_hex(8)
    cid = secrets.token_hex(8)
    c.execute("INSERT INTO contas VALUES(?,?,?,?,?,?)",
              (cid, fone, slug, salt, hash_senha(senha, salt), ts()))
    c.commit(); c.close()
    return {"token": nova_sessao(cid), "slug": slug, "salt": salt}


@app.post("/api/login")
def login(p: dict = Body(...)):
    fone = re.sub(r'\D', '', p.get("fone", ""))
    senha = p.get("senha", "") or ""
    c = db()
    r = c.execute("SELECT * FROM contas WHERE fone=?", (fone,)).fetchone()
    c.close()
    if not r or r["pass_hash"] != hash_senha(senha, r["salt"]):
        raise HTTPException(401, "telefone ou senha incorretos")
    return {"token": nova_sessao(r["id"]), "slug": r["slug"], "salt": r["salt"]}


@app.put("/api/backup")
async def put_backup(request: Request, x_token: str = Header(None)):
    r = conta_do_token(x_token)
    blob = await request.body()
    if len(blob) > MAX_BACKUP:
        raise HTTPException(413, "backup grande demais")
    with open(os.path.join(BACKUPS, r["id"] + ".b64"), "wb") as f:
        f.write(blob)
    return {"ok": True, "bytes": len(blob), "em": ts()}


@app.get("/api/backup")
def get_backup(x_token: str = Header(None)):
    r = conta_do_token(x_token)
    path = os.path.join(BACKUPS, r["id"] + ".b64")
    if not os.path.exists(path):
        raise HTTPException(404, "sem backup na nuvem")
    return PlainTextResponse(open(path, "r", encoding="utf-8").read())


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
    return {"slug": r["slug"], "fone": r["fone"], "publicado": pub, "temBackup": bak}
