(() => {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  const section = document.createElement('div');
  section.className = 'section';
  section.innerHTML = `
    <h2>Apple Authentication</h2>
    <div id="auth-status" class="auth-status">Loading authentication status…</div>
    <p class="auth-help" title="Apple may invalidate a session before the estimated date.">The countdown is an estimate. Apple can expire a session earlier.</p>
    <button id="auth-open" class="auth-button" type="button">Re-authenticate</button>`;
  sidebar.appendChild(section);

  const modal = document.createElement('div');
  modal.className = 'auth-modal';
  modal.innerHTML = `
    <div class="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <h2 id="auth-title">Renew Apple session</h2>
      <p id="auth-step">Enter the WebUI administrator password and your Apple ID password.</p>
      <label><span id="auth-admin-label">WebUI administrator password</span><input id="auth-admin" type="password" autocomplete="current-password" minlength="12"></label>
      <label id="auth-admin-confirm-row" hidden>Confirm new administrator password<input id="auth-admin-confirm" type="password" autocomplete="new-password" minlength="12"></label>
      <label id="apple-password-row">Apple ID password<input id="auth-password" type="password" autocomplete="off"></label>
      <label id="auth-code-row" hidden>Apple verification code<input id="auth-code" inputmode="numeric" autocomplete="one-time-code" maxlength="8"></label>
      <p id="auth-error" class="auth-error"></p>
      <p class="auth-security">Apple passwords and verification codes are sent only to this server and are not stored. During first-run setup, the administrator password is stored only as a salted hash in the persistent session directory. Never expose this WebUI directly to the internet; use HTTPS, a VPN, or an authenticated reverse proxy.</p>
      <div class="auth-actions"><button id="auth-cancel" class="secondary" type="button">Cancel</button><button id="auth-submit" type="button">Start</button></div>
    </div>`;
  document.body.appendChild(modal);

  let waitingForCode = false;
  let setupRequired = false;
  const statusEl = document.getElementById('auth-status');
  const openButton = document.getElementById('auth-open');
  const submitButton = document.getElementById('auth-submit');
  const errorEl = document.getElementById('auth-error');

  async function loadStatus() {
    const response = await fetch('/api/auth/status', {cache: 'no-store'});
    const status = await response.json();
    const days = status.remaining_days;
    const text = status.state === 'valid' ? `Session active · about ${days} days remaining`
      : status.state === 'warning' ? `Renew soon · about ${days} days remaining`
      : status.state === 'expired' ? 'Estimated session lifetime reached'
      : status.state === 'session_present' ? 'Session found · authentication date unknown'
      : 'No session found';
    statusEl.replaceChildren();
    const row = document.createElement('div');
    row.className = 'auth-row';
    const dot = document.createElement('span');
    dot.className = `auth-dot ${status.state}`;
    const strong = document.createElement('strong');
    strong.textContent = text;
    const username = document.createElement('div');
    username.textContent = status.username_masked || '';
    row.append(dot, strong);
    statusEl.append(row, username);
    setupRequired = Boolean(status.setup_required);
    openButton.disabled = !status.web_auth_enabled;
    openButton.textContent = setupRequired ? 'Set up & re-authenticate' : 'Re-authenticate';
    openButton.title = status.web_auth_enabled ? '' : 'Web authentication was explicitly disabled';
    document.getElementById('auth-admin-label').textContent = setupRequired
      ? 'Create WebUI administrator password'
      : 'WebUI administrator password';
    document.getElementById('auth-admin-confirm-row').hidden = !setupRequired;
    document.getElementById('auth-admin').autocomplete = setupRequired ? 'new-password' : 'current-password';
  }

  function adminHeaders() {
    return {'Content-Type': 'application/json', 'X-Admin-Password': document.getElementById('auth-admin').value};
  }

  openButton.addEventListener('click', () => { modal.classList.add('visible'); errorEl.textContent = ''; });
  document.getElementById('auth-cancel').addEventListener('click', () => modal.classList.remove('visible'));

  submitButton.addEventListener('click', async () => {
    errorEl.textContent = '';
    submitButton.disabled = true;
    try {
      const endpoint = waitingForCode ? '/api/auth/verify' : '/api/auth/start';
      const adminValue = document.getElementById('auth-admin').value;
      if (!waitingForCode && setupRequired) {
        const confirmation = document.getElementById('auth-admin-confirm').value;
        if (adminValue.length < 12) throw new Error('Use at least 12 characters for the administrator password');
        if (adminValue !== confirmation) throw new Error('The administrator passwords do not match');
      }
      const body = waitingForCode
        ? {code: document.getElementById('auth-code').value.trim()}
        : {password: document.getElementById('auth-password').value, admin_password: adminValue};
      const response = await fetch(endpoint, {method: 'POST', headers: adminHeaders(), body: JSON.stringify(body)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Authentication failed');
      if (result.requires_2fa) {
        waitingForCode = true;
        document.getElementById('auth-code-row').hidden = false;
        document.getElementById('apple-password-row').hidden = true;
        document.getElementById('auth-step').textContent = 'Enter the new code shown on your trusted Apple device.';
        submitButton.textContent = 'Verify code';
      } else {
        waitingForCode = false;
        modal.classList.remove('visible');
        document.getElementById('auth-password').value = '';
        document.getElementById('auth-code').value = '';
        document.getElementById('auth-admin').value = '';
        document.getElementById('auth-admin-confirm').value = '';
        await loadStatus();
      }
    } catch (error) {
      errorEl.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });

  loadStatus().catch(() => { statusEl.textContent = 'Authentication status unavailable'; });
  setInterval(loadStatus, 60000);
})();
