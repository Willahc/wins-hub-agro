"""
NDVI de pastagem via Google Earth Engine (Sentinel-2) -> CSV de alertas de degradacao.

Engenharia de dados / GIS para o WiNS Agro. Para cada fazenda (poligono real OU centroide+area),
calcula o NDVI mediano recente, COMPARA com ~6 meses atras (perda de vigor) e classifica o estado
da pastagem. Saida CSV pronta pra casar com a base por CNPJ / codigo_car.

Fonte: COPERNICUS/S2_SR_HARMONIZED (Sentinel-2 Surface Reflectance, 10 m, gratuito via GEE).

3 melhorias sobre o brief original (importam em campo):
  1. Mascara de nuvem REAL por banda SCL + composite MEDIANO da janela (o filtro "<10% nuvem em
     30 dias" sozinho costuma devolver ZERO imagem no Centro-Oeste/Norte em epoca de chuva).
  2. Sinal de degradacao = QUEDA do NDVI vs 6 meses atras (o pitch da Mari: "perdeu vigor nos
     ultimos 6 meses"), nao so um corte absoluto — pasto recem-pastejado tambem da NDVI baixo.
  3. Saida chaveada por codigo_car/CNPJ pra casar com lead_demanda (coluna "Saude do Pasto").

Pre-requisitos (uma vez so):
    pip install earthengine-api pandas
    earthengine authenticate          # abre o navegador, loga no Google
    # + um projeto Google Cloud com a Earth Engine API habilitada (gratis p/ uso nao comercial)

Uso:
    python ndvi_pasto_gee.py                    # modo TESTE (1 poligono hardcoded)
    python ndvi_pasto_gee.py fazendas.geojson   # LOTE a partir de GeoJSON (geometria real do CAR)
    # integracao com o banco WiNS: ver fazendas_do_banco()
"""
import sys
import math
import datetime
import ee
import pandas as pd

# ----------------------------- Configuracao -----------------------------
PROJETO_GEE   = "seu-projeto-gee"   # <-- id do seu projeto Google Cloud com Earth Engine habilitado
DIAS_JANELA   = 60                  # janela do composite (dias). 60 da imagem limpa onde 30 falha.
MESES_ATRAS   = 6                   # comparacao temporal (perda de vigor)
NUVEM_MAX     = 20                  # % de nuvem max no pre-filtro da cena
ESCALA_M      = 10                  # resolucao do reduceRegion (m) — NDVI do S2 = 10 m
NDVI_SAUDAVEL = 0.5                 # regra de negocio (Mari): >=0.5 saudavel
NDVI_DEGRAD   = 0.4                 #                          <0.4  degradacao
DELTA_ALERTA  = -0.10              # queda de NDVI >= 0,10 vs 6 meses = mancha de degradacao
SAIDA_CSV     = "alertas_pastagem.csv"

# classes da banda SCL (Scene Classification) a mascarar:
# 3=sombra de nuvem, 8=nuvem media, 9=nuvem alta, 10=cirrus, 11=neve/gelo
SCL_RUINS = [3, 8, 9, 10, 11]


def inicializar():
    """Autentica/inicializa o GEE. Requer 'earthengine authenticate' previo."""
    try:
        ee.Initialize(project=PROJETO_GEE)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJETO_GEE)


def _mascara_nuvem(img):
    """Zera pixels de nuvem/sombra/cirrus pela banda SCL (1=bom, 0=ruim)."""
    scl = img.select("SCL")
    mask = scl.remap(SCL_RUINS, [0] * len(SCL_RUINS), 1)
    return img.updateMask(mask)


def _ndvi(img):
    """NDVI = (B8 NIR - B4 Vermelho) / (B8 + B4)."""
    return img.normalizedDifference(["B8", "B4"]).rename("NDVI")


def _composite_ndvi(geom, data_fim, dias):
    """NDVI mediano (composite com mascara de nuvem) na janela [data_fim - dias, data_fim]."""
    inicio = data_fim.advance(-dias, "day")
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(geom)
           .filterDate(inicio, data_fim)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", NUVEM_MAX))
           .map(_mascara_nuvem)
           .map(_ndvi))
    return col.select("NDVI").median(), col.size()


def ndvi_medio(geom, data_fim, dias):
    """Valor medio do NDVI no poligono e nº de imagens. (None, 0) se nao houver imagem limpa."""
    img, n = _composite_ndvi(geom, data_fim, dias)
    val = img.reduceRegion(ee.Reducer.mean(), geom, ESCALA_M, maxPixels=int(1e9)).get("NDVI")
    info = ee.Dictionary({"ndvi": val, "n": n}).getInfo()
    ndvi = round(info["ndvi"], 3) if info["ndvi"] is not None else None
    return ndvi, info["n"]


def classificar(ndvi, delta):
    """Regra de negocio: estado da pastagem."""
    if ndvi is None:
        return "SEM IMAGEM (nuvem / sem cobertura no periodo)"
    if delta is not None and delta <= DELTA_ALERTA:
        return "MANCHA DE DEGRADACAO (perda de vigor nos ultimos 6m)"
    if ndvi >= NDVI_SAUDAVEL:
        return "Vegetacao saudavel"
    if ndvi < NDVI_DEGRAD:
        return "Mancha de degradacao detectada"
    return "Atencao (vigor intermediario)"


