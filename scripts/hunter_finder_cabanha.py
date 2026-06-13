#!/usr/bin/env python3
"""Hunter Email Finder nos STUDS ELITE (prospeccao.cabanha_extra): site próprio + nome do decisor
-> e-mail real do decisor + score. Esses studs entraram por QSA/Serper (sem e-mail RFB) e nunca
passaram pelo Hunter (que só leu icp527/icp_media). Grava em prospeccao.hunter_email (chave = left(cnpj14,8))."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','99999'))
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
BADDOM=('instagram','facebook','econodata','cnpj','consultasocio','escavador','youtube','linkedin','google','mfrural','wikipedia','gov.br','jusbrasil','tiktok',
        # domínios de TERCEIRO (mídia/associação/programa/vendor/bureau): Hunter chuta padrão e devolve e-mail FALSO do decisor
        'portaldbo','comprerural','erural.net','lancerural','redepress','calameo','ancp.org','geneplus','selectsires','semex.com','serasa','.mil.','folha.','uol.com','scotconsultoria','beefpoint','canalrural','prudentec')
def dom_of(url):
    m=re.match(r'^https?://(www\.)?([^/]+)', (url or '').lower())
    return m.group(2) if m else ''
def split_nome(d):
    w=[x for x in re.sub(r'\(.*','',d or '').strip().split() if len(x)>1]
    if not w: return None,None
    first=w[0]; last=w[-1]
    if last.upper() in SUF and len(w)>=2: last=w[-2]
    return first,last
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT left(regexp_replace(cnpj14,'\\D','','g'),8) AS cnpj_basico,
                          decisor, site, cabanha
      FROM prospeccao.cabanha_extra
      WHERE decisor IS NOT NULL AND decisor<>''
        AND site IS NOT NULL AND site<>''
        AND cnpj14 IS NOT NULL AND length(regexp_replace(cnpj14,'\\D','','g'))>=8
        AND left(regexp_replace(cnpj14,'\\D','','g'),8) NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
      ORDER BY cnpj_basico LIMIT %s""", (LIMIT,))
    rows=cur.fetchall()
    proc=[]
    for r in rows:
        dom=dom_of(r['site'])
        if dom and not any(b in dom for b in BADDOM): proc.append((r,dom))
    print(f"[Hunter cabanha finder: {len(proc)} studs com site próprio válido]", file=sys.stderr, flush=True)
    achou=0
    with httpx.Client(timeout=25) as cl:
        for i,(r,dom) in enumerate(proc,1):
            first,last=split_nome(r['decisor'])
            if not first: continue
            em=sc=None; ok_api=False
            for t in range(3):   # retry: falha de API != "vazio" (que é permanente)
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':dom,'first_name':first,'last_name':last,'api_key':KEY}).json()
                    em=j.get('data',{}).get('email'); sc=j.get('data',{}).get('score'); ok_api=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if not ok_api:
                print(f"  {i} API falhou 3x — pulado (re-run tenta de novo)", file=sys.stderr); continue
            if em: achou+=1
            cur.execute("INSERT INTO prospeccao.hunter_email(cnpj_basico,decisor,dominio,email_decisor,score,status) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET email_decisor=EXCLUDED.email_decisor,score=EXCLUDED.score,status=EXCLUDED.status,dominio=EXCLUDED.dominio",
                        (r['cnpj_basico'], r['decisor'], dom, em, sc, 'achado' if em else 'vazio'))
            time.sleep(0.4)
            if i%30==0: print(f"  {i}/{len(proc)} | achados {achou}", file=sys.stderr, flush=True)
    n=len(proc) or 1
    print(f"\n[FIM] {len(proc)} | e-mail decisor: {achou} ({100*achou//n}%)", file=sys.stderr, flush=True)
if __name__=="__main__": main()
