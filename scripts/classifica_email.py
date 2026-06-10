#!/usr/bin/env python3
"""Classifica o e-mail de cada lead do ICP: é do DECISOR (local-part bate com o nome dele),
gatekeeper (fiscal@/nfe@...), contador (domínio de contabilidade), ou genérico (sem bater nome)."""
import os, re, unicodedata
import psycopg2, psycopg2.extras
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
def na(s): return unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()
ROLE=('fiscal','contabil','contab','nfe','nf-e','juridic','dp','rh','financ','cobranca','compras',
      'contato','adm','escritorio','vendas','comercial','suporte','sac','recepcao','gerencia','diretoria','faturamento')
CONTADOR=('contab','assessor','advoc','advog','consult','escritorio','cont.')
STOP={'de','da','do','das','dos','e','filho','junior','neto','sobrinho','jose','joao','maria','ana','luiz','luis','carlos','antonio','paulo','pedro','francisco'}
conn=psycopg2.connect(**DB); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("""SELECT decisor, email FROM (
  SELECT decisor,email,email_status FROM prospeccao.icp527_screen
  UNION ALL SELECT decisor,email,email_status FROM prospeccao.icp_media_screen) x
  WHERE email IS NOT NULL AND email_status IN ('mx_ok','free_entregavel')""")
rows=cur.fetchall()
agg={'decisor':0,'gatekeeper':0,'contador':0,'generico':0}
ex={'decisor':[], 'gatekeeper':[]}
for r in rows:
    email=na(r['email']); local=email.split('@')[0]; dom=email.split('@')[1] if '@' in email else ''
    local_clean=re.sub(r'[^a-z]','',local)
    nome=na(re.sub(r'\(.*?\)','',r['decisor'] or ''))
    toks=[t for t in re.sub(r'[^a-z ]',' ',nome).split() if len(t)>=4 and t not in STOP]
    if any(t in local_clean for t in toks):
        agg['decisor']+=1
        if len(ex['decisor'])<6: ex['decisor'].append(f"{r['decisor'][:28]} -> {r['email']}")
    elif any(local.startswith(w) or local==w for w in ROLE):
        agg['gatekeeper']+=1
        if len(ex['gatekeeper'])<5: ex['gatekeeper'].append(r['email'])
    elif any(c in dom for c in CONTADOR):
        agg['contador']+=1
    else:
        agg['generico']+=1
tot=sum(agg.values())
print(f"=== {tot} e-mails entregáveis do ICP, por TIPO ===")
for k in ('decisor','gatekeeper','contador','generico'):
    print(f"  {k:11}: {agg[k]:4} ({100*agg[k]//tot}%)")
print("\n--- amostra DECISOR (e-mail bate com o nome) ---")
for s in ex['decisor']: print("  ",s)
print("--- amostra GATEKEEPER ---")
for s in ex['gatekeeper']: print("  ",s)
