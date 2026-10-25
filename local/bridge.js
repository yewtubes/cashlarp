/* Local integration patch; deliberately separate from captured original bundles. */
(() => {
  const flags = window.featureFlagsJson || {};
  for (const key of Object.keys(flags)) {
    if (/datadog|risk-signal|enable-tm|enable-sid|enable-sitm|conversion-tracking|one-trust|wait-for-sid/.test(key)) {
      flags[key] = key.includes("config") ? { sessionSampleRateOverride: 0 } : false;
    }
  }
  flags["cash-web-passkeys"] = "DISABLED";
  flags["cash-web-passkeys-try-login-with-passkeys"] = "DISABLED";
  window.recaptchaKeyId = "";
  window.accessToken = "sandbox-only";
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin !== location.origin) throw new Error("Sandbox blocks external network requests");
    const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    if (window.__sandboxCsrf) headers.set("X-Sandbox-CSRF", window.__sandboxCsrf);
    const response = await nativeFetch(input, { ...options, headers });
    if (/\/2\.0\/cash\/verify-(email|sms)$/.test(url.pathname) && response.ok) {
      const result = await response.clone().json();
      if (result.status === "SUCCESS") {
        const session = await nativeFetch("/api/me");
        if (session.ok) window.__sandboxCsrf = (await session.json()).csrf;
      }
    }
    return response;
  };
  navigator.sendBeacon = () => false;
  document.addEventListener("click", event => {
    const button = event.target.closest?.("button");
    if (button && /Log in with passkey/i.test(button.textContent)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      location.assign("/about");
      return;
    }
    const link = event.target.closest?.("a[href]");
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) {
      event.preventDefault();
      event.stopImmediatePropagation();
      location.assign("/about");
    }
  }, true);
})();
