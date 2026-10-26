/* Local transport adapter only. The captured application renders every account screen. */
(() => {
  // Select CardStudio's own 2D fallback; drawing still uses its original canvas.
  // Some managed browsers cannot allocate its extra WebGL preview context.
  let designerSupports3D;
  const chunks = window.webpackChunk = window.webpackChunk || [];
  let chunkPush = chunks.push;
  Object.defineProperty(chunks, "push", {
    configurable: true,
    get() {
      const delegate = chunkPush;
      return function(...payloads) {
        for (const payload of payloads) {
          const factories = payload?.[1];
          const factory = factories?.[77093];
          if (factory && !factory.sandboxWrapped) {
            const wrapped = function(module, exports, require) {
              const proxyRequire = new Proxy(require, {
                get(target, key, receiver) {
                  if (key !== "d") return Reflect.get(target, key, receiver);
                  return (targetExports, definitions) => {
                    if (!definitions.U) return target.d(targetExports, definitions);
                    const getOriginal = definitions.U;
                    const loadTextures = async (...args) => {
                      if (window.__sandboxDesignerActive && designerSupports3D === undefined) {
                        let renderer;
                        try {
                          const THREE = require(47158);
                          renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true });
                          renderer.setSize(Math.min(innerWidth,1024),Math.min(innerHeight,768),false);
                          designerSupports3D = !renderer.getContext().isContextLost();
                        } catch { designerSupports3D = false; }
                        finally { renderer?.dispose(); renderer?.forceContextLoss(); }
                      }
                      if (window.__sandboxDesignerActive && !designerSupports3D) throw new Error("Use original CardStudio 2D fallback");
                      return getOriginal()(...args);
                    };
                    return target.d(targetExports, { ...definitions, U: () => loadTextures });
                  };
                }
              });
              return factory(module, exports, proxyRequire);
            };
            wrapped.sandboxWrapped = true;
            factories[77093] = wrapped;
          }
        }
        return delegate.apply(this, payloads);
      };
    },
    set(value) { chunkPush = value; }
  });
  const originalFetch = window.fetch.bind(window);
  const tradeKeys = new Map();
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin !== location.origin) return Promise.reject(new Error("Sandbox blocks external network requests"));
    if (url.pathname === "/2.0/cash/get-flow" && typeof options.body === "string") {
      const initiation = JSON.parse(options.body).initiation_data || "";
      if (/^(CHANGE_CARD_DESIGN|REQUEST_PHYSICAL_CARD)/.test(initiation)) window.__sandboxDesignerActive = true;
    }
    const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    headers.set("X-Sandbox-CSRF", window.csrfToken);
    if (url.pathname === "/cash-app/crypto/invest/exchange" && typeof options.body === "string") {
      const signature = options.body;
      const payload = JSON.parse(signature);
      let key = tradeKeys.get(signature);
      if (!key) { key = Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2,"0")).join(""); tradeKeys.set(signature,key); }
      payload.external_id = key;
      return originalFetch(input, { ...options, headers, body: JSON.stringify(payload) }).then(response => {
        if (response.ok) tradeKeys.delete(signature);
        return response;
      });
    }
    const response = await originalFetch(input, { ...options, headers });
    if (response.status === 401 && url.pathname !== '/logout') {
      location.assign('/login?redirect=' + encodeURIComponent(location.pathname + location.search));
    }
    return response;
  };
  navigator.sendBeacon = () => false;
  document.addEventListener("click", event => {
    const link = event.target.closest?.("a[href]");
    if (link && new URL(link.href, location.href).origin !== location.origin) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
})();
