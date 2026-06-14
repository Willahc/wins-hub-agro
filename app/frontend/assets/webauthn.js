// WiNS — login por digital (WebAuthn / passkey). Sem dependências externas (CSP 'self').
// A biometria fica no aparelho; o servidor só lida com chave pública + assinatura.
(function () {
  const b64urlToBuf = (s) => {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    const pad = '='.repeat((4 - (s.length % 4)) % 4);
    const bin = atob(s + pad);
    const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return u.buffer;
  };
  const bufToB64url = (b) => {
    const u = new Uint8Array(b);
    let s = '';
    for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  };
  async function post(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }

  window.winsPasskeySupported = () => !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create);
  window.winsPasskeyAvailable = async () => {
    try { return !!(await fetch('/api/webauthn/available').then((r) => r.json())).available; }
    catch (e) { return false; }
  };

  // registra a digital DESTE aparelho (exige sessão ativa)
  window.winsPasskeyRegister = async (label) => {
    if (!window.winsPasskeySupported()) throw new Error('Aparelho/navegador sem suporte a digital.');
    const opt = await post('/api/webauthn/register/begin');
    opt.challenge = b64urlToBuf(opt.challenge);
    opt.user.id = b64urlToBuf(opt.user.id);
    (opt.excludeCredentials || []).forEach((c) => { c.id = b64urlToBuf(c.id); });
    const cred = await navigator.credentials.create({ publicKey: opt });
    const r = cred.response;
    return await post('/api/webauthn/register/complete', {
      id: cred.id, rawId: bufToB64url(cred.rawId), type: cred.type,
      response: {
        clientDataJSON: bufToB64url(r.clientDataJSON),
        attestationObject: bufToB64url(r.attestationObject),
        transports: r.getTransports ? r.getTransports() : [],
      },
      clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
      _label: label || null,
    });
  };

  // login por digital -> emite a sessão (mesmo cookie do login por senha)
  window.winsPasskeyLogin = async () => {
    if (!window.winsPasskeySupported()) throw new Error('Sem suporte a digital.');
    const opt = await post('/api/webauthn/login/begin');
    opt.challenge = b64urlToBuf(opt.challenge);
    (opt.allowCredentials || []).forEach((c) => { c.id = b64urlToBuf(c.id); });
    const cred = await navigator.credentials.get({ publicKey: opt });
    const r = cred.response;
    return await post('/api/webauthn/login/complete', {
      id: cred.id, rawId: bufToB64url(cred.rawId), type: cred.type,
      response: {
        clientDataJSON: bufToB64url(r.clientDataJSON),
        authenticatorData: bufToB64url(r.authenticatorData),
        signature: bufToB64url(r.signature),
        userHandle: r.userHandle ? bufToB64url(r.userHandle) : null,
      },
      clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    });
  };
})();
