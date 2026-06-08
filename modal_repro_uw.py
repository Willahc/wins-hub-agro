#!/usr/bin/env python3
"""Reproduz o cenário do William: ultrawide LG @ Windows 150%.
3440x1440 @150% -> ~2293x960 efetivo;  2560x1080 @150% -> ~1707x720 efetivo.
Abre o modal do bezerro e mede header/body/footer + tira screenshot."""
from pathlib import Path
from playwright.sync_api import sync_playwright

token = Path("/tmp/wins_token.txt").read_text().strip()
OUT = Path("/root/wins_agro_v1/smoke_shots"); OUT.mkdir(exist_ok=True)
DGET = "(()=>{const r=document.querySelector('[x-data]');return r.__x?r.__x.$data:r._x_dataStack[0]})()"

def ids(pg):
    return pg.evaluate("""async ()=>{
        const t = await (await fetch('/api/animais/busca?sexo=M&limit=5')).json();
        const m = await (await fetch('/api/animais/busca?sexo=F&limit=5')).json();
        const arrT=Array.isArray(t)?t:(t&&t.itens)||[], arrM=Array.isArray(m)?m:(m&&m.itens)||[];
        return {touro:(arrT[0]||{}).id, vaca:(arrM[0]||{}).id};
    }""")

def medir(pg):
    return pg.evaluate("""()=>{
        const ov=[...document.querySelectorAll('.modal-overlay')].find(o=>getComputedStyle(o).display!=='none');
        if(!ov) return {ok:false};
        const modal=ov.querySelector('.modal'), foot=ov.querySelector('.modal-footer'),
              body=ov.querySelector('.modal-body');
        const mr=modal.getBoundingClientRect();
        const o={modalH:Math.round(mr.height), vh:window.innerHeight,
                 baseDentro:mr.bottom<=window.innerHeight+1, topoDentro:mr.top>=-1,
                 bodyScroll: body.scrollHeight>body.clientHeight+1};
        if(foot){const fr=foot.getBoundingClientRect();
            o.footerBottom=Math.round(fr.bottom); o.footerDentro=fr.bottom<=window.innerHeight+1;}
        return o;
    }""")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=[
        "--host-resolver-rules=MAP winshubagro.cloud 127.0.0.1","--no-sandbox"])
    for w,h,label in [(2293,960,"3440x1440@150"),(1707,720,"2560x1080@150")]:
        ctx=b.new_context(viewport={"width":w,"height":h}, device_scale_factor=1)
        ctx.add_cookies([{"name":"access_token","value":token,"domain":"winshubagro.cloud",
                          "path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"}])
        pg=ctx.new_page()
        pg.goto("https://winshubagro.cloud/", wait_until="networkidle", timeout=30000)
        pg.wait_for_timeout(1200)
        i=ids(pg)
        pg.evaluate(f"async ()=>{{const d={DGET}; await d.abrirFilhote({i['touro']},{i['vaca']});}}")
        pg.wait_for_timeout(1600)
        m=medir(pg)
        print(f"[{label} -> {w}x{h}] {m}")
        pg.screenshot(path=str(OUT/f"repro_{label}.png"))
        ctx.close()
    b.close()
