#!/usr/bin/env python3
"""Screenshots das telas via cookie de sessão. uso: python3 scripts/shot.py <sufixo>"""
import sys, os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
SUF = sys.argv[1] if len(sys.argv) > 1 else 'shot'
OUT = '/tmp/shots'
os.makedirs(OUT, exist_ok=True)

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

    def shot(label):
        page.wait_for_timeout(1200)
        page.screenshot(path=f'{OUT}/{SUF}-{label}.png')
        print('ok ', label)

    def click_nav(txt):
        page.evaluate("""(t) => {
            const el = [...document.querySelectorAll('.nav-item')].find(n => n.textContent.includes(t));
            if (el) el.click();
        }""", txt)
        page.wait_for_timeout(1500)

    page.goto('https://winshubagro.cloud/', wait_until='networkidle')
    page.wait_for_timeout(1500)
    shot('overview')
    click_nav('White-Space'); shot('whitespace')
    click_nav('Matching'); shot('matching-empty')
    page.evaluate("""() => {
        const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Rodar Matching'));
        if (b) b.click();
    }""")
    page.wait_for_timeout(3500); shot('matching-run')
    click_nav('Mapa'); page.wait_for_timeout(2500); shot('mapa')
    click_nav('Território'); shot('territorio')
    click_nav('Mercado'); page.wait_for_timeout(2500); shot('mercado')

    if errs:
        print('--- console errors ---')
        for e in errs[:20]: print(e)
    browser.close()
