#!/usr/bin/env python3
"""Valida a Cotação de sêmen na aba Cruzar: cria fêmea com IQGg, roda acasalamento
ao vivo, gera a cotação PDF e confere que o endpoint devolve application/pdf. Limpa no fim."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'; os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 412, 'height': 880}, device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    def shot(label):
        page.wait_for_timeout(700); page.screenshot(path=f'{OUT}/cotacao-{label}.png'); print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); page.wait_for_timeout(1000)

    # fazenda DEMO + fêmea NEL com IQGg (vira espelho no catálogo -> acasalamento ao vivo)
    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO COTACAO')
    page.fill('input[placeholder="TO"]', 'TO'); page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click(); page.wait_for_timeout(1800)
    page.get_by_text('Curral', exact=False).last.click(); page.wait_for_timeout(600)
    page.fill('input[placeholder="247"]', '900'); page.fill('input[placeholder="opcional"]', 'ESTRELA FIV')
    page.evaluate("""() => { const sel=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.text.startsWith('NEL')));
        const opt=[...sel.options].find(o=>o.text.startsWith('NEL')); sel.value=opt.value; sel.dispatchEvent(new Event('change',{bubbles:true})); }""")
    page.evaluate("""() => { const labs=[...document.querySelectorAll('label')];
        const set=(t,v)=>{const l=labs.find(x=>x.textContent.trim()===t); if(l){const i=l.nextElementSibling; i.value=v; i.dispatchEvent(new Event('input',{bubbles:true}));}};
        set('IQGg','22.5'); }""")
    page.get_by_text('Salvar no curral').click(); page.wait_for_timeout(2500)

    # Rebanho -> ♥ Cruzar
    page.get_by_text('Rebanho', exact=False).last.click(); page.wait_for_timeout(1600)
    page.locator('.an button.mini.p').first.click()  # ♥ Cruzar
    page.wait_for_timeout(3500)
    assert page.get_by_text('Touros recomendados', exact=False).is_visible(), 'recs não carregaram'
    assert page.get_by_text('Cotação de sêmen', exact=False).is_visible(), 'card de cotação não apareceu'
    shot('1-cruzar-com-cotacao')

    # Baixar PDF -> intercepta a resposta do endpoint
    with page.expect_response(lambda r: '/api/campo/cotacao/pdf' in r.url) as resp_info:
        page.get_by_text('📄 Baixar PDF').click()
    resp = resp_info.value
    print('cotacao response:', resp.status, resp.headers.get('content-type'))
    assert resp.status == 200, f'status {resp.status}'
    assert 'application/pdf' in resp.headers.get('content-type', ''), 'não veio PDF'
    page.wait_for_timeout(800)
    shot('2-pos-baixar')

    print('--- console errors:', len(errs))
    for e in errs[:20]: print('  ', e)
    browser.close()
    print('COTACAO VALIDACAO OK')
