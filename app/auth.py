from datetime import datetime, timedelta
from jose import JWTError, jwt
import hmac
import bcrypt
import os

SECRET_KEY = os.getenv("SECRET_KEY", "***SECRET-KEY-REMOVIDA(rotacionada-jun04)***")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

MARI_EMAIL = os.getenv("MARI_EMAIL", "mari@winshubagro.cloud")
# bcrypt hash da senha (gerado fora da app). Mantém compat com o nome antigo da var.
MARI_PASSWORD_HASH = os.getenv("MARI_PASSWORD_HASH") or os.getenv("MARI_PASSWORD", "")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha contra hash bcrypt. Tolera hash ausente/ inválido."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate_user(email: str, password: str):
    # comparação de e-mail em tempo constante (evita enumeração por timing)
    if not hmac.compare_digest(email.strip().lower(), MARI_EMAIL.strip().lower()):
        return False
    if not verify_password(password, MARI_PASSWORD_HASH):
        return False
    return {"email": MARI_EMAIL, "name": "Mari"}


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
