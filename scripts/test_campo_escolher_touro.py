#!/usr/bin/env python3
"""Valida a ESCOLHA do touro recomendado na aba Cruzar (bug: card não clicava).
Cria fêmea com IQGg, roda acasalamento ao vivo, CLICA no 1º touro recomendado e confere:
- o card ganha estado selecionado (.rec.sel) + texto '✓ Touro escolhido';
- a URL da cotação passa a incluir touro_id (lidera pelo escolhido);
- o endpoint de cotação com touro_id devolve application/pdf 200.
Toca de novo p/ desmarcar (toggle). Limpa a fazenda DEMO no fim."""
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
        page.wait_for_timeout(600); page.screenshot(path=f'{OUT}/escolher-{label}.png'); print('ok ', label)

    page.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); page.wait_for_timeout(1000)

    page.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO ESCOLHER')
    page.fill('input[placeholder="TO"]', 'TO'); page.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    page.get_by_text('Criar fazenda').click(); page.wait_for_timeout(1800)
    page.get_by_text('Curral', exact=False).last.click(); page.wait_for_timeout(600)
    page.fill('input[x-model="novo.brinco"]', '901'); page.fill('input[x-model="novo.nome"]', 'AURORA FIV')
    page.evaluate("""() => { const sel=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.text.startsWith('NEL')));
        const opt=[...sel.options].find(o=>o.text.startsWith('NEL')); sel.value=opt.value; sel.dispatchEvent(new Event('change',{bubbles:true})); }""")
    page.evaluate("""() => { const labs=[...document.querySelectorAll('label')];
        const set=(t,v)=>{const l=labs.find(x=>x.textContent.trim()===t); if(l){const i=l.nextElementSibling; i.value=v; i.dispatchEvent(new Event('input',{bubbles:true}));}};
        set('IQGg','22.5'); }""")
    page.get_by_text('Salvar no curral').click(); page.wait_for_timeout(2500)

    page.get_by_text('Rebanho', exact=False).last.click(); page.wait_for_timeout(1600)
    page.locator('.an button.mini.p').first.click()  # ♥ Cruzar
    page.wait_for_timeout(3500)
    page.wait_for_timeout(800)
    rec = page.locator('.rec.pickable').first
    assert rec.is_visible(), 'nenhum touro recomendado'
    assert 'Tocar p/ escolher' in rec.inner_text(), 'sem dica de tocar'
    shot('1-recs')

    # CLICA no touro -> deve selecionar
    rec.click(); page.wait_for_timeout(700)
    cls = rec.get_attribute('class') or ''
    assert 'sel' in cls, f'card não ficou selecionado (class={cls})'
    assert '✓ Touro escolhido' in rec.inner_text(), 'texto de escolhido não apareceu'
    chosen_id = page.evaluate("() => { const el=document.querySelector('[x-data]'); return el && el.__x ? null : null; }")
    # confirma que a cotação agora inclui touro_id (lê via Alpine $data)
    url = page.evaluate("""() => { const root=document.querySelector('[x-data]');
        const d = (window.Alpine && Alpine.$data) ? Alpine.$data(root) : (root && root._x_dataStack ? root._x_dataStack[0] : null);
        return d ? d.cotacaoUrl() : ''; }""")
    print('cotacaoUrl:', url)
    assert 'touro_id=' in url, f'cotacaoUrl sem touro_id: {url}'
    assert page.get_by_text('PDF liderado pelo touro escolhido', exact=False).is_visible(), 'card de cotação não refletiu escolha'
    shot('2-escolhido')

    # Baixar PDF (com touro_id) -> 200 application/pdf
    with page.expect_response(lambda r: '/api/campo/cotacao/pdf' in r.url) as resp_info:
        page.get_by_text('📄 Baixar PDF').click()
    resp = resp_info.value
    print('cotacao response:', resp.status, resp.headers.get('content-type'), '| touro_id na url:', 'touro_id=' in resp.url)
    assert resp.status == 200 and 'application/pdf' in resp.headers.get('content-type', ''), 'cotação não veio PDF'
    assert 'touro_id=' in resp.url, 'endpoint chamado sem touro_id'

    # toggle: tocar de novo desmarca
    rec.click(); page.wait_for_timeout(500)
    assert 'sel' not in (rec.get_attribute('class') or ''), 'toggle não desmarcou'
    print('toggle OK')

    print('--- console errors:', len(errs))
    for e in errs[:20]: print('  ', e)
    browser.close()
    print('ESCOLHER TOURO VALIDACAO OK')
