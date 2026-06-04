"""Conectores para bancos de dados abertos (APIs públicas).

Fontes:
  - IBGE SIDRA  -> produção de leite e efetivo de rebanho bovino por UF/município
  - IBGE Localidades -> metadados de municípios
  - BrasilAPI   -> consulta CNPJ em tempo real (enriquecimento de lead)
  - Banco Central (SGS) -> indicadores (dólar)

Todas com cache em memória (TTL) porque são lentas e têm rate-limit.
"""
import time
import httpx

SIDRA = "https://apisidra.ibge.gov.br/values"
BRASILAPI = "https://brasilapi.com.br/api"
BCB = "https://api.bcb.gov.br/dados/serie"
HEADERS = {"User-Agent": "WiNSHubAgro/1.0 (+https://winshubagro.cloud)"}

# IBGE devolve o nome completo da UF; mapeamos para a sigla usada no resto do app.
UF_SIGLA = {
    "Rondônia": "RO", "Acre": "AC", "Amazonas": "AM", "Roraima": "RR", "Pará": "PA",
    "Amapá": "AP", "Tocantins": "TO", "Maranhão": "MA", "Piauí": "PI", "Ceará": "CE",
    "Rio Grande do Norte": "RN", "Paraíba": "PB", "Pernambuco": "PE", "Alagoas": "AL",
    "Sergipe": "SE", "Bahia": "BA", "Minas Gerais": "MG", "Espírito Santo": "ES",
    "Rio de Janeiro": "RJ", "São Paulo": "SP", "Paraná": "PR", "Santa Catarina": "SC",
    "Rio Grande do Sul": "RS", "Mato Grosso do Sul": "MS", "Mato Grosso": "MT",
    "Goiás": "GO", "Distrito Federal": "DF",
}

_CACHE = {}


def _cached(key, ttl, fn):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and (now - hit[0]) < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (now, val)
    return val


