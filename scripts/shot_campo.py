#!/usr/bin/env python3
"""Demo + screenshots da UI /campo via cookie. Cria fazenda DEMO, cadastra fêmea,
roda acasalamento ao vivo, captura cada tela. Limpeza dos dados é feita depois (SQL)."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 412, 'height': 880},  # tablet/celular retrato
                              device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    def shot(label):
        page.wait_for_timeout(900)
        page.screenshot(path=f'{OUT}/campo-{label}.png')
        print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle')
    page.wait_for_timeout(1200)
    shot('1-fazenda')

    # cria fazenda DEMO
    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO CAMPO')
    page.fill('input[placeholder="TO"]', 'TO')
    page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click()
    page.wait_for_timeout(1800)
    # cria lote
    page.fill('input[placeholder="Novo lote (ex.: Bezerras 2026)"]', 'Matrizes Elite 2026')
    page.get_by_text('+ Lote').click()
    page.wait_for_timeout(1500)
    shot('2-fazenda-criada')

    # aba Curral -> cadastra fêmea
    page.get_by_text('Curral', exact=False).last.click()
    page.wait_for_timeout(700)
    page.fill('input[placeholder="247"]', '247')
    page.fill('input[placeholder="opcional"]', 'BONITA DA SERRA')
    # raça: seleciona uma opção que contenha NEL (Nelore)
    page.evaluate("""() => {
        const sel = document.querySelector('select[x-model\\\\.number="novo.raca_id"]') ||
                    [...document.querySelectorAll('select')].find(s => [...s.options].some(o=>o.text.includes('NEL')));
        const opt = [...sel.options].find(o => o.text.startsWith('NEL'));
        sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true}));
    }""")
    page.fill('input[placeholder="0"] >> nth=0', '430')
    page.fill('input[placeholder="0"] >> nth=1', '6')
    page.wait_for_timeout(300)
    # IQGg próprio
    page.evaluate("""() => {
        const labs = [...document.querySelectorAll('label')];
        const setByLabel = (txt,val) => { const l = labs.find(x=>x.textContent.trim()===txt); if(l){const i=l.nextElementSibling; i.value=val; i.dispatchEvent(new Event('input',{bubbles:true}));}};
        setByLabel('IQGg','21.3');
    }""")
    shot('3-curral-form')
    page.get_by_text('Salvar no curral').click()
    page.wait_for_timeout(2200)  # enfileira + sincroniza

    # aba Rebanho
    page.get_by_text('Rebanho', exact=False).last.click()
    page.wait_for_timeout(1600)
    shot('4-rebanho')

    # acasalamento ao vivo
    try:
        page.locator('.an button.mini.p').first.click()  # botão ♥ Cruzar da LINHA do animal
        page.wait_for_timeout(3500)
        shot('5-acasalamento')
    except Exception as e:
        print('cruzar falhou:', e)

    print('--- console errors:', len(errs))
    for e in errs[:20]:
        print('  ', e)
    browser.close()
