#!/usr/bin/env python3
"""
normaliza_contatos.py — passa os telefones/e-mails crus da base por libs maduras
(phonenumbers / email-validator / validate-docbr via scripts/lib/br_validate.py),
classifica MÓVEL vs FIXO (WhatsApp-capable) e materializa em
prospeccao.telefone_normalizado.

Por que: o canal real do produtor é WhatsApp -> precisamos saber QUAIS telefones
da base são celular. Telefone da Receita costuma ser fixo; isto quantifica o gap
e entrega a lista pronta de móveis para o handoff comercial.

NÃO altera tabelas existentes — só cria/preenche prospeccao.telefone_normalizado.
Idempotente (TRUNCATE + reinsert).

Rodar no host (porta 5432 publicada em 127.0.0.1):
    set -a && . ./.env && set +a
    PGPASSWORD="$POSTGRES_PASSWORD" /root/.venv-wins-tools/bin/python \
        scripts/normaliza_contatos.py [--mx] [--limit N] [--dry-run]

--mx     também checa MX dos e-mails (mais lento)
--dry-run só relatório, não grava
"""
import os, sys, argparse
import psycopg2, psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.br_validate import normaliza_telefone, normaliza_email

DDL = """
CREATE TABLE IF NOT EXISTS prospeccao.telefone_normalizado (
    cnpj            char(14)    NOT NULL,
    telefone_raw    varchar(30),
    e164            varchar(20),
    valido          boolean     NOT NULL DEFAULT false,
    movel           boolean     NOT NULL DEFAULT false,
    tipo            varchar(16),
    ddd             varchar(3),
    operadora       varchar(40),
    motivo          varchar(40),
    atualizado_em   timestamptz DEFAULT now(),
    PRIMARY KEY (cnpj)
);
CREATE INDEX IF NOT EXISTS idx_telnorm_movel ON prospeccao.telefone_normalizado(movel) WHERE movel;
CREATE INDEX IF NOT EXISTS idx_telnorm_e164  ON prospeccao.telefone_normalizado(e164);
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mx", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn = psycopg2.connect(host=os.environ.get("PGHOST", "127.0.0.1"),
                          port=int(os.environ.get("PGPORT", 5432)),
                          dbname="wins_agro", user="postgres", password=pw)
    cn.autocommit = False
    c = cn.cursor()

    if not args.dry_run:
        c.execute(DDL)
        c.execute("TRUNCATE prospeccao.telefone_normalizado;")

    lim = f"LIMIT {args.limit}" if args.limit else ""
    c.execute(f"""
        SELECT cnpj, telefone FROM prospeccao.cnpj_rural
        WHERE telefone IS NOT NULL AND telefone <> '' {lim}
    """)
    rows = c.fetchall()

    stats = {"total": 0, "validos": 0, "movel": 0, "fixo": 0, "invalido": 0}
    batch = []
    for cnpj, tel in rows:
        stats["total"] += 1
        r = normaliza_telefone(tel)
        if r["valido"]:
            stats["validos"] += 1
            stats["movel" if r["movel"] else "fixo"] += 1
        else:
            stats["invalido"] += 1
        batch.append((cnpj, tel, r["e164"], r["valido"], r["movel"],
                      r["tipo"], r["ddd"], r["operadora"], r["motivo"]))

    if not args.dry_run and batch:
        psycopg2.extras.execute_values(c, """
            INSERT INTO prospeccao.telefone_normalizado
              (cnpj, telefone_raw, e164, valido, movel, tipo, ddd, operadora, motivo)
            VALUES %s
            ON CONFLICT (cnpj) DO UPDATE SET
              telefone_raw=EXCLUDED.telefone_raw, e164=EXCLUDED.e164,
              valido=EXCLUDED.valido, movel=EXCLUDED.movel, tipo=EXCLUDED.tipo,
              ddd=EXCLUDED.ddd, operadora=EXCLUDED.operadora, motivo=EXCLUDED.motivo,
              atualizado_em=now()
        """, batch, page_size=1000)
        cn.commit()

    # --- e-mails (relatório; não grava, email_valido já é a tabela canônica) ---
    c.execute("SELECT email FROM prospeccao.cnpj_rural WHERE email IS NOT NULL AND email<>''")
    em = c.fetchall()
    em_ok = sum(1 for (e,) in em if normaliza_email(e, checar_mx=args.mx)["valido"])

    print("=== TELEFONES ===")
    for k, v in stats.items():
        pct = f"{100*v/stats['total']:.1f}%" if stats["total"] and k != "total" else ""
        print(f"  {k:10s}: {v:>7d} {pct}")
    print(f"  -> WhatsApp-capable (móveis válidos): {stats['movel']}")
    print("=== E-MAILS (sintaxe%s) ===" % (" + MX" if args.mx else ""))
    print(f"  total: {len(em)}  validos: {em_ok}  ({100*em_ok/len(em):.1f}%)" if em else "  (vazio)")
    print("DRY-RUN — nada gravado" if args.dry_run else
          "Gravado em prospeccao.telefone_normalizado")
    cn.close()

if __name__ == "__main__":
    main()
