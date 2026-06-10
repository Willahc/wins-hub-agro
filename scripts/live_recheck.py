#!/usr/bin/env python3
"""Re-checagem AO VIVO do ICP (1.461) via BrasilAPI: a empresa está ATIVA agora? o decisor (QSA)
ainda é o atual? Pega validade máxima de que o lead é real e vivo. Grava prospeccao.icp_recheck."""
import os, sys, time, re
import psycopg2, psycopg2.extras, httpx
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
QUALS=("Administrador","Sócio-Administrador","Sócio","Presidente","Diretor","Titular","Proprietário")
HOLD=(" S/A"," S.A","PARTICIPAC","HOLDING","EMPREEND"," FUNDO")
def pessoa(n): u=(n or "").upper(); return not any(h in u for h in HOLD)
def qsa(cl,c):
    for a in range(4):
        try:
            r=cl.get(f"https://brasilapi.com.br/api/cnpj/v1/{c}",timeout=20)
            if r.status_code==429: time.sleep(4+a*4); continue
            if r.status_code!=200: return None
            return r.json()
        except Exception: time.sleep(2)
    return None
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.icp_recheck(
        cnpj_basico varchar(8) PRIMARY KEY, cnpj14 text, situacao_viva text, decisor_atual text, recheck_em timestamptz DEFAULT now());""")
    # cnpj14 (matriz preferida) p/ cada ICP
    cur.execute("""
      SELECT DISTINCT ON (s.cnpj_basico) s.cnpj_basico,
             e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv AS cnpj14
      FROM (SELECT cnpj_basico FROM prospeccao.icp527_screen UNION SELECT cnpj_basico FROM prospeccao.icp_media_screen) s
      JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=s.cnpj_basico
      WHERE NOT EXISTS (SELECT 1 FROM prospeccao.icp_recheck r WHERE r.cnpj_basico=s.cnpj_basico)
      ORDER BY s.cnpj_basico, (e.identificador_matriz_filial='1') DESC""")
    rows=cur.fetchall()
    print(f"[re-check ao vivo de {len(rows)} ICP]", file=sys.stderr, flush=True)
    ativa=mortas=0
    with httpx.Client(headers={"User-Agent":"wins-agro/recheck"}) as cl:
        for i,r in enumerate(rows,1):
            d=qsa(cl, r["cnpj14"]); time.sleep(0.7)
            sit=dec=None
            if d:
                sit=d.get("descricao_situacao_cadastral")
                decis=[f"{(s.get('nome_socio') or '').strip()} ({(s.get('qualificacao_socio') or '').strip()})"
                       for s in (d.get("qsa") or []) if (s.get('nome_socio') or '').strip() and pessoa(s.get('nome_socio')) and any(q in (s.get('qualificacao_socio') or '') for q in QUALS)]
                dec=next((x for x in decis if 'dminist' in x or 'Presid' in x or 'Diret' in x), decis[0] if decis else None)
            if sit and 'ATIVA' in (sit or '').upper(): ativa+=1
            elif sit: mortas+=1
            cur.execute("INSERT INTO prospeccao.icp_recheck(cnpj_basico,cnpj14,situacao_viva,decisor_atual) VALUES(%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET situacao_viva=EXCLUDED.situacao_viva,decisor_atual=EXCLUDED.decisor_atual,recheck_em=now()",
                        (r["cnpj_basico"], r["cnpj14"], sit, dec))
            if i%50==0: print(f"  {i}/{len(rows)} | ativas {ativa} · não-ativas {mortas}", file=sys.stderr, flush=True)
    print(f"\n[FIM] {len(rows)} | ATIVAS {ativa} · não-ativas {mortas}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
