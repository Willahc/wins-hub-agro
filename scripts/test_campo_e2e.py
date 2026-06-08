#!/usr/bin/env python3
"""Regressão end-to-end: exercita TODAS as features do WiNS Campo numa fazenda só,
do cadastro à cotação/briefing/auditoria/descarte, conferindo 0 erros de console.
Limpeza via SQL externa (keyed em 'ZZ DEMO E2E')."""
import os, pathlib, datetime
from playwright.sync_api import sync_playwright

TOKEN = pathlib.Path('/tmp/wtok').read_text().strip()
OUT = '/tmp/shots'; os.makedirs(OUT, exist_ok=True)
ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width':412,'height':1200}, ignore_https_errors=True, service_workers='allow')
    ctx.add_cookies([{'name':'access_token','value':TOKEN,'domain':'winshubagro.cloud','path':'/','httpOnly':True,'secure':True,'sameSite':'Lax'}])
    pg = ctx.new_page(); errs=[]; pdfs=[]
    pg.on('pageerror', lambda e: errs.append('PAGEERR: '+str(e)))
    pg.on('console', lambda m: errs.append('CONS: '+m.text) if m.type=='error' else None)
    pg.on('response', lambda r: pdfs.append((r.url.split('?')[0], r.status)) if '/pdf' in r.url else None)
    def step(n): print('•', n)

    pg.goto('https://winshubagro.cloud/campo', wait_until='networkidle'); pg.wait_for_timeout(1000)

    # 1) Fazenda + lote
    pg.fill('input[placeholder="Razão social / nome da fazenda"]', 'ZZ DEMO E2E')
    pg.fill('input[placeholder="TO"]', 'TO'); pg.fill('input[placeholder="Porto Nacional"]', 'Porto Nacional')
    pg.get_by_text('Criar fazenda').click(); pg.wait_for_timeout(1700)
    pg.fill('input[placeholder="Novo lote (ex.: Bezerras 2026)"]', 'Matrizes E2E'); pg.get_by_text('+ Lote').click(); pg.wait_for_timeout(1200)
    step('fazenda + lote')

    # 2) Curral: fêmea NEL + IQGg + SISBOV
    pg.get_by_text('Curral', exact=False).last.click(); pg.wait_for_timeout(600)
    pg.fill('input[placeholder="247"]', '111')
    pg.evaluate("""()=>{const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith('Nome'));l.nextElementSibling.value='ESTRELA E2E';l.nextElementSibling.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.fill('input[maxlength="15"]', '987654321098765')
    pg.evaluate("""()=>{const s=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.text.startsWith('NEL')));const o=[...s.options].find(o=>o.text.startsWith('NEL'));s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));}""")
    pg.evaluate("""()=>{const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim()==='IQGg');l.nextElementSibling.value='23.0';l.nextElementSibling.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.get_by_text('Salvar no curral').click(); pg.wait_for_timeout(2400)
    step('curral (SISBOV + IQGg)')

    # 3) Rebanho: pesagem (sheet) + sanitário com proxima_dose (sheet)
    pg.get_by_text('Rebanho', exact=False).last.click(); pg.wait_for_timeout(1500)
    pg.get_by_text('⚖ Pesar').first.click(); pg.wait_for_timeout(400)
    pg.fill('input[x-ref="pesoInput"]', '442'); pg.locator('.escore button', has_text='6').click()
    pg.get_by_text('Registrar pesagem').click(); pg.wait_for_timeout(1600)
    pg.locator('.an .mini', has_text='💉').first.click(); pg.wait_for_timeout(400)
    pg.fill('input[x-ref="prodInput"]', 'Aftosa')
    pg.evaluate("""(d)=>{const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith('Próxima dose'));l.nextElementSibling.value=d;l.nextElementSibling.dispatchEvent(new Event('input',{bubbles:true}));}""", ontem)
    pg.get_by_text('Registrar manejo').click(); pg.wait_for_timeout(1600)
    step('pesagem + sanitário')

    # 4) Agenda: lembrete atrasado aparece
    pg.get_by_text('Agenda', exact=False).last.click(); pg.wait_for_timeout(1400)
    assert pg.get_by_text('atrasado', exact=False).first.is_visible(), 'agenda sem lembrete'
    step('agenda (lembrete atrasado)')

    # 5) Cruzar: acasalamento + cotação PDF
    pg.get_by_text('Rebanho', exact=False).last.click(); pg.wait_for_timeout(1200)
    pg.locator('.an button.mini.p', has_text='Cruzar').first.click(); pg.wait_for_timeout(3500)
    assert pg.get_by_text('Touros recomendados', exact=False).is_visible(), 'acasalamento sem recs'
    with pg.expect_response(lambda r:'/api/campo/cotacao/pdf' in r.url) as ri:
        pg.get_by_text('📄 Baixar PDF').click()
    assert ri.value.status==200, 'cotacao falhou'
    step('cruzar + cotação PDF')

    # 6) Fazenda: auditoria + movimentação entrada + briefing PDF
    pg.get_by_text('Fazenda', exact=False).last.click(); pg.wait_for_timeout(900)
    pg.get_by_text('Rodar auditoria').click(); pg.wait_for_timeout(1500)
    assert pg.get_by_text('IQGg médio', exact=False).is_visible(), 'auditoria nao rodou'
    pg.locator('.seg.wrap3 button', has_text='entrada').first.click()
    pg.evaluate("""()=>{const set=(t,v)=>{const l=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith(t));if(l){l.nextElementSibling.value=v;l.nextElementSibling.dispatchEvent(new Event('input',{bubbles:true}));}};set('Nº da GTA','GTA-E2E');set('Quantidade','50');}""")
    pg.get_by_text('Registrar movimentação').click(); pg.wait_for_timeout(1800)
    with pg.expect_response(lambda r:'/api/campo/briefing/pdf' in r.url) as ri2:
        pg.get_by_text('📋 Briefing de chegada').click()
    assert ri2.value.status==200, 'briefing falhou'
    step('auditoria + GTA + briefing PDF')

    # 7) Persistência: reload restaura fazenda + aba
    pg.reload(wait_until='networkidle'); pg.wait_for_timeout(2000)
    assert 'E2E' in pg.locator('.top .sub').inner_text(), 'fazenda nao persistiu'
    step('persistência pós-reload')

    pg.screenshot(path=f'{OUT}/e2e-final.png', full_page=True)
    print('=== PDFs:', pdfs)
    print('=== console/page errors:', len(errs))
    for e in errs[:15]: print('  ', e)
    b.close()
    assert len(errs)==0, 'HOUVE ERROS'
    print('E2E REGRESSION OK — 0 erros')
