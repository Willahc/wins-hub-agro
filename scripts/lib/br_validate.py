"""
br_validate.py — helpers de validação/normalização BR, compartilhados pelos scripts
de enriquecimento. Troca regex/heurística caseira por libs maduras:

  - phonenumbers (port do libphonenumber do Google): parse/valida/formata e detecta
    MÓVEL vs FIXO — usado para saber o que é WhatsApp-capable.
  - validate-docbr: dígito verificador correto de CPF/CNPJ.
  - email-validator: sintaxe + (opcional) checagem de MX, antes do smtp_verify.

Sem efeito colateral: funções puras, retornam dicts. Importável tanto no host
(venv /root/.venv-wins-tools) quanto dentro do container app (adicionar as libs ao
requirements.txt — já incluídas).
"""
from __future__ import annotations
import phonenumbers
from phonenumbers import PhoneNumberType, NumberParseException, geocoder, carrier
from validate_docbr import CPF, CNPJ

_CPF = CPF()
_CNPJ = CNPJ()

# Tipos do libphonenumber considerados "móvel" (WhatsApp-capable no BR)
_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}

# rótulos legíveis para number_type()
_TIPO_LABEL = {
    PhoneNumberType.FIXED_LINE: "FIXO",
    PhoneNumberType.MOBILE: "MOVEL",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXO_OU_MOVEL",
    PhoneNumberType.TOLL_FREE: "TOLL_FREE",
    PhoneNumberType.VOIP: "VOIP",
    PhoneNumberType.UNKNOWN: "DESCONHECIDO",
}


def normaliza_telefone(raw: str, regiao: str = "BR") -> dict:
    """Normaliza um telefone BR. Retorna sempre um dict — nunca levanta.

    {valido, movel, e164, tipo, ddd, operadora, motivo}
    'movel' = True quando o número é (provavelmente) celular -> candidato a WhatsApp.
    """
    out = {"raw": raw, "valido": False, "movel": False, "e164": None,
           "tipo": None, "ddd": None, "operadora": None, "motivo": None}
    if not raw or not str(raw).strip():
        out["motivo"] = "vazio"
        return out
    s = str(raw).strip()
    try:
        # números crus da Receita vêm sem +55; tentamos com a região default
        num = phonenumbers.parse(s, regiao)
    except NumberParseException as e:
        out["motivo"] = f"parse_error:{e.error_type}"
        return out

    if not phonenumbers.is_possible_number(num):
        out["motivo"] = "impossivel"
        return out
    if not phonenumbers.is_valid_number(num):
        out["motivo"] = "invalido"
        return out

    tipo = phonenumbers.number_type(num)
    out.update(
        valido=True,
        movel=tipo in _MOBILE_TYPES,
        e164=phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
        tipo=_TIPO_LABEL.get(tipo, "DESCONHECIDO"),
        ddd=str(num.national_number)[:2] if num.national_number else None,
        operadora=carrier.name_for_number(num, "pt") or None,
        motivo="ok",
    )
    return out


def valida_cpf(doc: str) -> bool:
    return bool(doc) and _CPF.validate(str(doc))


def valida_cnpj(doc: str) -> bool:
    return bool(doc) and _CNPJ.validate(str(doc))


def normaliza_email(addr: str, checar_mx: bool = False) -> dict:
    """Valida sintaxe (e, se checar_mx, deliverabilidade via DNS MX).
    NÃO faz handshake SMTP — isso continua no smtp_verify.py.
    """
    out = {"raw": addr, "valido": False, "normalizado": None, "dominio": None, "motivo": None}
    if not addr or not str(addr).strip():
        out["motivo"] = "vazio"
        return out
    try:
        from email_validator import validate_email, EmailNotValidError
    except ImportError:
        out["motivo"] = "email_validator_ausente"
        return out
    try:
        info = validate_email(str(addr).strip(), check_deliverability=checar_mx)
        out.update(valido=True, normalizado=info.normalized,
                   dominio=info.domain, motivo="ok")
    except Exception as e:  # EmailNotValidError e erros de DNS
        out["motivo"] = str(e)[:120]
    return out


if __name__ == "__main__":
    # auto-teste rápido
    for t in ["5135613675", "11987654321", "(34) 99999-8888", "123", ""]:
        print(t, "->", normaliza_telefone(t))
    print("CPF 11144477735:", valida_cpf("11144477735"))
    print("CNPJ 21098855000177:", valida_cnpj("21098855000177"))
    print("email:", normaliza_email("fazenda.estreladoeste3@gmail.com"))