def _get_json(url, timeout=25):
    r = httpx.get(url, timeout=timeout, headers=HEADERS, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sidra_por_uf(key, url, valor_label, ttl=86400):
    def fetch():
        data = _get_json(url)
        out = []
        for r in data[1:]:  # primeira linha é o cabeçalho descritivo
            nome = r.get("D1N")
            out.append({
                "uf": nome,
                "uf_sigla": UF_SIGLA.get(nome),
                valor_label: _to_float(r.get("V")),
                "ano": r.get("D3N"),
                "unidade": r.get("MN"),
            })
        out = [o for o in out if o.get(valor_label) is not None]
        out.sort(key=lambda o: o[valor_label], reverse=True)
        return out
    return _cached(key, ttl, fetch)


def producao_leite_uf():
    """IBGE/SIDRA t74 v106 c80/2682 — produção de leite (mil litros) por UF."""
    return _sidra_por_uf(
        "leite_uf",
        f"{SIDRA}/t/74/n3/all/v/106/p/last/c80/2682",
        "leite_mil_litros",
    )


def rebanho_bovino_uf():
    """IBGE/SIDRA t3939 v105 c79/2670 — efetivo de bovinos (cabeças) por UF."""
    return _sidra_por_uf(
        "rebanho_uf",
        f"{SIDRA}/t/3939/n3/all/v/105/p/last/c79/2670",
        "bovinos",
    )


def abate_bovino_uf():
    """IBGE/SIDRA t1092 — abate de bovinos por UF (último trimestre): cabeças e peso de carcaça."""
    def fetch():
        # v284 = animais abatidos (cabeças); v285 = peso total das carcaças (kg)
        url = (f"{SIDRA}/t/1092/n3/all/v/284,285/p/last"
               "/c12716/115236/c18/992/c12529/118225")
        data = _get_json(url)
        por_uf = {}
        periodo = None
        for r in data[1:]:
            nome = r.get("D1N")
            periodo = r.get("D3N")
            var = r.get("D2C")  # 284 ou 285
            d = por_uf.setdefault(nome, {"uf": nome, "uf_sigla": UF_SIGLA.get(nome)})
            if var == "284":
                d["cabecas"] = _to_float(r.get("V"))
            elif var == "285":
                d["peso_carcaca_kg"] = _to_float(r.get("V"))
        out = [v for v in por_uf.values() if v.get("cabecas")]
        out.sort(key=lambda o: o.get("cabecas") or 0, reverse=True)
        for o in out:
            o["periodo"] = periodo
        return out
    return _cached("abate_uf", 86400, fetch)


def producao_leite_municipios():
    """IBGE/SIDRA t74 n6 — produção de leite por município (mil litros) com código IBGE."""
    def fetch():
        data = _get_json(f"{SIDRA}/t/74/n6/all/v/106/p/last/c80/2682", timeout=40)
        out = []
        for r in data[1:]:
            litros = _to_float(r.get("V"))
            if litros is None or litros <= 0:
                continue
            out.append({
                "codigo_ibge": r.get("D1C"),
                "nome": r.get("D1N"),
                "leite_mil_litros": litros,
                "ano": r.get("D3N"),
            })
        return out
    return _cached("leite_mun", 86400, fetch)


def valor_producao_municipios():
    """IBGE/SIDRA t74 n6 v215 c80/0 — valor da produção animal por município (Mil Reais)."""
    def fetch():
        data = _get_json(f"{SIDRA}/t/74/n6/all/v/215/p/last/c80/0", timeout=40)
        out = []
        for r in data[1:]:
            val = _to_float(r.get("V"))
            if val is None or val <= 0:
                continue
            out.append({
                "codigo_ibge": r.get("D1C"),
                "nome": r.get("D1N"),
                "valor_mil_reais": val,
                "ano": r.get("D3N"),
            })
        return out
    return _cached("valor_mun", 86400, fetch)


def indicadores():
    """Banco Central (SGS): dólar comercial (série 1) e Selic meta (série 432)."""
    def fetch():
        out = {}
        try:
            d = _get_json(f"{BCB}/bcdata.sgs.1/dados/ultimos/1?formato=json", timeout=15)
            out["dolar"] = {"valor": _to_float(d[-1]["valor"]), "data": d[-1]["data"]}
        except Exception:
            out["dolar"] = None
        try:
            s = _get_json(f"{BCB}/bcdata.sgs.432/dados/ultimos/1?formato=json", timeout=15)
            out["selic"] = {"valor": _to_float(s[-1]["valor"]), "data": s[-1]["data"]}
        except Exception:
            out["selic"] = None
        return out
    return _cached("indicadores", 3600, fetch)


def cnpj(numero):
    """BrasilAPI: consulta CNPJ (situação, sócios, capital). numero = só dígitos."""
    num = "".join(ch for ch in str(numero) if ch.isdigit())
    if len(num) != 14:
        return {"error": "CNPJ inválido (precisa de 14 dígitos)"}

    def fetch():
        try:
            d = _get_json(f"{BRASILAPI}/cnpj/v1/{num}", timeout=15)
        except httpx.HTTPStatusError as e:
            return {"error": f"CNPJ não encontrado ({e.response.status_code})"}
        except Exception as e:
            return {"error": str(e)}
        socios = [
            {"nome": s.get("nome_socio"), "qualificacao": s.get("qualificacao_socio")}
            for s in (d.get("qsa") or [])
        ]
        return {
            "razao_social": d.get("razao_social"),
            "nome_fantasia": d.get("nome_fantasia"),
            "situacao": d.get("descricao_situacao_cadastral") or d.get("situacao_cadastral"),
            "capital_social": d.get("capital_social"),
            "porte": d.get("porte"),
            "cnae": d.get("cnae_fiscal_descricao"),
            "municipio": d.get("municipio"),
            "uf": d.get("uf"),
            "telefone": d.get("ddd_telefone_1"),
            "email": d.get("email"),
            "abertura": d.get("data_inicio_atividade"),
            "socios": socios,
        }
    return _cached(f"cnpj_{num}", 86400, fetch)