def geom_de_centroide(lat, lon, area_ha):
    """Aproxima a fazenda por um CIRCULO de mesma area ao redor do centroide.
    Fallback p/ quando nao se tem o poligono real do CAR (so centroide+area)."""
    area_m2 = max(float(area_ha or 1), 1) * 10000.0
    raio = math.sqrt(area_m2 / math.pi)
    return ee.Geometry.Point([lon, lat]).buffer(raio)


def analisar_fazenda(fz):
    """fz = dict {id, cnpj, codigo_car, geom(ee.Geometry)} -> linha de resultado."""
    hoje = ee.Date(datetime.date.today().isoformat())
    ndvi_atual, n_at = ndvi_medio(fz["geom"], hoje, DIAS_JANELA)
    ndvi_passado, _ = ndvi_medio(fz["geom"], hoje.advance(-MESES_ATRAS, "month"), DIAS_JANELA)
    delta = (round(ndvi_atual - ndvi_passado, 3)
             if (ndvi_atual is not None and ndvi_passado is not None) else None)
    return {
        "id_fazenda": fz.get("id"),
        "cnpj": fz.get("cnpj"),
        "codigo_car": fz.get("codigo_car"),
        "data": datetime.date.today().isoformat(),
        "ndvi_atual": ndvi_atual,
        "ndvi_6m_atras": ndvi_passado,
        "delta_6m": delta,
        "n_imagens": n_at,
        "status_pasto": classificar(ndvi_atual, delta),
    }


# ------------------------------- Entradas (ROI) -------------------------------
def fazendas_teste():
    """Modo TESTE: 1 poligono hardcoded (simula uma propriedade em MT)."""
    poly = ee.Geometry.Polygon([[
        [-55.10, -15.60], [-55.05, -15.60], [-55.05, -15.55], [-55.10, -15.55], [-55.10, -15.60],
    ]])
    return [{"id": "FAZ_TESTE", "cnpj": None, "codigo_car": None, "geom": poly}]


def fazendas_de_geojson(caminho):
    """Lote a partir de um GeoJSON FeatureCollection com a GEOMETRIA REAL (recomendado).
    Cada feature: properties {id|codigo_car, cnpj} + geometry (Polygon)."""
    import json
    fc = json.load(open(caminho, encoding="utf-8"))
    out = []
    for ft in fc["features"]:
        p = ft.get("properties", {})
        out.append({
            "id": p.get("id") or p.get("codigo_car"),
            "cnpj": p.get("cnpj"),
            "codigo_car": p.get("codigo_car"),
            "geom": ee.Geometry(ft["geometry"]),
        })
    return out


def fazendas_do_banco(limite=50):
    """Le centroide+area do banco WiNS (prospeccao.imovel_rural) e aproxima por circulo.
    Requer psycopg2. ATENCAO: imovel_rural NAO tem dono (CPF/CNPJ vazio no CAR publico),
    entao a saida chaveia por codigo_car — ver a ressalva de integracao no fim do arquivo."""
    import os
    import psycopg2
    cn = psycopg2.connect(host=os.getenv("DB_HOST", "db"), dbname=os.getenv("POSTGRES_DB", "wins_agro"),
                          user=os.getenv("POSTGRES_USER", "postgres"),
                          password=os.getenv("POSTGRES_PASSWORD", ""))
    cur = cn.cursor()
    cur.execute("""SELECT codigo_car, cpf_cnpj, latitude, longitude, area_total_ha
                   FROM prospeccao.imovel_rural
                   WHERE latitude IS NOT NULL AND area_total_ha > 0
                   ORDER BY area_total_ha DESC
                   LIMIT %s""", (limite,))
    out = []
    for car, doc, lat, lon, area in cur.fetchall():
        out.append({"id": car, "cnpj": doc, "codigo_car": car,
                    "geom": geom_de_centroide(float(lat), float(lon), area)})
    cur.close()
    cn.close()
    return out


def main():
    inicializar()
    if len(sys.argv) > 1:
        fazendas = fazendas_de_geojson(sys.argv[1])
    else:
        fazendas = fazendas_teste()
    print(f"Analisando {len(fazendas)} fazenda(s)...")
    linhas = []
    for i, fz in enumerate(fazendas, 1):
        try:
            r = analisar_fazenda(fz)
        except Exception as e:
            r = {"id_fazenda": fz.get("id"), "status_pasto": f"ERRO: {e}"}
        linhas.append(r)
        print(f"  [{i}/{len(fazendas)}] {r.get('id_fazenda')}: {r.get('status_pasto')} "
              f"(NDVI {r.get('ndvi_atual')}, delta {r.get('delta_6m')})")
    df = pd.DataFrame(linhas)
    df.to_csv(SAIDA_CSV, index=False, encoding="utf-8")
    print(f"\nOK -> {SAIDA_CSV} ({len(df)} linhas)")


if __name__ == "__main__":
    main()
