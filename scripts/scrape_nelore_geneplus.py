#!/usr/bin/env python3
"""
scrape_nelore_geneplus.py — Extrai a lista pública de fazendas/rebanhos Nelore
certificados CEIP pelo Programa Embrapa Geneplus, com município/UF e contagem de
animais CEIP por fazenda/ano.

Fonte: https://geneplus.com.br/certificadosCeip/nelore/ano/{ANO}
       (cada fazenda tem um PDF: https://geneplus.com.br/certificadosCeip/download/{ID})

Saída: data/nelore_programas/geneplus_ceip.json

Campos por fazenda: fazenda, municipio, uf, anos[], total_animais_ceip, pdf_url.
NOTA: a ficha CEIP do Geneplus NÃO traz proprietário nem consultor nominado;
o responsável técnico é institucional ("Programa Embrapa Geneplus").

Uso: python3 scrape_nelore_geneplus.py [ano_inicial ano_final]
Requer: curl, pdftotext (poppler-utils) no PATH.
"""
import re, json, os, sys, subprocess, tempfile, glob
from collections import defaultdict

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "https://geneplus.com.br"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "nelore_programas", "geneplus_ceip.json")


def curl(url, out=None, binary=False):
    cmd = ["curl", "-sk", "-A", UA, "-L", "--max-time", "60", url]
    if out:
        cmd += ["-o", out]
        subprocess.run(cmd, check=False)
        return out
    return subprocess.run(cmd, capture_output=True, text=not binary).stdout


def get_year_page(ano):
    """Return list of (farm_label, download_id) for a given year."""
    html = curl(f"{BASE}/certificadosCeip/nelore/ano/{ano}")
    ids = re.findall(r"/certificadosCeip/download/(\d+)", html)
    farms = re.findall(
        r"Nelore\s*</td>\s*<td[^>]*>\s*" + re.escape(str(ano)) + r"\s*</td>\s*<td[^>]*>(.*?)</td>",
        html, re.S)
    farms = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", f)).strip() for f in farms]
    return list(zip(farms, ids))


def parse_pdf(pdf_path):
    txt_path = pdf_path + ".txt"
    subprocess.run(["pdftotext", "-layout", pdf_path, txt_path], capture_output=True)
    t = open(txt_path, errors="replace").read()
    fz = re.search(r"Fazenda:\s*(.+?)\s*-\s*([A-ZÀ-Ÿ ]+?)\s*/\s*([A-Z]{2})", t)
    fazenda = municipio = uf = ""
    if fz:
        fazenda, municipio, uf = fz.group(1).strip(), fz.group(2).strip(), fz.group(3).strip()
    else:
        fz2 = re.search(r"Fazenda:\s*(.+)", t)
        if fz2:
            fazenda = fz2.group(1).strip()[:80]
    n = len(re.findall(r"CEIP N[ºo°]:", t))
    return fazenda, municipio, uf, n


def main(y0=2019, y1=2025):
    tmp = tempfile.mkdtemp(prefix="gp_ceip_")
    id_meta = {}     # id -> {ano, farm_label}
    for ano in range(y0, y1 + 1):
        for farm, fid in get_year_page(ano):
            id_meta.setdefault(fid, {"ano": str(ano), "farm_label": farm})
    fichas = []
    for fid, meta in sorted(id_meta.items(), key=lambda kv: int(kv[0])):
        pdf = os.path.join(tmp, f"{fid}.pdf")
        curl(f"{BASE}/certificadosCeip/download/{fid}", out=pdf, binary=True)
        if not os.path.getsize(pdf):
            continue
        fazenda, municipio, uf, n = parse_pdf(pdf)
        fichas.append({"download_id": fid, "ano": meta["ano"],
                       "fazenda": fazenda or meta["farm_label"], "municipio": municipio,
                       "uf": uf, "n_animais_ceip": n,
                       "pdf_url": f"{BASE}/certificadosCeip/download/{fid}"})
    farms = defaultdict(lambda: {"anos": set(), "total": 0})
    for r in fichas:
        k = (r["fazenda"], r["municipio"], r["uf"])
        farms[k]["anos"].add(r["ano"]); farms[k]["total"] += r["n_animais_ceip"]
    uniq = [{"fazenda": k[0], "municipio": k[1], "uf": k[2], "anos": sorted(v["anos"]),
             "total_animais_ceip": v["total"]} for k, v in farms.items()]
    uniq.sort(key=lambda x: -x["total_animais_ceip"])
    out = {"_meta": {"fonte": "Geneplus (Embrapa) - Programa Nelore CEIP",
                     "metodo": "HTML + PDF (pdftotext)", "mapa": "registro MAPA nº 25",
                     "total_fazendas": len(uniq), "total_fichas": len(fichas)},
           "fazendas": uniq, "fichas_por_ano": fichas}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
    print(f"Saved {len(uniq)} fazendas / {len(fichas)} fichas -> {OUT}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]), int(a[1])) if len(a) == 2 else main()
