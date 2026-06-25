"""Configuração de teste: define o ambiente mínimo ANTES de importar `auth`/`main`.

`auth.py` faz `raise RuntimeError` se SECRET_KEY não estiver setada (proteção contra
assinar JWT com chave pública). Os testes não tocam o banco — exercitam só as funções
puras de segurança (token, senha, TOTP), que são o núcleo crítico da aplicação.
"""
import os

# senha "teste-123" em bcrypt (gerada offline só para o teste; não é credencial real)
_TEST_HASH = "$2b$10$aD2CUNab.GYr.bI2JCYs5eon6Xji/wFQexfh/pXxLRsxTO.Fv5JRm"

os.environ.setdefault("SECRET_KEY", "x" * 64)
os.environ.setdefault("MARI_EMAIL", "mari@winshubagro.cloud")
os.environ.setdefault("MARI_PASSWORD_HASH", _TEST_HASH)
# MFA desligado nos testes (sem MFA_TOTP_SECRET) → verify_totp deve liberar.
os.environ.pop("MFA_TOTP_SECRET", None)
