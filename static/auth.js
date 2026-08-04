(() => {
  const host = document.getElementById("auth-settings-host");
  if (!host) return;

  host.innerHTML = `
    <div class="settings-card-heading"><span class="settings-icon">◉</span><div><h3>Apple authentication</h3><p>Renew the Apple session without opening a container console.</p></div></div>
    <div class="auth-settings-body">
      <div><div id="auth-status" class="auth-status">Loading authentication status…</div>
      <p class="auth-help" title="Apple may invalidate a session before the estimated date.">The countdown is an estimate; a successful poll is authoritative.</p></div>
      <button id="auth-open" class="button primary auth-button" type="button">Re-authenticate</button>
    </div>`;

  const modal = document.createElement("div");
  modal.className = "auth-modal";
  modal.innerHTML = `
    <div class="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <h2 id="auth-title">Renew Apple session</h2>
      <p id="auth-step">Enter the WebUI administrator password and your Apple ID password.</p>
      <div class="auth-identity" aria-live="polite">
        <span>Apple ID used for Find My</span>
        <strong id="auth-current-identity">Loading…</strong>
      </div>
      <div id="apple-username-row" class="auth-field" hidden>
        <label for="auth-username">Apple ID email address</label>
        <input id="auth-username" type="email" inputmode="email" autocomplete="username" placeholder="name@example.com">
        <small>Enter the email address you use to sign in to your Apple Account.</small>
      </div>
      <div class="auth-field">
        <label id="auth-admin-label" for="auth-admin">WebUI administrator password</label>
        <div class="auth-password-control">
          <input id="auth-admin" type="password" autocomplete="current-password">
          <button class="password-toggle" type="button" data-password-target="auth-admin" aria-label="Show WebUI administrator password" aria-pressed="false">Show</button>
        </div>
      </div>
      <div id="auth-admin-confirm-row" class="auth-field" hidden>
        <label for="auth-admin-confirm">Confirm new administrator password</label>
        <div class="auth-password-control">
          <input id="auth-admin-confirm" type="password" autocomplete="new-password">
          <button class="password-toggle" type="button" data-password-target="auth-admin-confirm" aria-label="Show administrator password confirmation" aria-pressed="false">Show</button>
        </div>
      </div>
      <div id="weak-password-warning" class="auth-warning" hidden>
        <strong>Security warning: this administrator password is weak.</strong>
        <p>A weak password makes it easier to access your private location history. At least 12 characters are strongly recommended.</p>
        <label><input id="weak-warning-accept" type="checkbox"> I understand that this password is not recommended and may reduce security.</label>
        <label><input id="weak-warning-confirm" type="checkbox"> I confirm again that I deliberately want to use this weak password.</label>
      </div>
      <div id="apple-password-row" class="auth-field">
        <label id="apple-password-label" for="auth-password">Password for this Apple ID</label>
        <div class="auth-password-control">
          <input id="auth-password" type="password" autocomplete="current-password">
          <button class="password-toggle" type="button" data-password-target="auth-password" aria-label="Show Apple ID password" aria-pressed="false">Show</button>
        </div>
        <small id="apple-password-help">This means your Apple Account password — not the WebUI password.</small>
      </div>
      <div id="auth-code-row" class="auth-field" hidden><label for="auth-code">Apple verification code</label><input id="auth-code" inputmode="numeric" autocomplete="one-time-code" maxlength="8"></div>
      <p id="auth-error" class="auth-error"></p>
      <details class="auth-security">
        <summary>Security and storage details</summary>
        <p>Apple passwords and verification codes are sent only to this server and are not stored. During first-run setup, the administrator password is stored only as a salted hash in the persistent session directory. Never expose this WebUI directly to the internet; use HTTPS, a VPN, or an authenticated reverse proxy.</p>
      </details>
      <div class="auth-actions"><button id="auth-cancel" class="secondary" type="button">Cancel</button><button id="auth-submit" type="button">Start</button></div>
    </div>`;
  document.body.appendChild(modal);

  let waitingForCode = false;
  let setupRequired = false;
  let usernameConfigured = false;
  let maskedUsername = "";
  const statusEl = document.getElementById("auth-status");
  const openButton = document.getElementById("auth-open");
  const submitButton = document.getElementById("auth-submit");
  const errorEl = document.getElementById("auth-error");

  async function loadStatus() {
    const response = await fetch("/api/auth/status", { cache: "no-store" });
    const status = await response.json();
    const days = status.remaining_days;
    const text =
      status.state === "valid"
        ? `Session active · about ${days} days remaining`
        : status.state === "warning"
          ? `Renew soon · about ${days} days remaining`
          : status.state === "expired"
            ? "Estimated session lifetime reached"
            : status.state === "session_present"
              ? "Session found · authentication date unknown"
              : "No session found";
    statusEl.replaceChildren();
    const row = document.createElement("div");
    row.className = "auth-row";
    const dot = document.createElement("span");
    dot.className = `auth-dot ${status.state}`;
    const strong = document.createElement("strong");
    strong.textContent = text;
    const username = document.createElement("div");
    username.textContent = status.username_masked || "";
    row.append(dot, strong);
    statusEl.append(row, username);
    setupRequired = Boolean(status.setup_required);
    usernameConfigured = Boolean(status.username_configured);
    maskedUsername = status.username_masked || "";
    document.getElementById("auth-current-identity").textContent =
      maskedUsername ? maskedUsername : "No Apple ID saved yet";
    openButton.disabled = !status.web_auth_enabled;
    openButton.textContent = setupRequired
      ? "Set up & re-authenticate"
      : "Re-authenticate";
    openButton.title = status.web_auth_enabled
      ? ""
      : "Web authentication was explicitly disabled";
    document.getElementById("auth-admin-label").textContent = setupRequired
      ? "Create WebUI administrator password"
      : "WebUI administrator password";
    document.getElementById("auth-admin-confirm-row").hidden = !setupRequired;
    document.getElementById("apple-username-row").hidden =
      usernameConfigured && !setupRequired;
    document.getElementById("auth-admin").autocomplete = setupRequired
      ? "new-password"
      : "current-password";
    document.getElementById("auth-title").textContent = setupRequired
      ? "Set up Apple access"
      : "Renew Apple session";
    document.getElementById("auth-step").textContent = setupRequired
      ? "Protect this WebUI first, then connect the Apple ID you use for Find My."
      : `Unlock the WebUI, then renew the Apple session for ${maskedUsername || "the saved Apple ID"}.`;
    document.getElementById("apple-password-label").textContent = maskedUsername
      ? `Password for ${maskedUsername}`
      : "Password for the Apple ID above";
    updateWeakPasswordWarning();
  }

  function updateWeakPasswordWarning() {
    const value = document.getElementById("auth-admin").value;
    document.getElementById("weak-password-warning").hidden = !(
      setupRequired &&
      value.length > 0 &&
      value.length < 12
    );
  }

  function adminHeaders() {
    return {
      "Content-Type": "application/json",
      "X-Admin-Password": document.getElementById("auth-admin").value,
    };
  }

  function setPasswordVisibility(button, visible) {
    const input = document.getElementById(button.dataset.passwordTarget);
    input.type = visible ? "text" : "password";
    button.textContent = visible ? "Hide" : "Show";
    button.setAttribute("aria-pressed", String(visible));
    button.setAttribute(
      "aria-label",
      `${visible ? "Hide" : "Show"} ${button.dataset.passwordTarget === "auth-password" ? "Apple ID password" : "WebUI administrator password"}`,
    );
  }

  document.querySelectorAll("[data-password-target]").forEach((button) => {
    button.addEventListener("click", () => {
      setPasswordVisibility(
        button,
        button.getAttribute("aria-pressed") !== "true",
      );
    });
  });

  openButton.addEventListener("click", () => {
    modal.classList.add("visible");
    errorEl.textContent = "";
    const firstField =
      setupRequired && !usernameConfigured ? "auth-username" : "auth-admin";
    document.getElementById(firstField).focus();
  });
  document
    .getElementById("auth-admin")
    .addEventListener("input", updateWeakPasswordWarning);
  document
    .getElementById("auth-cancel")
    .addEventListener("click", () => modal.classList.remove("visible"));

  submitButton.addEventListener("click", async () => {
    errorEl.textContent = "";
    submitButton.disabled = true;
    try {
      const endpoint = waitingForCode ? "/api/auth/verify" : "/api/auth/start";
      const adminValue = document.getElementById("auth-admin").value;
      if (!waitingForCode && setupRequired) {
        const confirmation =
          document.getElementById("auth-admin-confirm").value;
        if (!adminValue) throw new Error("Enter an administrator password");
        if (adminValue !== confirmation)
          throw new Error("The administrator passwords do not match");
        if (
          adminValue.length < 12 &&
          (!document.getElementById("weak-warning-accept").checked ||
            !document.getElementById("weak-warning-confirm").checked)
        )
          throw new Error(
            "Confirm both security warnings to use a password shorter than 12 characters",
          );
      }
      const body = waitingForCode
        ? { code: document.getElementById("auth-code").value.trim() }
        : {
            password: document.getElementById("auth-password").value,
            username: document.getElementById("auth-username").value.trim(),
            admin_password: adminValue,
            accept_weak_password_warning: document.getElementById(
              "weak-warning-accept",
            ).checked,
            confirm_weak_password_warning: document.getElementById(
              "weak-warning-confirm",
            ).checked,
          };
      const response = await fetch(endpoint, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(result.error || "Authentication failed");
      if (result.requires_2fa) {
        waitingForCode = true;
        document.getElementById("auth-code-row").hidden = false;
        document.getElementById("apple-password-row").hidden = true;
        document.getElementById("auth-step").textContent =
          "Enter the new code shown on your trusted Apple device.";
        submitButton.textContent = "Verify code";
      } else {
        waitingForCode = false;
        modal.classList.remove("visible");
        document.getElementById("auth-password").value = "";
        document.getElementById("auth-code").value = "";
        document.getElementById("auth-admin").value = "";
        document.getElementById("auth-admin-confirm").value = "";
        document.getElementById("auth-username").value = "";
        document.getElementById("weak-warning-accept").checked = false;
        document.getElementById("weak-warning-confirm").checked = false;
        document
          .querySelectorAll("[data-password-target]")
          .forEach((button) => setPasswordVisibility(button, false));
        updateWeakPasswordWarning();
        await loadStatus();
      }
    } catch (error) {
      errorEl.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });

  loadStatus().catch(() => {
    statusEl.textContent = "Authentication status unavailable";
  });
  setInterval(loadStatus, 60000);
})();
