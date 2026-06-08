#!/usr/bin/env python3
"""Valida que os 3 modais (bezerro, touro, matriz) cabem em zoom 100% em
1366x768 e 1920x1080: header no topo, footer/botões dentro do viewport,
scroll interno no body quando o conteúdo excede. Foco no rodapé do bezerro
(botões Ficha do pai/mãe) que antes cortava."""
from pathlib import Path
from playwright.sync_api import sync_playwright

token = Path("/tmp/wins_token.txt").read_text().strip()
OUT = Path("/root/wins_agro_v1/smoke_shots"); OUT.mkdir(exist_ok=True)
errs = []

DGET = "(()=>{const r=document.querySelector('[x-data]');return r.__x?r.__x.$data:r._x_dataStack[0]})()"

def ids(pg):
    return pg.evaluate("""async ()=>{
        const t = await (await fetch('/api/animais/busca?sexo=M&limit=5')).json();
        const m = await (await fetch('/api/animais/busca?sexo=F&limit=5')).json();
        const arrT = Array.isArray(t)?t:(t&&t.itens)||[];
        const arrM = Array.isArray(m)?m:(m&&m.itens)||[];
        return { touro: (arrT[0]||{}).id, vaca: (arrM[0]||{}).id,
                 nt: arrT.length, nm: arrM.length };
    }""")

def medir(pg, overlay_attr):
    # overlay_attr: o x-show que identifica o modal aberto
    return pg.evaluate("""(sel)=>{
        const ov=[...document.querySelectorAll('.modal-overlay')]
            .find(o=>getComputedStyle(o).display!=='none');
        if(!ov) return {ok:false, why:'sem overlay'};
        const modal=ov.querySelector('.modal');
        const head=ov.querySelector('.modal-head');
        const body=ov.querySelector('.modal-body');
        const footer=ov.querySelector('.modal-footer');
        if(!modal||!head||!body) return {ok:false, why:'sem partes'};
        const mr=modal.getBoundingClientRect(), hr=head.getBoundingClientRect(),
              br=body.getBoundingClientRect();
        const out={
            ok:true,
            topoDentro: mr.top>=-1,
            baseDentro: mr.bottom<=window.innerHeight+1,
            tituloVisivel: hr.top>=-1 && hr.bottom<=window.innerHeight+1,
            altModal: Math.round(mr.height), vh: window.innerHeight,
            bodyScrollavel: body.scrollHeight>body.clientHeight+1,
            bodyOverflow: getComputedStyle(body).overflowY,
        };
        if(footer){
            const fr=footer.getBoundingClientRect();
            out.footerDentro = fr.bottom<=window.innerHeight+1 && fr.top>=mr.top-1;
            const btns=[...footer.querySelectorAll('button')];
            out.botoesDentro = btns.length>0 && btns.every(b=>{
                const r=b.getBoundingClientRect();
                return r.bottom<=window.innerHeight+1 && r.top>=-1;
            });
            out.nBotoes = btns.length;
        }
        return out;
    }""", overlay_attr)

def linha(tag, nome, m):
    base = f"[{tag}] {nome:8s} topo={m.get('topoDentro')} base={m.get('baseDentro')} titulo={m.get('tituloVisivel')} modalH={m.get('altModal')}/{m.get('vh')} scrollBody={m.get('bodyScrollavel')}({m.get('bodyOverflow')})"
    if 'footerDentro' in m:
        base += f" footer={m.get('footerDentro')} botoes={m.get('botoesDentro')}({m.get('nBotoes')})"
    print(base)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=[
        "--host-resolver-rules=MAP winshubagro.cloud 127.0.0.1",
        "--no-sandbox"])
    for w,h in [(1366,768),(1920,1080)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=1)
        ctx.add_cookies([{"name":"access_token","value":token,"domain":"winshubagro.cloud",
                          "path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"}])
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("https://winshubagro.cloud/", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(1200)
        info = ids(pg)
        tag = f"{w}x{h} z100%"
        print(f"\n=== {tag} | touro={info.get('touro')} vaca={info.get('vaca')} (nt={info.get('nt')} nm={info.get('nm')}) ===")
        if not info.get('touro') or not info.get('vaca'):
            print("  !! não consegui IDs; abortando esta tela"); ctx.close(); continue

        # --- BEZERRO (foco: footer Ficha do pai/mãe) ---
        pg.evaluate(f"async ()=>{{const d={DGET}; await d.abrirFilhote({info['touro']},{info['vaca']});}}")
        pg.wait_for_timeout(1600)
        m = medir(pg, ""); linha(tag, "bezerro", m)
        if w==1366:
            pg.screenshot(path=str(OUT/"modal_bezerro_fit.png"))
        pg.evaluate(f"()=>{{const d={DGET}; d.fecharFilhote();}}"); pg.wait_for_timeout(400)
        # abre/fecha 5x p/ garantir estabilidade
        for _ in range(5):
            pg.evaluate(f"async ()=>{{const d={DGET}; await d.abrirFilhote({info['touro']},{info['vaca']});}}")
            pg.wait_for_timeout(250)
            pg.evaluate(f"()=>{{const d={DGET}; d.fecharFilhote();}}")
            pg.wait_for_timeout(150)

        # --- TOURO ---
        pg.evaluate(f"async ()=>{{const d={DGET}; await d.abrirTouro({info['touro']});}}")
        pg.wait_for_timeout(1400)
        linha(tag, "touro", medir(pg, ""))
        pg.evaluate(f"()=>{{const d={DGET}; d.fecharTouro();}}"); pg.wait_for_timeout(400)

        # --- MATRIZ ---
        pg.evaluate(f"async ()=>{{const d={DGET}; await d.abrirMatriz({info['vaca']});}}")
        pg.wait_for_timeout(1400)
        linha(tag, "matriz", medir(pg, ""))
        if w==1366:
            pg.screenshot(path=str(OUT/"modal_matriz_fit.png"))
        pg.evaluate(f"()=>{{const d={DGET}; d.fecharMatriz();}}"); pg.wait_for_timeout(300)
        ctx.close()
    b.close()

print(f"\nJS errors={len(errs)}")
for e in errs[:8]: print("  -", e)
