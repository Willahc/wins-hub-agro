#!/usr/bin/env python3
"""Segue o LINK EXTERNO da bio do IG (linktree/site da fazenda, já raspado pelo Apify em
ig_contato.ext) e extrai o WhatsApp de lá — é o número da PRÓPRIA fazenda (alta precisão).
Upsert em prospeccao.cabanha_zap (fonte='extlink'). Roda só nas cabanhas SEM zap."""
import os, re, sys
import psycopg2, psycopg2.extras, httpx

DB = dict(host="db", dbname="wins_agro", user="postgres", password=os.getenv("POSTGRES_PASSWORD",""))
RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{8,13})', re.I)
RE_ZAP = re.compile(r'(?:whats\s?app|whatsapp|zap)\D{0,14}(\(?\d{2}\)?\s?9\d{4}[-\s.]?\d{4})', re.I)
DDD_OK = {'11','12','13','14','15','16','17','18','19','21','22','24','27','28','31','32','33','34','35','37','38',
          '41','42','43','44','45','46','47','48','49','51','53','54','55','61','62','63','64','65','66','67','68',
          '69','71','73','74','75','77','79','81','82','83','84','85','86','87','88','89','91','92','93','94','95','96','97','98','99'}
DDD2UF = {}
for _u,_dd in [('SP',range(11,20)),('RJ',[21,22,24]),('ES',[27,28]),('MG',[31,32,33,34,35,37,38]),('PR',[41,42,43,44,45,46]),
   ('SC',[47,48,49]),('RS',[51,53,54,55]),('DF',[61]),('GO',[62,64]),('TO',[63]),('MT',[65,66]),('MS',[67]),('AC',[68]),
   ('RO',[69]),('BA',[71,73,74,75,77]),('SE',[79]),('PE',[81,87]),('AL',[82]),('PB',[83]),('RN',[84]),('CE',[85,88]),
   ('PI',[86,89]),('PA',[91,93,94]),('AM',[92,97]),('RR',[95]),('AP',[96]),('MA',[98,99])]:
    for _d in _dd: DDD2UF[str(_d)]=_u

def norm_mobile(raw):
    d=re.sub(r'\D','',raw or '')
    if d.startswith('55') and len(d)>=12: d=d[2:]
    if len(d)==11 and d[2]=='9' and d[:2] in DDD_OK: return d
    if len(d)==10 and d[2] in '6789' and d[:2] in DDD_OK: return d[:2]+'9'+d[2:]
    return None

UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def main():
    c=psycopg2.connect(**DB); c.autocommit=True; cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.cabanha_zap(cnpj text PRIMARY KEY, decisor text, fazenda text,
        uf text, whatsapp text, fonte text, instagram text, via_busca text, buscado_em timestamptz DEFAULT now(),
        uf_match boolean)""")
    cur.execute("""
      WITH semzap AS (SELECT cnpj, decisor, COALESCE(cabanha,fazenda) fazenda, uf, instagram
         FROM prospeccao.v_fila_prospeccao
         WHERE ativo AND whatsapp IS NULL AND prospeccao.cel_whats(telefone) IS NULL AND instagram<>'')
      SELECT s.*, ig.ext FROM semzap s JOIN prospeccao.ig_contato ig ON ig.username=s.instagram
      WHERE COALESCE(ig.ext,'')<>''""")
    rows=cur.fetchall(); print(f"[extlink: {len(rows)} links a seguir]", file=sys.stderr, flush=True)
    achou=ok=0
    for i,r in enumerate(rows,1):
        url=r['ext'] or ''
        if not url.startswith('http'): url='https://'+url
        zap=None
        try:
            t=httpx.get(url, headers=UA, timeout=12, follow_redirects=True).text
            m=RE_WA.search(t) or RE_ZAP.search(t)
            if m: zap=norm_mobile(m.group(1))
        except Exception: pass
        if not zap: continue
        ufm = DDD2UF.get(zap[:2])==r['uf']; achou+=1; ok+=int(bool(ufm))
        cur.execute("""INSERT INTO prospeccao.cabanha_zap(cnpj,decisor,fazenda,uf,whatsapp,fonte,instagram,via_busca,uf_match)
          VALUES(%s,%s,%s,%s,%s,'extlink',%s,'extlink',%s)
          ON CONFLICT(cnpj) DO UPDATE SET whatsapp=EXCLUDED.whatsapp,fonte='extlink',
            instagram=EXCLUDED.instagram,via_busca='extlink',uf_match=EXCLUDED.uf_match,buscado_em=now()""",
          (r['cnpj'],r['decisor'],r['fazenda'],r['uf'],zap,r['instagram'],ufm))
        if i%30==0: print(f"  {i}/{len(rows)} | wa {achou}", file=sys.stderr, flush=True)
    print(f"[FIM extlink] {len(rows)} · WhatsApp {achou} · DDD-UF ok {ok}", file=sys.stderr, flush=True)

if __name__=="__main__": main()
