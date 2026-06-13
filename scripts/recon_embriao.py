#!/usr/bin/env python3
"""
recon_embriao.py — Recon de fontes GRATUITAS de embriões / FIV bovinos no Brasil.

Conclusão da recon (jun/2026): a fonte mais tratável e ESTRUTURADA é a loja
oficial CRV Brasil (plataforma Tray/tcdn). Cada página de categoria de embrião
embute um JSON `listProducts` com nome (DOADORA x TOURO), preço e SKU.

Outras fontes avaliadas:
  - erural.net / Lance Rural / Superbid / Central Leilões: catálogos de leilão
    de embriões FIV. Páginas client-rendered (Next.js sem __NEXT_DATA__ no HTML
    estático) -> precisa de browser headless. Catálogos PDF existem mas formato
    livre (sire x doadora em prosa) -> parsing frágil, NÃO estruturado.
  - ABS Global (IVB NEO / ABS NEO) e In Vitro Brasil: produtos "neo" são cotação,
    sem preço público por acasalamento.
  - Instagram de criatórios: contato por bio, não estruturado.

Este script enumera as categorias de embrião da CRV via sitemap e extrai o
`listProducts` de cada uma. Salva /tmp/embrioes_crv.json (dentro do container API).
Rodar:  docker exec -i wins_agro_v1_api_1 python - < scripts/recon_embriao.py
        depois: docker cp wins_agro_v1_api_1:/tmp/embrioes_crv.json ...
"""
import re, json, sys
import httpx

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
BASE = "https://loja.crvbrasil.com.br"


def get(u):
    return httpx.get(u, headers=H, verify=False, follow_redirects=True, timeout=90)


def embryo_categories():
    """Lê o sitemap e devolve as URLs de categoria-folha de embrião."""
    idx = get(f"{BASE}/sitemap.xml").text
    cats = []
    for sm in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx):
        t = get(sm).text
        for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", t):
            # folhas de embrião = têm subcategoria (>= 5 segmentos de path)
            if "/embrioes/" in u and u.rstrip("/").count("/") >= 5:
                cats.append(u.rstrip("/"))
    return sorted(set(cats))


def parse_list_products(html):
    """Extrai o array JSON `listProducts` embutido na página de categoria."""
    m = re.search(r'"listProducts"\s*:\s*(\[.*?\])\s*[},]', html, re.S)
    if not m:
        return []
    blob = m.group(1)
    # o JSON usa \uXXXX e aspas normais -> json.loads resolve
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # tenta fechar no primeiro ] balanceado
        depth = 0
        for i, ch in enumerate(blob):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(blob[: i + 1])
        return []


def main():
    cats = embryo_categories()
    rows = []
    for c in cats:
        try:
            html = get(c + "/").text
            prods = parse_list_products(html)
            for p in prods:
                rows.append(
                    {
                        "id_product": p.get("idProduct"),
                        "category": p.get("category"),
                        "category_url": c,
                        "nome": p.get("nameProduct"),
                        "sell_price": p.get("sellPrice"),
                        "price": p.get("price"),
                        "reference": p.get("reference"),
                        "url": p.get("urlProduct"),
                        "img": p.get("urlImage"),
                    }
                )
            print(f"  {c.split('/embrioes/')[-1]:45} -> {len(prods)} produtos", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  ERRO {c}: {e}", file=sys.stderr)
    # dedup por id_product
    seen, uniq = set(), []
    for r in rows:
        k = r["id_product"] or r["url"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    with open("/tmp/embrioes_crv.json", "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)
    print(f"\nCategorias: {len(cats)} | Produtos únicos: {len(uniq)} -> /tmp/embrioes_crv.json", file=sys.stderr)


if __name__ == "__main__":
    main()
