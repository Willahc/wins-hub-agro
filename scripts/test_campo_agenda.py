#!/usr/bin/env python3
"""Valida a Agenda sanitária: registra lembrete atrasado, confere na agenda,
'Aplica' (fecha o lembrete + cria nova dose) e 'Dispensa' outro. Limpa no fim."""
import os, pathlib, datetime
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'
os.makedirs(OUT, exist_ok=True)
ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
amanha = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
futuro = (datetime.date.today() + datetime.timedelta(days=180)).isoformat()

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
        page.wait_for_timeout(700); page.screenshot(path=f'{OUT}/agenda-{label}.png'); print('ok ', label)

    def add_sanitario(produto, prox):
        """Abre 💉 no 1º animal e registra com proxima_dose=prox."""
        page.locator('.an .mini', has_text='💉').first.click()
        page.wait_for_timeout(500)
        page.fill('input[x-ref="prodInput"]', produto)
        page.fill('input[type="date"]', prox)
        page.get_by_text('Registrar manejo').click()
        page.wait_for_timeout(1800)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle')
    page.wait_for_timeout(1000)

    # fazenda DEMO + fêmea com raça (p/ raca_sigla na agenda)
    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO AGENDA')
    page.fill('input[placeholder="TO"]', 'TO'); page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click(); page.wait_for_timeout(1800)
    page.get_by_text('Curral', exact=False).last.click(); page.wait_for_timeout(600)
    page.fill('input[placeholder="247"]', '777'); page.fill('input[placeholder="opcional"]', 'VACA AGENDA')
    page.evaluate("""() => { const sel=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.text.startsWith('NEL')));
        const opt=[...sel.options].find(o=>o.text.startsWith('NEL')); sel.value=opt.value; sel.dispatchEvent(new Event('change',{bubbles:true})); }""")
    page.get_by_text('Salvar no curral').click(); page.wait_for_timeout(2200)

    # Rebanho -> 2 lembretes: 1 atrasado (ontem), 1 futuro-próximo (amanhã)
    page.get_by_text('Rebanho', exact=False).last.click(); page.wait_for_timeout(1600)
    add_sanitario('Aftosa', ontem)
    add_sanitario('Vermífugo Ivomec', amanha)

    # Agenda
    page.get_by_text('Agenda', exact=False).last.click(); page.wait_for_timeout(1500)
    shot('1-lista')
    atrasados = int(page.locator('.stat .v').nth(0).inner_text())
    assert atrasados >= 1, f'esperava >=1 atrasado, veio {atrasados}'
    assert page.get_by_text('atrasado', exact=False).first.is_visible(), 'rótulo atrasado não apareceu'

    # Aplicar no item Aftosa (atrasado) -> abre sheet pré-preenchido
    aftosa_card = page.locator('.rec', has_text='Aftosa')
    aftosa_card.get_by_text('✓ Aplicar').click()
    page.wait_for_timeout(500)
    prod_val = page.locator('input[x-ref="prodInput"]').input_value()
    assert prod_val == 'Aftosa', f'sheet não pré-preencheu produto (veio {prod_val!r})'
    shot('2-aplicar-prefill')
    page.fill('input[type="date"]', futuro)  # próxima dose daqui 180d (fora da janela de 30d)
    page.get_by_text('Registrar manejo').click()
    page.wait_for_timeout(2500)  # salva + carregaAgenda

    # Aftosa deve ter sumido da agenda (lembrete de origem concluído; novo está fora dos 30d)
    assert page.locator('.rec', has_text='Aftosa').count() == 0, 'lembrete Aftosa deveria ter saído da agenda'
    shot('3-pos-aplicar')

    # Dispensar o Vermífugo
    verm_card = page.locator('.rec', has_text='Vermífugo')
    verm_card.get_by_text('dispensar').click()
    page.wait_for_timeout(1500)
    assert page.locator('.rec', has_text='Vermífugo').count() == 0, 'Vermífugo deveria sumir após dispensar'
    shot('4-pos-dispensar')

    print('--- console errors:', len(errs))
    for e in errs[:20]: print('  ', e)
    browser.close()
    print('AGENDA VALIDACAO OK')
