#!/usr/bin/env python3
"""Validação MÁXIMA de e-mail do ICP: verificação SMTP real (a caixa existe?) via RCPT TO,
+ detecção de catch-all (domínio aceita qualquer coisa = validade incerta). Porta 25 aberta.
Free providers (gmail/hotmail) não são verificáveis por RCPT (aceitam tudo) → marcados à parte.
Grava prospeccao.email_valido. Roda no container api."""
import os, re, sys, smtplib, socket, time
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
FREE={'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com','msn.com','globo.com'}
HELO="winshubagro.cloud"; MAILFROM="verify@winshubagro.cloud"
_mxcache={}

def mx_of(dom):
    if dom in _mxcache: return _mxcache[dom]
    try:
        j=httpx.get("https://dns.google/resolve",params={"name":dom,"type":"MX"},timeout=8).json()
        mxs=sorted([(int(a["data"].split()[0]),a["data"].split()[1].rstrip('.')) for a in j.get("Answer",[]) if a.get("type")==15])
        _mxcache[dom]=mxs[0][1] if mxs else None
    except Exception: _mxcache[dom]=None
    return _mxcache[dom]

def rcpt(mx, addr):
    """retorna code do RCPT TO (250=aceita). -1 em erro de conexão."""
    try:
        s=smtplib.SMTP(mx, 25, timeout=15); s.ehlo_or_helo_if_needed=lambda:None
        s.helo(HELO); s.mail(MAILFROM); code,_=s.rcpt(addr); s.quit(); return code
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, OSError, smtplib.SMTPException):
        return -1

def verify(row):
    email=row["email"].strip().lower(); dom=email.split("@",1)[1]
    if dom in FREE: return (row["cnpj_basico"], email, dom, "free_entregavel", False)
    mx=mx_of(dom)
    if not mx: return (row["cnpj_basico"], email, dom, "sem_mx", False)
    c=rcpt(mx, email)
    if c==-1: return (row["cnpj_basico"], email, dom, "inconclusivo", False)
    if c>=500: return (row["cnpj_basico"], email, dom, "INVALIDO", False)
    if c!=250: return (row["cnpj_basico"], email, dom, "inconclusivo", False)
    # aceitou -> testa catch-all
    time.sleep(0.5)
    ca=rcpt(mx, "zz"+str(abs(hash(dom))%99999)+"nao-existe@"+dom)
    catch = (ca==250)
    return (row["cnpj_basico"], email, dom, ("catch_all" if catch else "VALIDO"), catch)

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.email_valido(
        cnpj_basico varchar(8), email text, dominio text, smtp_status text, catch_all bool,
        verificado_em timestamptz DEFAULT now(), PRIMARY KEY(cnpj_basico,email));""")
    cur.execute("""SELECT cnpj_basico, email FROM (
        SELECT cnpj_basico,email,email_status FROM prospeccao.icp527_screen
        UNION ALL SELECT cnpj_basico,email,email_status FROM prospeccao.icp_media_screen) x
        WHERE email IS NOT NULL AND email_status IN ('mx_ok','free_entregavel')""")
    rows=[dict(r) for r in cur.fetchall()]
    # dedupe
    seen=set(); uniq=[]
    for r in rows:
        k=(r["cnpj_basico"],r["email"])
        if k in seen: continue
        seen.add(k); uniq.append(r)
    print(f"[verificando {len(uniq)} e-mails do ICP via SMTP]", file=sys.stderr, flush=True)
    agg={}; done=0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs={ex.submit(verify,r):r for r in uniq}
        for f in as_completed(futs):
            res=f.result(); done+=1; agg[res[3]]=agg.get(res[3],0)+1
            cur.execute("""INSERT INTO prospeccao.email_valido(cnpj_basico,email,dominio,smtp_status,catch_all)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico,email) DO UPDATE SET smtp_status=EXCLUDED.smtp_status,catch_all=EXCLUDED.catch_all,verificado_em=now()""", res)
            if done%50==0: print(f"  {done}/{len(uniq)} | "+" ".join(f"{k}:{v}" for k,v in sorted(agg.items())), file=sys.stderr, flush=True)
    print(f"\n[FIM] {done} e-mails:", file=sys.stderr)
    for k,v in sorted(agg.items(), key=lambda x:-x[1]): print(f"  {k}: {v}", file=sys.stderr)

if __name__=="__main__": main()
