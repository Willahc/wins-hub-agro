#!/usr/bin/env python3
"""Enrolamento do MFA (TOTP / Google Authenticator) da Mari.
Gera um segredo NOVO, mostra o QR pra escanear e a linha pra colar no .env.
O segredo é gerado AQUI no servidor (não trafega pelo chat). Depois de escanear:
  1) cole  MFA_TOTP_SECRET=<segredo>  no /root/wins_agro_v1/.env
  2) redeploy do api (gotcha #1)  →  o login passa a exigir o código de 6 dígitos.
Uso: docker exec -i wins_agro_v1_api_1 python - < scripts/setup_mfa.py
"""
import os
import pyotp
import qrcode

EMAIL = os.getenv("MARI_EMAIL", "mari@winshubagro.cloud")
ISSUER = "WiNS Hub Agro"

secret = pyotp.random_base32()
uri = pyotp.totp.TOTP(secret).provisioning_uri(name=EMAIL, issuer_name=ISSUER)

print("\n" + "=" * 60)
print("  ENROLAMENTO MFA — escaneie o QR no Google Authenticator")
print("=" * 60)
qr = qrcode.QRCode(border=1)
qr.add_data(uri)
qr.make(fit=True)
qr.print_ascii(invert=True)   # QR em ASCII no terminal
print("Se o QR não escanear, digite a chave manualmente no app:")
print("  Chave:", secret)
print("  Conta:", EMAIL, "| Emissor:", ISSUER)
print("\nDepois de escanear, ATIVE o 2º fator:")
print("  1) adicione esta linha ao .env:")
print(f"     MFA_TOTP_SECRET={secret}")
print("  2) redeploy do api (build + recriar container).")
print("  A partir daí o login pede senha + código de 6 dígitos.\n")
