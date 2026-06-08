#!/usr/bin/env python3
"""Valida a Auditoria genética na aba Fazenda contra a fazenda já semeada (ZZ DEMO AUDIT).
Seleciona a fazenda, roda a auditoria, confere stats/ranking e o atalho Cruzar."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'; os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 412, 'height': 1100}, device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    def shot(label):
        page.wait_for_timeout(600); page.screenshot(path=f'{OUT}/audit-{label}.png', full_page=True); print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); page.wait_for_timeout(1200)

    # seleciona a fazenda DEMO AUDIT no dropdown
    page.evaluate("""() => {
        const sel = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.text.includes('ZZ DEMO AUDIT')));
        const opt = [...sel.options].find(o => o.text.includes('ZZ DEMO AUDIT'));
        sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true}));
    }""")
    page.wait_for_timeout(1800)

    # roda a auditoria
    page.get_by_text('Rodar auditoria').click()
    page.wait_for_timeout(1600)

    # asserts
    assert page.get_by_text('IQGg médio', exact=False).is_visible(), 'stats da auditoria não apareceram'
    assert page.get_by_text('Ranking genético', exact=False).is_visible(), 'ranking não apareceu'
    assert page.get_by_text('corrigir', exact=False).count() >= 1, 'flag de prioridade corretiva ausente'
    assert page.get_by_text('sem genotipagem', exact=False).is_visible(), 'aviso de genotipagem ausente'
    txt = page.inner_text('body')
    assert 'Vantagem do rebanho' in txt, 'benchmark de raça ausente'
    shot('1-auditoria')

    # atalho Cruzar a partir do ranking
    page.locator('.an button.mini.p').first.click()
    page.wait_for_timeout(3500)
    assert page.get_by_text('Touros recomendados', exact=False).is_visible(), 'Cruzar do audit não carregou recs'
    shot('2-cruzar-do-audit')

    print('--- console errors:', len(errs))
    for e in errs[:20]: print('  ', e)
    browser.close()
    print('AUDITORIA VALIDACAO OK')
