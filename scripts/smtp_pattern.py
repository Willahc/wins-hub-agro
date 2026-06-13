#!/usr/bin/env python3
"""Resgata e-mail nos domínios onde o Hunter deu VAZIO (mas o domínio existe), SEM gastar Hunter:
gera padrões de e-mail a partir do nome do decisor/operador e valida por RCPT TO real (porta 25).
Pula domínio catch-all (RCPT aceita qualquer coisa -> não dá pra confirmar padrão). Grava
prospeccao.smtp_pattern (status VALIDO/catch_all/sem_mx/inconclusivo).
Uso: docker run ... --env-file .env -e NSHARD=6 -e SHARD=n hunterpy python /s/smtp_pattern.py"""
import os, re, sys, smtplib, socket, time, unicodedata
import psycopg2, psycopg2.extras, httpx
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
HELO="winshubagro.cloud"; MAILFROM="verify@winshubagro.cloud"
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
_mx={}
def mx_of(d):
    if d in _mx: return _mx[d]
    try:
        j=httpx.get("https://dns.google/resolve",params={"name":d,"type":"MX"},timeout=8).json()
        mxs=sorted([(int(a["data"].split()[0]),a["data"].split()[1].rstrip('.')) for a in j.get("Answer",[]) if a.get("type")==15])
        _mx[d]=mxs[0][1] if mxs else None
    except Exception: _mx[d]=None
    return _mx[d]
def asc(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
def patterns(nome, dom):
    w=[asc(x).lower() for x in re.sub(r'\(.*','',nome or '').split() if len(x)>1]
    if len(w)<2: return []
    f,l=w[0],w[-1]
    if l.upper() in SUF and len(w)>=3: l=w[-2]
    cand=[f, f+'.'+l, f+l, f[0]+l, f+'_'+l, f+'.'+w[1] if len(w)>2 else None]
    return [c+'@'+dom for c in dict.fromkeys([c for c in cand if c])]
def rcpt(s, addr):
    try: c,_=s.rcpt(addr); return c
    except Exception: return -1
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.smtp_pattern(
        cnpj_basico varchar(8) PRIMARY KEY, dominio text, email text, status text, achado_em timestamptz DEFAULT now());""")
    cur.execute("""
      SELECT cnpj_basico, dom, nome FROM (
        SELECT cnpj_basico, dominio_resolvido dom, operador nome FROM prospeccao.hunter_resto
          WHERE status='vazio' AND dominio_resolvido IS NOT NULL AND operador ~ '\S\s+\S'
        UNION
        SELECT cnpj_basico, dominio dom, decisor FROM prospeccao.hunter_email
          WHERE status='vazio' AND dominio IS NOT NULL AND decisor ~ '\S\s+\S'
      ) u WHERE cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.smtp_pattern)
    """)
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD]
    print(f"[SMTP-pattern: {len(rows)} domínios | shard {SHARD}/{NSHARD}]", file=sys.stderr, flush=True)
    found=0
    for i,r in enumerate(rows,1):
        dom=r['dom']; cands=patterns(r['nome'], dom)
        if not cands:
            continue
        mx=mx_of(dom)
        st='sem_mx'; email=None
        if mx:
            try:
                s=smtplib.SMTP(mx,25,timeout=12); s.helo(HELO); s.mail(MAILFROM)
                ca=rcpt(s, 'zzq'+str(abs(hash(dom))%9999)+'naoexiste@'+dom)
                if ca==250: st='catch_all'
                elif ca==-1: st='inconclusivo'
                else:
                    st='inconclusivo'
                    for c in cands:
                        code=rcpt(s,c); time.sleep(0.3)
                        if code==250: email=c; st='VALIDO'; break
                        if code>=500: st='testado_sem_match'
                try: s.quit()
                except Exception: pass
            except Exception: st='inconclusivo'
        if email: found+=1
        cur.execute("""INSERT INTO prospeccao.smtp_pattern(cnpj_basico,dominio,email,status) VALUES(%s,%s,%s,%s)
            ON CONFLICT(cnpj_basico) DO UPDATE SET email=EXCLUDED.email,status=EXCLUDED.status""",
            (r['cnpj_basico'], dom, email, st))
        if i%40==0: print(f"  {i}/{len(rows)} | validos {found}", file=sys.stderr, flush=True)
    print(f"\n[FIM] {len(rows)} | e-mails VALIDOS por padrão: {found}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
