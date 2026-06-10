#!/usr/bin/env python3
"""
scrape_nelore_qualitas.py — Extrai a lista de rebanhos/criadores participantes do
Programa Nelore Qualitas (proprietário, fazenda, cidade, UF).

A página pública https://qualitas.agr.br/criadores-nelore/ é um mapa SVG interativo;
os dados de fato vivem na página Elementor 'criadores-novo', acessível via a REST
API do WordPress (wp-json). Não há técnico nominado por rebanho — as visitas técnicas
são feitas pelos diretores da Qualitas (Émerson Moraes, zootec.; Leonardo Souza, vet.).

Saída: data/nelore_programas/qualitas_rebanhos.json
Uso: python3 scrape_nelore_qualitas.py
Requer: curl no PATH.
"""
import re, json, os, subprocess, html as H

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WPJSON = "https://qualitas.agr.br/wp-json/wp/v2/pages?slug=criadores-novo&_fields=content"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "nelore_programas", "qualitas_rebanhos.json")
UF2ST = {"TO": "Tocantins", "GO": "Goiás", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
         "MG": "Minas Gerais", "SP": "São Paulo", "RO": "Rondônia", "BA": "Bahia",
         "PA": "Pará", "BO": "Bolívia"}


def txt(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def main():
    raw = subprocess.run(["curl", "-sk", "-A", UA, WPJSON], capture_output=True, text=True).stdout
    c = json.loads(raw)[0]["content"]["rendered"]
    recs = []
    # Each breeder block: <strong>OWNER</strong> ... Fazenda: X ... Cidade: Y-UF
    for m in re.finditer(r"<strong>(.*?)</strong>(.*?)(?=<strong>|</ol>)", c, re.S):
        owner = txt(m.group(1)); body = m.group(2)
        if "Fazenda:" not in body and "Agropecuária:" not in body:
            continue
        faz = re.search(r"(?:Fazenda|Agropecuária):\s*([^<]*)", body)
        cid = re.search(r"Cidade:\s*([^<]*)", body)
        site = re.search(r"Website:\s*([^<]*)", body)
        city = txt(cid.group(1)) if cid else ""
        uf = ""
        um = re.search(r"[–-]\s*([A-Z]{2})\s*$", city)
        if um and um.group(1) in UF2ST:
            uf = um.group(1)
        recs.append({"uf": uf, "estado": UF2ST.get(uf, ""), "proprietario": owner,
                     "fazenda": txt(faz.group(1)) if faz else "",
                     "cidade": re.sub(r"\s*[–-]\s*[A-Z]{2}\s*$", "", city).strip(),
                     "website": txt(site.group(1)) if site else ""})
    # backfill blank UF from nearest preceding explicit UF (panels are state-grouped)
    last = ""
    for r in recs:
        if r["uf"]:
            last = r["uf"]
        else:
            r["uf"] = last; r["estado"] = UF2ST.get(last, "")
    seen, clean = set(), []
    for r in recs:
        k = (r["proprietario"], r["fazenda"])
        if k in seen:
            continue
        seen.add(k); clean.append(r)
    out = {"_meta": {"fonte": "Qualitas - Programa Nelore Qualitas", "url": WPJSON,
                     "metodo": "wp-json REST -> HTML Elementor parseado",
                     "tecnicos": ["Émerson Moraes (zootec.)", "Leonardo Souza (vet.)"],
                     "total_rebanhos": len(clean)}, "rebanhos": clean}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
    print(f"Saved {len(clean)} rebanhos -> {OUT}")
    print("NOTE: registros de estados com 1 criador (markup sem <strong>) podem precisar de revisão manual.")


if __name__ == "__main__":
    main()
