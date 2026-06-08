#!/usr/bin/env python3
"""Validação das telas próprias de pesagem/sanitário (substituem prompt()).
Cria fazenda DEMO, cadastra fêmea, abre cada bottom-sheet, salva, captura tela.
Dados DEMO limpos depois via SQL (scripts/cleanup_demo_sheets.sql)."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 412, 'height': 880},
                              device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    def shot(label):
        page.wait_for_timeout(700)
        page.screenshot(path=f'{OUT}/sheet-{label}.png')
        print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle')
    page.wait_for_timeout(1000)

    # fazenda DEMO + lote
    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO SHEETS')
    page.fill('input[placeholder="TO"]', 'TO')
    page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click()
    page.wait_for_timeout(1800)

    # Curral -> cadastra fêmea
    page.get_by_text('Curral', exact=False).last.click()
    page.wait_for_timeout(600)
    page.fill('input[placeholder="247"]', '301')
    page.fill('input[placeholder="opcional"]', 'TESTE PESAGEM')
    page.get_by_text('Salvar no curral').click()
    page.wait_for_timeout(2200)

    # Rebanho
    page.get_by_text('Rebanho', exact=False).last.click()
    page.wait_for_timeout(1600)

    # --- TELA DE PESAGEM ---
    page.get_by_text('⚖ Pesar').first.click()
    page.wait_for_timeout(500)
    assert page.locator('.sheet .sh-t', has_text='Pesagem').is_visible(), 'sheet de pesagem não abriu'
    page.fill('input[x-ref="pesoInput"]', '438')
    page.locator('.escore button', has_text='6').click()  # escore 6
    shot('1-pesagem-aberta')
    page.get_by_text('Registrar pesagem').click()
    page.wait_for_timeout(2000)
    assert not page.locator('.sheet .sh-t', has_text='Pesagem').is_visible(), 'sheet não fechou após salvar'
    shot('2-pesagem-salva')

    # --- TELA DE SANITÁRIO ---
    page.locator('.an .mini', has_text='💉').first.click()
    page.wait_for_timeout(500)
    assert page.locator('.sheet .sh-t', has_text='sanitário').is_visible(), 'sheet sanitário não abriu'
    page.locator('.seg.wrap3 button', has_text='vacina').click()
    page.fill('input[x-ref="prodInput"]', 'Aftosa')
    page.fill('input[placeholder="ex.: 5 mL"]', '5 mL')
    shot('3-sanitario-aberto')
    page.get_by_text('Registrar manejo').click()
    page.wait_for_timeout(2000)
    shot('4-sanitario-salvo')

    print('--- console errors:', len(errs))
    for e in errs[:20]:
        print('  ', e)
    browser.close()
    print('VALIDACAO OK')
