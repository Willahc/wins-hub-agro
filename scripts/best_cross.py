"""Melhor bezerro EQUILIBRADO a partir dos dados (touro × matriz Nelore).
Cria = média dos pais por característica; equilíbrio = maximizar o traço mais fraco
da cria (normalizado contra a população), excluindo parentesco."""
import psycopg2, os, sys
DB = dict(host=os.getenv("DB_HOST", "db"), port=5432, dbname="wins_agro",
          user="postgres", password=os.getenv("POSTGRES_PASSWORD", ""))
TR = [(8, 'GPD/cresc'), (16, 'AOL/carcaça'), (12, 'PES/precoc'), (11, 'HP/fertil'), (18, 'MAR/marmoreio')]
cn = psycopg2.connect(**DB); cur = cn.cursor()

cur.execute("""
SELECT r.id, r.nome, r.registro, COALESCE(r.pai_registro,''), COALESCE(r.mae_registro,''),
       COALESCE(r.avo_materno_registro,''),
       MAX(CASE WHEN a.caracteristica_id=8 THEN a.valor END),
       MAX(CASE WHEN a.caracteristica_id=16 THEN a.valor END),
       MAX(CASE WHEN a.caracteristica_id=12 THEN a.valor END),
       MAX(CASE WHEN a.caracteristica_id=11 THEN a.valor END),
       MAX(CASE WHEN a.caracteristica_id=18 THEN a.valor END),
       MAX(CASE WHEN a.caracteristica_id=20 THEN a.valor END)
FROM mercado.reprodutor r JOIN mercado.avaliacao a ON a.reprodutor_id=r.id
WHERE r.raca_id=1 AND r.sexo='M' AND a.caracteristica_id IN (8,16,12,11,18,20)
GROUP BY r.id
HAVING count(*) FILTER (WHERE a.caracteristica_id IN (8,16,12,11,18))=5
""")
T = []
for r in cur.fetchall():
    T.append(dict(id=r[0], nome=r[1], reg=r[2], pai=r[3], mae=r[4], avo=r[5],
                  v=[float(r[6]), float(r[7]), float(r[8]), float(r[9]), float(r[10])],
                  iqgg=float(r[11]) if r[11] is not None else None))
mins = [min(t['v'][i] for t in T) for i in range(5)]
maxs = [max(t['v'][i] for t in T) for i in range(5)]
def nrm(v): return [max(0, min(1, (v[i]-mins[i])/(maxs[i]-mins[i]))) if maxs[i] > mins[i] else .5 for i in range(5)]
for t in T:
    t['n'] = nrm(t['v']); t['bal'] = min(t['n'])
T.sort(key=lambda t: (t['bal'], sum(t['n'])), reverse=True)
Ttop = T[:600]
print(f"touros: {len(T)} | escala min..max:", [f'{mins[i]:.1f}..{maxs[i]:.1f}' for i in range(5)], flush=True)

cur.execute("""
SELECT dam.id, dam.nome, dam.registro, COALESCE(dam.pai_registro,''), COALESCE(dam.mae_registro,''),
       COALESCE(dam.avo_materno_registro,''), count(DISTINCT f.id),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=8),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=16),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=12),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=11),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=18),
       AVG(a.valor) FILTER (WHERE a.caracteristica_id=20)
FROM mercado.reprodutor dam
JOIN mercado.reprodutor f ON f.mae_id=dam.id
JOIN mercado.avaliacao a ON a.reprodutor_id=f.id AND a.caracteristica_id IN (8,16,12,11,18,20)
WHERE dam.sexo='F'
GROUP BY dam.id HAVING count(DISTINCT f.id)>=5
""")
V = []
for r in cur.fetchall():
    vals = [r[7], r[8], r[9], r[10], r[11]]
    if any(x is None for x in vals):
        continue
    v = dict(id=r[0], nome=r[1], reg=r[2], pai=r[3], mae=r[4], avo=r[5], nf=r[6],
             v=[float(x) for x in vals], iqgg=float(r[12]) if r[12] is not None else None)
    v['n'] = nrm(v['v']); V.append(v)
print(f"matrizes c/ perfil completo (>=5 filhos): {len(V)}", flush=True)

def parente(t, v):
    if t['mae'] and t['mae'] == v['reg']: return True
    if v['pai'] and t['reg'] == v['pai']: return True
    if t['pai'] and v['pai'] and t['pai'] == v['pai']: return True
    if v['pai'] and t['avo'] == v['pai']: return True
    return False

best = []
for t in Ttop:
    for v in V:
        if parente(t, v): continue
        calf = [0.5*(t['n'][i]+v['n'][i]) for i in range(5)]
        best.append((min(calf), sum(calf)/5, t, v, calf))
best.sort(key=lambda x: (x[0], x[1]), reverse=True)
print("\n=== TOP 6 cruzamentos por EQUILÍBRIO (maior 'pior traço' da cria) ===", flush=True)
for bal, mean, t, v, calf in best[:6]:
    print(f"\n# {t['nome'][:28]} (IQGg {t['iqgg']:.0f}) x {v['nome'][:24]} (mae, {v['nf']} filhos, IQGg {v['iqgg']:.0f})")
    print(f"  equilibrio(min)={bal:.2f}  media={mean:.2f}")
    for i, (cid, nm) in enumerate(TR):
        print(f"    {nm:14} cria={0.5*(t['v'][i]+v['v'][i]):7.2f}  norm={calf[i]:.2f}  [touro {t['v'][i]:.1f} | vaca {v['v'][i]:.1f}]")
cn.close()
