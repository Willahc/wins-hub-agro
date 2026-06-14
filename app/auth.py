from datetime import datetime, timedelta, timezone
import jwt  # PyJWT (python-jose foi removido: CVE-2024-33663/33664 sem fix upstream)
import hmac
import bcrypt
import os
import pyotp

_DEFAULT_SECRET = "CHANGE-ME-set-SECRET_KEY-in-env"
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
# Falha cedo se a chave não foi configurada: assinar JWT com uma string pública
# permitiria forjar sessões. Defina SECRET_KEY no .env (64+ chars aleatórios).
if SECRET_KEY == _DEFAULT_SECRET:
    raise RuntimeError(
        "SECRET_KEY não configurada — defina a variável de ambiente SECRET_KEY "
        "(ex.: openssl rand -hex 32) antes de subir a aplicação."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

MARI_EMAIL = os.getenv("MARI_EMAIL", "mari@winshubagro.cloud")
# bcrypt hash da senha (gerado fora da app). Mantém compat com o nome antigo da var.
MARI_PASSWORD_HASH = os.getenv("MARI_PASSWORD_HASH") or os.getenv("MARI_PASSWORD", "")

# 2º fator (TOTP/Google Authenticator). OPCIONAL: só é exigido quando MFA_TOTP_SECRET
# está configurado no .env. Sem ele, o login segue só com senha (não quebra nada).
MFA_TOTP_SECRET = os.getenv("MFA_TOTP_SECRET", "").strip()
MFA_ENABLED = bool(MFA_TOTP_SECRET)


def verify_totp(code: str) -> bool:
    """True se o MFA está desligado, ou se o código de 6 dígitos confere (janela ±1
    p/ tolerar drift de relógio)."""
    if not MFA_ENABLED:
        return True
    if not code:
        return False
    try:
        return pyotp.TOTP(MFA_TOTP_SECRET).verify(str(code).strip().replace(" ", ""), valid_window=1)
    except Exception:
        return False


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha contra hash bcrypt. Tolera hash ausente/ inválido."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate_user(email: str, password: str, code: str = None):
    # comparação de e-mail em tempo constante (evita enumeração por timing)
    if not hmac.compare_digest(email.strip().lower(), MARI_EMAIL.strip().lower()):
        return False
    if not verify_password(password, MARI_PASSWORD_HASH):
        return False
    if not verify_totp(code):   # 2º fator: se ativo, exige código TOTP válido
        return False
    return {"email": MARI_EMAIL, "name": "Mari"}


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        # PyJWT valida exp por padrão e rejeita alg diferente da whitelist
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
