"""Testes de caracterização do núcleo de autenticação (auth.py).

Rede de segurança mínima: trava o comportamento atual de token/senha/MFA para que a
modularização futura do monolito (extração de routers/serviços) não regrida em silêncio.
Nenhum acesso a banco — só funções puras.
"""
import time

import jwt
import pytest

import auth


def test_token_roundtrip():
    tok = auth.create_access_token({"sub": "mari@winshubagro.cloud", "name": "Mari"})
    claims = auth.decode_token(tok)
    assert claims is not None
    assert claims["sub"] == "mari@winshubagro.cloud"
    assert "exp" in claims


def test_token_invalido_retorna_none():
    assert auth.decode_token("nao-e-um-token") is None


def test_token_assinado_com_outra_chave_e_rejeitado():
    forjado = jwt.encode({"sub": "x", "exp": time.time() + 999}, "chave-errada", algorithm="HS256")
    assert auth.decode_token(forjado) is None


def test_token_expirado_retorna_none():
    expirado = jwt.encode(
        {"sub": "x", "exp": int(time.time()) - 10}, auth.SECRET_KEY, algorithm=auth.ALGORITHM
    )
    assert auth.decode_token(expirado) is None


def test_verify_password():
    assert auth.verify_password("teste-123", auth.MARI_PASSWORD_HASH) is True
    assert auth.verify_password("senha-errada", auth.MARI_PASSWORD_HASH) is False
    assert auth.verify_password("qualquer", "") is False


def test_verify_totp_liberado_quando_mfa_desligado():
    # conftest não setou MFA_TOTP_SECRET → MFA desligado → libera
    assert auth.MFA_ENABLED is False
    assert auth.verify_totp("") is True


@pytest.mark.parametrize(
    "email,senha,ok",
    [
        ("mari@winshubagro.cloud", "teste-123", True),
        ("MARI@winshubagro.cloud", "teste-123", True),  # e-mail case-insensitive
        ("mari@winshubagro.cloud", "senha-errada", False),
        ("intruso@x.com", "teste-123", False),
    ],
)
def test_authenticate_user(email, senha, ok):
    res = auth.authenticate_user(email, senha)
    assert bool(res) is ok
    if ok:
        assert res["email"] == auth.MARI_EMAIL
