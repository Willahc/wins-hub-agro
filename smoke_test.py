#!/usr/bin/env python3
"""Smoke test da demo WiNS Hub Agro contra o nginx real (SNI -> cert válido).
Cunha JWT com a SECRET_KEY do .env (middleware só checa assinatura) e percorre
todas as seções + camadas do mapa, capturando console/CSP/erros de rede.
"""
import os, sys, json, datetime
from pathlib import Path

# --- carrega SECRET_KEY do .env sem dependência externa ---
env = {}
for line in Path("/root/wins_agro_v1/.env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
EMAIL = env.get("MARI_EMAIL", "mari@winshubagro.cloud")

# token cunhado dentro do container (mesma SECRET_KEY que a API valida)
token = Path("/tmp/wins_token.txt").read_text().strip()

SECTIONS = ["visao", "whitespace", "arbitragem", "rankings", "matching",
            "marketplace", "demanda", "territorio", "mapa", "mercado"]
MAP_LAYERS = ["rebanho", "leite", "valor", "tendencia", "lotacao"]
OUT = Path("/root/wins_agro_v1/smoke_shots"); OUT.mkdir(exist_ok=True)

from playwright.sync_api import sync_playwright

console_errors, page_errors, csp_violations, bad_responses = [], [], [], []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        "--host-resolver-rules=MAP winshubagro.cloud 127.0.0.1, MAP www.winshubagro.cloud 127.0.0.1",
        "--no-sandbox",
    ])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_cookies([{
        "name": "access_token", "value": token,
        "domain": "winshubagro.cloud", "path": "/",
        "httpOnly": True, "secure": True, "sameSite": "Lax",
    }])
    page = ctx.new_page()

    page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text}")
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("response", lambda r: bad_responses.append(f"{r.status} {r.url}")
            if r.url.find("/api/") >= 0 and r.status >= 400 else None)
    # securitypolicyviolation via JS hook
    page.add_init_script("""
      document.addEventListener('securitypolicyviolation', e => {
        window.__csp = window.__csp || [];
        window.__csp.push(e.violatedDirective + ' :: ' + e.blockedURI);
      });
    """)

    print("Abrindo home...")
    page.goto("https://winshubagro.cloud/", wait_until="networkidle", timeout=30000)
    title = page.title()
    print(f"  título: {title!r}  url: {page.url}")
    if "login" in page.url:
        print("ERRO: caiu no login (cookie não aceito).")
        sys.exit(2)

    def D():
        return """(() => { const r = document.querySelector('[x-data]');
                   return r.__x ? r.__x.$data : r._x_dataStack[0]; })"""

    results = {}
    for sec in SECTIONS:
        # navega como a Mari (dispara go(), que carrega dados/mapa)
        page.evaluate(f"() => {{ const d = {D()}(); d.go('{sec}'); }}")
        page.wait_for_timeout(2200)

        if sec == "matching":
            # roda um matching real (perfil Nelore corte, TO)
            page.evaluate(f"""() => {{ const d = {D()}();
                d.match.finalidade='corte'; d.match.prioridade='geral'; d.match.uf='TO'; d.runMatching(); }}""")
            page.wait_for_timeout(3000)

        if sec == "mapa":
            page.wait_for_timeout(1500)
            for layer in MAP_LAYERS:
                page.evaluate(f"""() => {{ const d = {D()}();
                    d.mapLayer='{layer}'; d.loadMapa(); }}""")
                page.wait_for_timeout(1400)
            # volta p/ camada default p/ screenshot
            page.evaluate(f"() => {{ const d = {D()}(); d.mapLayer='rebanho'; d.loadMapa(); }}")
            page.wait_for_timeout(1800)

        info = page.evaluate(f"""() => {{
            const s = document.querySelector("[x-show=\\"section==='{sec}'\\"]");
            if (!s) return {{visible:false}};
            const vis = s.offsetParent !== null || getComputedStyle(s).display !== 'none';
            const rows = s.querySelectorAll('tr, .card, canvas, .leaflet-container').length;
            const txt = (s.innerText||'').replace(/\\s+/g,' ').trim().slice(0,80);
            return {{visible:vis, rows, txt}};
        }}""")
        if sec == "mapa":
            info["tiles"] = page.evaluate("() => document.querySelectorAll('.leaflet-tile-loaded').length")
            info["markers"] = page.evaluate("() => document.querySelectorAll('.leaflet-interactive, .leaflet-marker-icon').length")
        if sec == "matching":
            info["resultados"] = page.evaluate(f"() => {{ const d = {D()}(); return (d.matchResult||[]).length; }}")
        results[sec] = info
        page.screenshot(path=str(OUT / f"{sec}.png"), full_page=(sec in ("matching","demanda")))
        status = "OK" if info.get("visible") else "VAZIO/oculto"
        extra = ""
        if "tiles" in info: extra = f" tiles={info['tiles']} pts={info['markers']}"
        if "resultados" in info: extra = f" resultados={info['resultados']}"
        print(f"  [{status}] {sec:12s} rows/cards={info.get('rows','-')}{extra}  «{info.get('txt','')}»")

    # valida o PDF do parecer (a ferramenta de fechamento)
    print("Testando PDF do parecer...")
    pdf = page.evaluate("""async () => {
        const r = await fetch('/api/matching/pdf', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({finalidade:'corte', prioridade:'geral', uf:'TO'})});
        const buf = await r.arrayBuffer();
        const head = new TextDecoder().decode(new Uint8Array(buf).slice(0,5));
        return {status:r.status, bytes:buf.byteLength, ct:r.headers.get('content-type'), head};
    }""")
    print(f"  PDF: status={pdf['status']} bytes={pdf['bytes']} ct={pdf['ct']} magic={pdf['head']!r}")
    pdf_ok = pdf["status"] == 200 and pdf["head"] == "%PDF-"

    csp = page.evaluate("() => window.__csp || []")
    csp_violations.extend(csp)
    browser.close()

print("\n===== RESUMO =====")
print(f"Console errors/warnings: {len(console_errors)}")
for e in console_errors[:20]: print("  -", e)
print(f"Page (JS) errors: {len(page_errors)}")
for e in page_errors[:20]: print("  -", e)
print(f"CSP violations: {len(csp_violations)}")
for e in csp_violations[:20]: print("  -", e)
print(f"API responses >=400: {len(bad_responses)}")
for e in bad_responses[:20]: print("  -", e)
print(f"\nScreenshots em: {OUT}")
pdf_ok = locals().get("pdf_ok", False)
ok = pdf_ok and not (page_errors or csp_violations or bad_responses)
print("\nVEREDITO:", "✅ demo limpa (inclui matching+PDF)" if ok else "⚠️ revisar itens acima")
