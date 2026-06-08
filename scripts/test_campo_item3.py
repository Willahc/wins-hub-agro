#!/usr/bin/env python3
"""Item 3: SISBOV no Curral + Movimentação/GTA na aba Fazenda. Cadastra fêmea com SISBOV,
registra uma GTA e confere que aparece na lista. Verificação no banco + limpeza via SQL externa."""
import os, pathlib
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'; os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 412, 'height': 1200}, device_scale_factor=2, ignore_https_errors=True)
    ctx.add_cookies([{'name': 'access_token', 'value': TOKEN, 'domain': 'winshubagro.cloud',
                      'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append('PAGEERR: ' + str(e)))

    def shot(label):
        page.wait_for_timeout(600); page.screenshot(path=f'{OUT}/item3-{label}.png', full_page=True); print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); page.wait_for_timeout(1000)

    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO ITEM3')
    page.fill('input[placeholder="TO"]', 'TO'); page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click(); page.wait_for_timeout(1800)

    # Curral: fêmea com SISBOV
    page.get_by_text('Curral', exact=False).last.click(); page.wait_for_timeout(600)
    page.fill('input[placeholder="247"]', '555')
    page.evaluate("""() => { const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith('Nome'));
        const i=l.nextElementSibling; i.value='VACA SISBOV'; i.dispatchEvent(new Event('input',{bubbles:true})); }""")
    page.fill('input[maxlength="15"]', '123456789012345')  # campo SISBOV
    page.get_by_text('Salvar no curral').click(); page.wait_for_timeout(2200)

    # Fazenda: registra GTA
    page.get_by_text('Fazenda', exact=False).last.click(); page.wait_for_timeout(900)
    page.locator('.seg.wrap3 button', has_text='saida').first.click()
    # preenche o card de movimentação mirando por label (único, sem ambiguidade)
    page.evaluate("""() => {
        const set=(t,v)=>{const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith(t)); if(l){const i=l.nextElementSibling; i.value=v; i.dispatchEvent(new Event('input',{bubbles:true}));}};
        set('Nº da GTA','GTA-78901');
        set('Origem','Fazenda Sede');
        set('Destino','Frigorífico X');
        set('Finalidade','engorda');
        set('Quantidade','40');
    }""")
    page.get_by_text('Registrar movimentação').click()
    page.wait_for_timeout(2200)

    assert page.get_by_text('Últimas movimentações', exact=False).is_visible(), 'lista de movimentações não apareceu'
    assert page.get_by_text('GTA-78901', exact=False).is_visible() or page.get_by_text('GTA 78901', exact=False).is_visible(), 'GTA não listada'
    shot('1-fazenda-gta')

    print('--- console errors:', len(errs))
    for e in errs[:20]: print('  ', e)
    browser.close()
    print('ITEM3 VALIDACAO OK')
