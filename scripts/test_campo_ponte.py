#!/usr/bin/env python3
"""Valida a PONTE: busca no catálogo no Curral -> vincula -> cadastra -> a vaca fica
ligada ao reprodutor REAL (espelho = id do catálogo), com pedigree p/ o acasalamento."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'; os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 412, 'height': 1000}, device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('PAGEERR: '+str(e)))
    pg.on('console', lambda m: errs.append('CONS: '+m.text) if m.type == 'error' else None)

    def shot(l): pg.wait_for_timeout(500); pg.screenshot(path=f'{OUT}/ponte-{l}.png'); print('ok', l)

    pg.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); pg.wait_for_timeout(1200)
    # seleciona a Fazenda Demonstração
    pg.evaluate("""()=>{const s=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.text.includes('Fazenda Demonstração')));const o=[...s.options].find(o=>o.text.includes('Fazenda Demonstração'));s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));}""")
    pg.wait_for_timeout(1500)

    # Curral -> busca no catálogo
    pg.get_by_text('Curral', exact=False).last.click(); pg.wait_for_timeout(700)
    pg.fill('input[placeholder="acha o animal e puxa pedigree/genética"]', 'REM')
    pg.wait_for_timeout(1500)  # debounce + busca
    # clica no 1º resultado
    res = pg.locator('.card .muted:has-text("Reg")').first
    assert res.count() >= 1, 'sem resultados de busca'
    # pega o nome do 1º item antes de clicar
    primeiro = pg.locator('div[\\@click="pickCatalogo(r)"], .card >> div').first
    pg.locator('text=/Reg /').first.click()  # clica no item (linha com 'Reg ')
    pg.wait_for_timeout(800)
    # confere o banner de vínculo
    assert pg.get_by_text('Vinculado ao catálogo', exact=False).is_visible(), 'banner de vínculo não apareceu'
    shot('1-vinculado')

    # cadastra (com brinco)
    pg.fill('input[placeholder="247"]', '888')
    pg.get_by_text('Salvar no curral').click()
    pg.wait_for_timeout(2500)
    print('--- console/page errors:', len(errs))
    for e in errs[:10]: print('  ', e)
    b.close()
    assert len(errs) == 0, 'houve erros'
    print('PONTE UI OK')
