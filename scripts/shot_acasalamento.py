#!/usr/bin/env python3
"""Screenshot do fluxo de acasalamento dirigido, capturando erros JS."""
import pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'
pathlib.Path(OUT).mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    page.goto('https://winshubagro.cloud/', wait_until='networkidle')
    page.wait_for_timeout(1200)
    if 'login' in page.url:
        print('ERRO: login'); raise SystemExit(1)

    page.evaluate("""() => { const el=[...document.querySelectorAll('.nav-item')].find(n=>n.textContent.includes('Matrizes')); if(el) el.click(); }""")
    page.wait_for_timeout(1800)
    # abre 1a matriz
    page.evaluate("""() => { const tr=document.querySelector("section[x-show=\\"section==='matrizes'\\"] tbody tr"); if(tr) tr.click(); }""")
    page.wait_for_timeout(1500)
    # clica botão acasalamento
    page.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Acasalamento dirigido')); if(b) b.click(); }""")
    page.wait_for_timeout(2200)
    page.screenshot(path=f'{OUT}/acasal-geral.png')
    rows = page.evaluate("() => { const t=[...document.querySelectorAll('.modal')].find(m=>m.textContent.includes('Acasalamento dirigido')); return t? t.querySelectorAll('tbody tr').length : -1; }")
    print('recomendacoes (geral):', rows)

    # troca prioridade p/ carcaça
    page.evaluate("""() => {
        const t=[...document.querySelectorAll('.modal')].find(m=>m.textContent.includes('Acasalamento dirigido'));
        const sel=t && t.querySelector('select');
        if(sel){ sel.value='carcaca'; sel.dispatchEvent(new Event('change')); }
    }""")
    page.wait_for_timeout(2000)
    page.screenshot(path=f'{OUT}/acasal-carcaca.png')
    print('ok screenshots')
    print('CONSOLE ERRORS:', errs if errs else 'nenhum')
    browser.close()
