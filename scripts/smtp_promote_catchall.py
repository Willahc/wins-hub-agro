#!/usr/bin/env python3
"""Tenta PROMOVER os e-mails 'accept_all' do Hunter (caixa não confirmada) usando verificação SMTP
real (RCPT TO + teste de catch-all). Se o SMTP achar mailbox REAL (250 no e-mail, 550 no aleatório),
promove verif_status -> 'valid'. Se 550 no e-mail, marca 'invalid'. Catch-all/inconclusivo: mantém.
Expectativa honesta: accept_all do Hunter ≈ catch_all do SMTP, então poucos promovem (só falsos-positivos
do Hunter). Roda no api (porta 25 aberta, tem POSTGRES_PASSWORD). Uso: docker cp + docker exec."""
import os, sys, smtplib, socket, time
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
FREE={'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com','msn.com','globo.com'}
HELO="winshubagro.cloud"; MAILFROM="verify@winshubagro.cloud"
_mx={}
def mx_of(d):
    if d in _mx: return _mx[d]
    try:
        j=httpx.get("https://dns.google/resolve",params={"name":d,"type":"MX"},timeout=8).json()
        mxs=sorted([(int(a["data"].split()[0]),a["data"].split()[1].rstrip('.')) for a in j.get("Answer",[]) if a.get("type")==15])
        _mx[d]=mxs[0][1] if mxs else None
    except Exception: _mx[d]=None
    return _mx[d]
def rcpt(mx, addr):
    try:
        s=smtplib.SMTP(mx,25,timeout=15); s.helo(HELO); s.mail(MAILFROM); c,_=s.rcpt(addr); s.quit(); return c
    except (smtplib.SMTPServerDisconnected,smtplib.SMTPConnectError,socket.timeout,OSError,smtplib.SMTPException): return -1
def check(row):
    email=row["email"].strip().lower(); dom=email.split("@",1)[1]
    if dom in FREE: return (row,"free",None)
    mx=mx_of(dom)
    if not mx: return (row,"sem_mx",None)
    c=rcpt(mx,email)
    if c==-1: return (row,"inconclusivo",None)
    if c>=500: return (row,"INVALIDO","invalid")
    if c!=250: return (row,"inconclusivo",None)
    time.sleep(0.5)
    ca=rcpt(mx,"zz"+str(abs(hash(dom))%99999)+"nao-existe@"+dom)
    if ca==250: return (row,"catch_all",None)
    return (row,"VALIDO","valid")          # mailbox real + domínio rejeita inexistente = PROMOVE
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
      SELECT 'hunter_email' tbl,'email_decisor' col,cnpj_basico,email_decisor email FROM prospeccao.hunter_email WHERE verif_status='accept_all'
      UNION ALL SELECT 'hunter_operador','email_operador',cnpj_basico,email_operador FROM prospeccao.hunter_operador WHERE verif_status='accept_all'
      UNION ALL SELECT 'hunter_resto','email_operador',cnpj_basico,email_operador FROM prospeccao.hunter_resto WHERE verif_status='accept_all'""")
    rows=[dict(r) for r in cur.fetchall()]
    print(f"[SMTP-promote em {len(rows)} catch-all do Hunter]", file=sys.stderr, flush=True)
    agg={}; promo=0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(check,r):r for r in rows}
        for f in as_completed(futs):
            row,label,newst=f.result(); agg[label]=agg.get(label,0)+1
            if newst:
                cur.execute(f"UPDATE prospeccao.{row['tbl']} SET verif_status=%s WHERE cnpj_basico=%s AND {row['col']}=%s",
                            (newst,row['cnpj_basico'],row['email']))
                if newst=='valid': promo+=1
    print(f"\n[FIM] {len(rows)} | promovidos a valid: {promo} | "+" ".join(f"{k}:{v}" for k,v in sorted(agg.items())), file=sys.stderr)
if __name__=="__main__": main()
