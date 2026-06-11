"""Conectores para bancos de dados abertos (APIs públicas).

Fontes:
  - IBGE SIDRA  -> produção de leite e efetivo de rebanho bovino por UF/município
  - IBGE Localidades -> metadados de municípios
  - BrasilAPI   -> consulta CNPJ em tempo real (enriquecimento de lead)
  - Banco Central (SGS) -> indicadores (dólar)

Todas com cache em memória (TTL) porque são lentas e têm rate-limit.
"""
import time
import logging
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
    # NÃO cacheia falhas: uma indisponibilidade transitória da API externa não pode
    # ficar "grudada" pelo TTL (ex.: arroba None por 6h faz a IATF em lote gravar
    # snapshot ganho_cria=NULL permanente; CNPJ com timeout ficaria 24h dando erro).
    falhou = val is None or (isinstance(val, dict) and val.get("error"))
    # dict de sub-cotações (ex.: graos) com TODOS os valores None também é falha
    if isinstance(val, dict) and val and not val.get("error") and all(v is None for v in val.values()):
        falhou = True
    if not falhou:
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


def _html(url, timeout=20):
    r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "pt-BR",
    })
    r.raise_for_status()
    return r.text


def boi_gordo():
    """Indicador do Boi Gordo CEPEA-ESALQ/B3 (R$/@). O CEPEA bloqueia acesso direto
    (Cloudflare), então lemos o MESMO indicador republicado pela Notícias Agrícolas.
    Ancora no par data(dd/mm/aaaa)->valor da tabela de cotações (robusto a outros
    números na página)."""
    import re

    def extrair(html):
        m = re.search(r"(\d{2}/\d{2}/\d{4})[^0-9]{0,200}?(\d{3},\d{2})", html)
        if not m:
            return None, None
        v = _to_float(m.group(2).replace(".", "").replace(",", "."))
        if v and 150 <= v <= 800:   # faixa plausível p/ arroba do boi
            return v, m.group(1)
        return None, None

    def fetch():
        try:
            v, data = extrair(_html(
                "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo/"
                "boi-gordo-indicador-esalq-bmf"))
        except Exception:
            v, data = None, None
        if not v:
            return None
        return {
            "valor": v, "data": data, "unidade": "R$/@",
            "fonte": "Indicador ESALQ/B3 (Notícias Agrícolas)",
        }
    return _cached("boi_gordo", 6 * 3600, fetch)


def _cotacao_data_valor(url, lo, hi):
    """Extrai o par data(dd/mm/aaaa)->valor da tabela de cotações (robusto)."""
    import re
    html = _html(url)
    m = re.search(r"(\d{2}/\d{2}/\d{4})[^0-9]{0,200}?(\d{1,3}(?:\.\d{3})*,\d{2})", html)
    if not m:
        return None
    v = _to_float(m.group(2).replace(".", "").replace(",", "."))
    if v and lo <= v <= hi:
        return {"valor": v, "data": m.group(1)}
    return None


def leite_preco():
    """Preço do leite ao produtor (CEPEA, R$/litro, média Brasil) — via Notícias Agrícolas.
    Âncora na linha 'Brasil' da tabela de Preços ao Produtor."""
    import re

    def fetch():
        try:
            html = _html("https://www.noticiasagricolas.com.br/cotacoes/leite")
        except Exception:
            return None
        m = re.search(r"Brasil</td>\s*<td>(\d,\d{2,4})", html)
        if not m:
            return None
        v = _to_float(m.group(1).replace(",", "."))
        if not v or not (0.5 <= v <= 6):
            return None
        return {"valor": v, "unidade": "R$/litro",
                "fonte": "CEPEA Preços ao Produtor (Notícias Agrícolas)"}
    return _cached("leite_preco", 12 * 3600, fetch)


def graos():
    """Milho e soja (R$/saca) — Indicadores ESALQ via Notícias Agrícolas."""
    def fetch():
        out = {}
        try:
            out["milho"] = _cotacao_data_valor(
                "https://www.noticiasagricolas.com.br/cotacoes/milho", 30, 250)
        except Exception:
            out["milho"] = None
        try:
            out["soja"] = _cotacao_data_valor(
                "https://www.noticiasagricolas.com.br/cotacoes/soja", 80, 350)
        except Exception:
            out["soja"] = None
        return out
    return _cached("graos", 6 * 3600, fetch)


def indicadores():
    """Câmbio USD/BRL e Selic. O BCB SGS (api.bcb.gov.br) bloqueia/erra as
    requisições deste servidor (WAF -> HTML 'inválido' / 500), então o dólar vem
    da referência do BCE via Frankfurter: confiável, sem chave e já retorna o
    ÚLTIMO DIA ÚTIL no fim de semana (com a data), resolvendo o '—' de sáb/dom."""
    def fetch():
        out = {}
        try:
            d = _get_json("https://api.frankfurter.app/latest?from=USD&to=BRL", timeout=15)
            brl = (d.get("rates") or {}).get("BRL")
            iso = d.get("date") or ""                       # YYYY-MM-DD
            data_br = "/".join(reversed(iso.split("-"))) if iso else None
            out["dolar"] = ({"valor": _to_float(brl), "data": data_br,
                             "fonte": "USD/BRL ref. (BCE/Frankfurter)"} if brl else None)
        except Exception:
            out["dolar"] = None
        # Selic (BCB SGS) — best-effort; hoje não é exibida no painel.
        try:
            s = _get_json(f"{BCB}/bcdata.sgs.432/dados/ultimos/1?formato=json", timeout=10)
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
        except Exception:
            # não expõe str(e) (pode vazar URL/host do upstream); loga internamente
            logging.getLogger("uvicorn.error").warning("Falha ao consultar CNPJ", exc_info=True)
            return {"error": "Consulta de CNPJ indisponível no momento."}
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
