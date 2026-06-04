from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

SECRET_KEY = os.getenv("SECRET_KEY", "***SECRET-KEY-REMOVIDA(rotacionada-jun04)***")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

MARI_EMAIL = os.getenv("MARI_EMAIL", "mari@winshubagro.cloud")
MARI_PASSWORD_HASH = os.getenv("MARI_PASSWORD", "***SENHA-PG-REMOVIDA(rotacionada-jun08)***")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def authenticate_user(email: str, password: str):
    if email != MARI_EMAIL:
        return False
    if password != MARI_PASSWORD_HASH:
        return False
    return {"email": email, "name": "Mari"}


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
