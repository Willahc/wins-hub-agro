-- Login por digital (WebAuthn/passkey): credenciais registradas.
-- O servidor guarda só a CHAVE PÚBLICA + contador; a biometria nunca sai do aparelho.
CREATE TABLE IF NOT EXISTS prospeccao.webauthn_credential (
  cred_id      text PRIMARY KEY,            -- base64url do credential id
  user_email   text NOT NULL,
  public_key   text NOT NULL,               -- base64url da chave pública (COSE)
  sign_count   bigint NOT NULL DEFAULT 0,   -- anti-clonagem (detecta replay)
  transports   text,
  label        text,
  created_at   timestamptz DEFAULT now(),
  last_used_at timestamptz
);
GRANT SELECT, INSERT, UPDATE, DELETE ON prospeccao.webauthn_credential TO wins_app;
