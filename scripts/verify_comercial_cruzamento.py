#!/usr/bin/env python3
"""Verifica no navegador real a nova página Comercial + complementos do Cruzamento.
Captura erros de console/page, exercita matching+ficha(radar), bezerro, ficha animal, sugestões."""
import pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
BASE = 'https://winshubagro.cloud'

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--no-sandbox'])
        ctx = b.new_context(viewport={'width':1400,'height':1000}, ignore_https_errors=True)
        ctx.add_cookies([{'name':'access_token','value':TOKEN,'domain':'winshubagro.cloud','path':'/','httpOnly':True,'secure':True,'sameSite':'Lax'}])
        pg = ctx.new_page(); errs=[]
        pg.on('pageerror', lambda e: errs.append('PAGEERR: '+str(e)))
        pg.on('console', lambda m: errs.append('CONS: '+m.text) if m.type=='error' else None)

        # ---------- COMERCIAL ----------
        pg.goto(f'{BASE}/comercial', wait_until='networkidle', timeout=40000)
        # sidebar tem o item Comercial ativo?
        active = pg.eval_on_selector('.nav-item.active', 'el=>el.textContent.trim()')
        print('nav ativo:', active)
        pg.click("button:has-text('Rodar recomendação')", timeout=15000)
        pg.wait_for_selector("table.data tbody tr", timeout=20000)
        rows = pg.query_selector_all("table.data tbody tr")
        topname = pg.inner_text(".top-match .tm-name") if pg.query_selector('.top-match') else '(sem top-match)'
        print(f'COMERCIAL matching -> linhas:{len(rows)} | top:{topname}')
        pg.screenshot(path='/tmp/shots/comercial.png')
        # abre ficha do touro (1ª linha) -> radar
        pg.click("table.data tbody tr >> nth=0")
        pg.wait_for_selector("#radarTouro", timeout=10000)
        pg.wait_for_timeout(1200)
        has_canvas = pg.eval_on_selector('#radarTouro', 'el=>el.width>0')
        print('COMERCIAL ficha touro -> radar render:', has_canvas)
        pg.screenshot(path='/tmp/shots/comercial_ficha.png')
        pg.click(".mdl-x")
        pg.wait_for_timeout(500)

        # ---------- CRUZAMENTO ----------
        pg.goto(f'{BASE}/cruzamento', wait_until='networkidle', timeout=40000)
        pg.wait_for_selector("table.data tbody tr", timeout=20000)
        # abre ficha clicando no nome do 1º animal
        pg.click(".link-nome >> nth=0")
        pg.wait_for_selector(".mdl", timeout=10000)
        pg.wait_for_timeout(1000)
        print('CRUZAMENTO ficha animal -> modal aberto:', bool(pg.query_selector('.mdl')))
        pg.screenshot(path='/tmp/shots/cruz_ficha.png')
        pg.click(".mdl-x"); pg.wait_for_timeout(400)
        # filtra só touros, marca o 1º como pai
        pg.select_option("select.select >> nth=1", "M")
        pg.wait_for_timeout(1500)
        pg.wait_for_selector("button.sel-btn:has-text('pai')", timeout=10000)
        pg.click("button.sel-btn:has-text('pai') >> nth=0")
        # filtra só matrizes, marca a 1ª como mãe (seleção do touro persiste no estado)
        pg.select_option("select.select >> nth=1", "F")
        pg.wait_for_timeout(1500)
        pg.wait_for_selector("button.sel-btn:has-text('mãe')", timeout=10000)
        pg.click("button.sel-btn:has-text('mãe') >> nth=0")
        # sugestões p/ a mãe
        pg.click("button:has-text('Sugerir melhores touros')")
        pg.wait_for_selector(".sug-row", timeout=15000)
        sugs = pg.query_selector_all(".sug-row")
        print('CRUZAMENTO sugestões -> recs:', len(sugs))
        pg.screenshot(path='/tmp/shots/cruz_sugestoes.png')
        # ver bezerro
        if pg.query_selector("button:has-text('Ver bezerro previsto')"):
            pg.click("button:has-text('Ver bezerro previsto')")
            pg.wait_for_selector("#filhoteChart", timeout=10000)
            pg.wait_for_timeout(1000)
            print('CRUZAMENTO bezerro -> chart render:', pg.eval_on_selector('#filhoteChart','el=>el.width>0'))
            pg.screenshot(path='/tmp/shots/cruz_bezerro.png')

        print('ERROS DE CONSOLE/PAGE:', len(errs))
        for e in errs[:12]: print('  ', e[:160])
        b.close()

run()
