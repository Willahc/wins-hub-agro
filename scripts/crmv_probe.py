#!/usr/bin/env python3
"""Sonda de viabilidade CRMV (Implanta). Abre ConsultaInscritos, tenta resolver o
reCAPTCHA v2 (checkbox) e dispara a busca, interceptando a request/response do Buscar.
Decide: captcha passa de graça? qual o payload? quantos registros por chamada (paginação)?"""
import sys, json, asyncio
from playwright.async_api import async_playwright

UF = sys.argv[1] if len(sys.argv) > 1 else "sp"
URL = f"https://crmv-{UF}.implanta.net.br/servicosonline/Publico/ConsultaInscritos/"

async def main():
    async with async_playwright() as p:
        import os
        headful = os.environ.get("HEADFUL") == "1"
        browser = await p.chromium.launch(headless=not headful, args=["--no-sandbox","--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-BR", viewport={"width":1280,"height":900})
        page = await ctx.new_page()
        captured = {}
        async def on_resp(resp):
            if "Buscar" in resp.url:
                captured["url"] = resp.url
                captured["status"] = resp.status
                try:
                    captured["body"] = (await resp.text())[:4000]
                except Exception as e:
                    captured["body"] = f"<err {e}>"
                req = resp.request
                captured["post_data"] = req.post_data
                captured["headers"] = {k: v for k, v in req.headers.items() if k.lower() in ("__requestverificationtoken","content-type","x-requested-with")}
        page.on("response", on_resp)

        await page.goto(URL, wait_until="domcontentloaded", timeout=40000)
        print(f"[+] página carregada: {URL}")

        # tenta clicar no checkbox do reCAPTCHA v2 (frame_locator é robusto p/ iframe cross-origin)
        token = ""
        try:
            anchor = page.frame_locator("iframe[src*='api2/anchor'], iframe[title='reCAPTCHA']").locator("#recaptcha-anchor")
            await anchor.wait_for(state="visible", timeout=15000)
            await anchor.click(timeout=10000)
            print("[+] checkbox clicado, aguardando token...")
            for _ in range(25):
                token = await page.evaluate("(document.getElementById('g-recaptcha-response')||{}).value || ''")
                if token:
                    break
                await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"[!] erro no checkbox: {e}")
        print(f"[token] len={len(token)} (vazio = challenge de imagem barrou)")

        # dispara a busca pela própria UI (clica Consultar)
        try:
            for sel in ["button:has-text('Consultar')","input[value='Consultar']","#btnConsultar","a:has-text('Consultar')"]:
                el = await page.query_selector(sel)
                if el:
                    await el.click(); print(f"[+] cliquei em Consultar via {sel}"); break
            await page.wait_for_timeout(6000)
        except Exception as e:
            print(f"[!] erro ao consultar: {e}")

        print("=== BUSCAR capturado ===")
        print(json.dumps(captured, ensure_ascii=False, indent=2)[:4500])
        await browser.close()

asyncio.run(main())
