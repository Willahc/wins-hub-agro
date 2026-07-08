#!/usr/bin/env python3
"""Validador do painel admin de claims.

Verifica:
  - app.py possui endpoints admin
  - admin-claims.html existe e contém referências corretas
  - tabela estabelecimento_claims tem colunas admin_note, verified_at, rejected_at
  - endpoints admin exigem x-admin-token
  - payloads admin não retornam campos proibidos
"""
import os, re, sqlite3, sys

BASE = "/root/wins_agro_v1"
APP = os.path.join(BASE, "ci-api/app.py")
HTML = os.path.join(BASE, "ci/admin-claims.html")
DB = os.path.join(BASE, "ci-data/ci.db")

PROHIBITED = {
    "cnpj", "score", "lead_tier", "tier", "prioridade", "dor",
    "reclamacoes", "pitch", "confidence", "fontes_json",
}
errors = []


def _contains_prohibited(text, field):
    """Verifica se o campo proibido aparece como palavra inteira (evita falsos positivos)."""
    return bool(re.search(r'\b' + re.escape(field) + r'\b', text))


def ok(msg):
    print(f"  ✓ {msg}")


def fail(msg):
    errors.append(msg)
    print(f"  ✗ {msg}")


def main():
    print("=" * 60)
    print("Validador — Admin Claims")
    print("=" * 60)

    # 1. app.py endpoints admin
    print("\n[1] Endpoints admin no app.py:")
    code = open(APP, encoding="utf-8").read()
    for ep in ("/api/admin/claims", "/api/admin/claims/health"):
        if ep in code:
            ok(f"endpoint {ep} encontrado")
        else:
            fail(f"endpoint {ep} NÃO encontrado")
    if "x_admin_token" in code or "x-admin-token" in code:
        ok("header x-admin-token presente no código")
    else:
        fail("header x-admin-token NÃO encontrado no código")
    if "_verify_admin" in code:
        ok("função _verify_admin presente")
    else:
        fail("função _verify_admin NÃO encontrada")

    # 2. admin-claims.html
    print("\n[2] Página admin-claims.html:")
    if os.path.isfile(HTML):
        ok("arquivo existe")
        h = open(HTML, encoding="utf-8").read()
        if "/api/admin/claims" in h:
            ok("contém /api/admin/claims")
        else:
            fail("NÃO contém /api/admin/claims")
        if "x-admin-token" in h:
            ok("contém x-admin-token")
        else:
            fail("NÃO contém x-admin-token")
        for field in PROHIBITED:
            if _contains_prohibited(h, field):
                fail(f"contém campo proibido: {field}")
        if not any(_contains_prohibited(h, f) for f in PROHIBITED):
            ok("nenhum campo proibido encontrado na página")
    else:
        fail("admin-claims.html NÃO existe")

    # 3. Colunas na tabela
    print("\n[3] Colunas da tabela estabelecimento_claims:")
    try:
        c = sqlite3.connect(DB, timeout=10)
        cols = {row[1] for row in c.execute("PRAGMA table_info(estabelecimento_claims)").fetchall()}
        c.close()
        for col in ("admin_note", "verified_at", "rejected_at"):
            if col in cols:
                ok(f"coluna {col} existe")
            else:
                fail(f"coluna {col} NÃO existe")
    except Exception as e:
        fail(f"erro ao acessar banco: {e}")

    # 4. Campos proibidos no código admin
    print("\n[4] Campos proibidos no app.py (endpoints admin):")
    admin_section = code[code.index("/api/admin/claims"):]
    for field in PROHIBITED:
        if _contains_prohibited(admin_section, field):
            fail(f"campo proibido '{field}' encontrado na seção admin")
    if not any(_contains_prohibited(admin_section, f) for f in PROHIBITED):
        ok("nenhum campo proibido na seção admin")

    # Resultado
    print("\n" + "=" * 60)
    if errors:
        print(f"FALHAS: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TODAS AS VERIFICAÇÕES OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
