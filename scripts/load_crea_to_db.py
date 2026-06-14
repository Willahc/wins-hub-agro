#!/usr/bin/env python3
"""
load_crea_to_db.py — Ingest the harvested JSONL rosters into
prospeccao.tecnico_crea.

Sources:
  - /tmp/crea_go.jsonl       (CREA-GO public API: agrônomos/zootecnistas, name+título+situação, no contact)
  - /tmp/abcz_jurados.jsonl  (ABCZ Colégio de Jurados: zootec/agro/vet WITH phone+email, no UF)

Run on the HOST (psql reachable via docker exec). Files are docker-cp'd to host /tmp first.
"""
import json, sys, subprocess

DB = ["docker", "exec", "-i", "wins_agro_v1_db_1", "psql", "-U", "postgres", "-d", "wins_agro"]


def sql(stmt):
    p = subprocess.run(DB + ["-v", "ON_ERROR_STOP=1", "-c", stmt],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr)
        raise SystemExit(f"SQL failed: {stmt[:80]}")
    return p.stdout


def copy_rows(rows, cols):
    """Build a single psql script: create temp table, COPY FROM STDIN (inline CSV),
    then upsert. Piped to psql via stdin so \\copy/COPY and SQL share one session."""
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for r in rows:
        w.writerow([("" if r.get(c) is None else str(r.get(c)).replace("\r", " ").replace("\n", " "))
                    for c in cols])
    data = buf.getvalue()
    collist = ",".join(cols)
    coldef = ",".join(f"{c} text" for c in cols)
    script = (
        "\\set ON_ERROR_STOP on\n"
        "BEGIN;\n"
        f"CREATE TEMP TABLE _stg ({coldef}) ON COMMIT DROP;\n"
        f"\\copy _stg ({collist}) FROM STDIN WITH (FORMAT csv, NULL '')\n"
        + data
        + "\\.\n"
        + UPSERT + "\n"
        "COMMIT;\n"
    )
    p = subprocess.run(DB, input=script, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + "\n" + p.stderr)
        raise SystemExit("copy/upsert failed")
    return p.stdout


UPSERT = """
INSERT INTO prospeccao.tecnico_crea
  (cnpj_or_cpf, nome, registro_crea, titulo, uf, municipio, situacao, email, telefone, fonte, fonte_url)
SELECT NULLIF(cnpj_or_cpf,''), nome, NULLIF(registro_crea,''), NULLIF(titulo,''),
       NULLIF(uf,''), NULLIF(municipio,''), NULLIF(situacao,''),
       NULLIF(email,''), NULLIF(telefone,''), NULLIF(fonte,''), NULLIF(fonte_url,'')
FROM _stg
ON CONFLICT (uf, registro_crea, nome) DO UPDATE SET
   titulo = COALESCE(EXCLUDED.titulo, prospeccao.tecnico_crea.titulo),
   situacao = COALESCE(EXCLUDED.situacao, prospeccao.tecnico_crea.situacao),
   email = COALESCE(EXCLUDED.email, prospeccao.tecnico_crea.email),
   telefone = COALESCE(EXCLUDED.telefone, prospeccao.tecnico_crea.telefone);
"""

COLS = ["cnpj_or_cpf", "nome", "registro_crea", "titulo", "uf", "municipio",
        "situacao", "email", "telefone", "fonte", "fonte_url"]


def load_jsonl(path, fonte, field_map=None):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            row = {c: None for c in COLS}
            for c in COLS:
                if c in d:
                    row[c] = d[c]
            if field_map:
                for k, v in field_map.items():
                    row[k] = d.get(v)
            row["fonte"] = fonte
            rows.append(row)
    return rows


def main():
    all_rows = []
    # CREA-GO
    try:
        all_rows += load_jsonl("/tmp/crea_go.jsonl", "crea_go_api")
    except FileNotFoundError:
        sys.stderr.write("no crea_go.jsonl\n")
    # ABCZ jurados
    try:
        all_rows += load_jsonl("/tmp/abcz_jurados.jsonl", "abcz_jurados",
                               field_map={"email": "email", "telefone": "telefone"})
    except FileNotFoundError:
        sys.stderr.write("no abcz_jurados.jsonl\n")

    # ABCZ rows have NULL uf & registro -> ON CONFLICT(uf,registro,nome) won't fire on NULLs.
    # Pre-dedup ABCZ in-memory by nome so we don't double-insert across reruns is handled by
    # a guard: delete existing abcz rows first, then insert fresh.
    sql("DELETE FROM prospeccao.tecnico_crea WHERE fonte = 'abcz_jurados';")

    # split: crea rows go through upsert; abcz rows plain insert (already cleared)
    crea = [r for r in all_rows if r["fonte"] == "crea_go_api"]
    abcz = [r for r in all_rows if r["fonte"] == "abcz_jurados"]

    if crea:
        copy_rows(crea, COLS)
        sys.stderr.write(f"upserted {len(crea)} CREA-GO rows\n")
    if abcz:
        # dedup abcz by nome
        seen = set(); dd = []
        for r in abcz:
            k = (r["nome"] or "").upper()
            if k in seen:
                continue
            seen.add(k); dd.append(r)
        copy_rows(dd, COLS)
        sys.stderr.write(f"inserted {len(dd)} ABCZ rows\n")

    print(sql("SELECT fonte, titulo, count(*) FROM prospeccao.tecnico_crea GROUP BY 1,2 ORDER BY 1,3 DESC;"))


if __name__ == "__main__":
    main()
