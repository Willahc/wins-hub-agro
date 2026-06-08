#!/usr/bin/env python3
"""Screenshot da seção Matrizes (lista + modal de progênie), capturando erros JS."""
import pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'
pathlib.Path(OUT).mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, ignore_https_errors=True)
    ctx.add_cookies([{
        'name': 'access_token', 'value': TOKEN,
        'domain': 'winshubagro.cloud', 'path': '/',
        'httpOnly': True, 'secure': True, 'sameSite': 'Lax',
    }])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    page.goto('https://winshubagro.cloud/', wait_until='networkidle')
    page.wait_for_timeout(1200)
    if 'login' in page.url:
        print('ERRO: caiu no login (token inválido).'); raise SystemExit(1)

    # abrir Matrizes via nav
    page.evaluate("""() => {
        const el = [...document.querySelectorAll('.nav-item')].find(n => n.textContent.includes('Matrizes'));
        if (el) el.click();
    }""")
    page.wait_for_timeout(2000)
    page.screenshot(path=f'{OUT}/matrizes-lista.png')
    print('ok lista')

    # contar linhas da tabela
    rows = page.evaluate("() => document.querySelectorAll(\"section[x-show=\\\"section==='matrizes'\\\"] tbody tr\").length")
    print('linhas na tabela:', rows)

    # clicar 1a linha -> modal progênie
    page.evaluate("""() => {
        const tr = document.querySelector("section[x-show=\\"section==='matrizes'\\"] tbody tr");
        if (tr) tr.click();
    }""")
    page.wait_for_timeout(1800)
    page.screenshot(path=f'{OUT}/matrizes-modal.png')
    print('ok modal')

    print('CONSOLE ERRORS:', errs if errs else 'nenhum')
    browser.close()
