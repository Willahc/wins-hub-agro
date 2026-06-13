#!/usr/bin/env python3
"""Probe: descobre QUAL campo do ator Apify carrega e-mail/telefone de contato da conta profissional.
Roda 1 ator em poucos handles via run-sync-get-dataset-items e dumpa as chaves + campos de contato."""
import os, sys, json, httpx
TOKEN=os.environ['APIFY_TOKEN']
ACTOR=os.environ.get('ACTOR','apify~instagram-scraper')
handles=sys.argv[1:] or ['nelore_modelo','neloreboi']
urls=[f"https://www.instagram.com/{h}/" for h in handles]
payload={"directUrls":urls,"resultsType":"details","resultsLimit":1,"addParentData":False}
url=f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={TOKEN}"
print(f"[ator {ACTOR} | {len(urls)} handles]", file=sys.stderr, flush=True)
r=httpx.post(url, json=payload, timeout=180)
print("HTTP", r.status_code, file=sys.stderr, flush=True)
items=r.json() if r.headers.get('content-type','').startswith('application/json') else []
print(f"itens retornados: {len(items)}", file=sys.stderr, flush=True)
CONTACT_KEYS=['email','public_email','business_email','publicEmail','businessEmail',
              'phone','public_phone_number','business_phone_number','contact_phone_number',
              'publicPhoneNumber','businessPhoneNumber','contactPhoneNumber','businessCategoryName',
              'isBusinessAccount','externalUrl','externalUrls']
for it in items[:5]:
    if not isinstance(it,dict):
        print("item não-dict:", str(it)[:200]); continue
    u=it.get('username') or it.get('inputUrl')
    print(f"\n=== {u} ===")
    print("TODAS as chaves:", sorted(it.keys()))
    print("contato:", {k:it.get(k) for k in CONTACT_KEYS if k in it})
