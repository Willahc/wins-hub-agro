#!/usr/bin/env python3
"""Verifica a aba 🩺 Técnicos no Hub: navega, confere KPIs + tabela + filtro zootecnista,
0 erro de console, screenshot."""
import pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width':1400,'height':1000}, ignore_https_errors=True)
    ctx.add_cookies([{'name':'access_token','value':TOKEN,'domain':'winshubagro.cloud','path':'/','httpOnly':True,'secure':True,'sameSite':'Lax'}])
    pg = ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append('PAGEERR: '+str(e)))
    pg.on('console', lambda m: errs.append('CONS: '+m.text) if m.type=='error' else None)

    pg.goto('https://winshubagro.cloud/', wait_until='networkidle', timeout=40000)
    # clica no nav "Técnicos"
    pg.click("text=Técnicos", timeout=15000)
    pg.wait_for_timeout(2500)
    # espera a tabela ou KPIs
    pg.wait_for_selector("text=técnicos (fila coerente)", timeout=15000)

    total = pg.inner_text("css=.kpi:has-text('fila coerente') .value")
    vets  = pg.inner_text("css=.kpi:has-text('veterinários') .value")
    zoo   = pg.inner_text("css=.kpi:has-text('zootecnistas') .value")
    rows  = pg.query_selector_all("section:has-text('canal de genética') tbody tr")
    print(f"KPIs -> total:{total} vets:{vets} zootec:{zoo} | linhas na tabela:{len(rows)}")
    pg.screenshot(path='/tmp/shots/tecnicos.png', full_page=False)

    # aplica filtro zootecnista e confere que recarrega
    pg.select_option("section:has-text('canal de genética') select >> nth=1", "zootecnista")
    pg.wait_for_timeout(2500)
    rows2 = pg.query_selector_all("section:has-text('canal de genética') tbody tr")
    first = pg.inner_text("section:has-text('canal de genética') tbody tr >> nth=0") if rows2 else "(vazio)"
    print(f"Filtro zootecnista -> linhas:{len(rows2)} | 1ª: {first[:80]}")
    pg.screenshot(path='/tmp/shots/tecnicos_zootec.png', full_page=False)

    print("ERROS DE CONSOLE:", len(errs))
    for e in errs[:8]: print('  ', e[:140])
    b.close()
