/* One-time seasonal artwork. Never changes account data or native controls. */
(() => {
  const config = window.cashlarpSeasonalConfig;
  if (!config) return;
  // Use the server's UTC clock, avoiding browser timezone/clock differences.
  const offset = config.serverTime - Date.now();
  const style = document.createElement('style');
  style.textContent = `
    html[data-cashlarp-season="halloween"] .cashlarp-logo{width:184px!important;height:54px!important}
    html[data-cashlarp-season="halloween"] input{accent-color:#f57a18}
    html[data-cashlarp-season="halloween"] ::selection{background:#ffd1a6;color:#20150e}
    html[data-cashlarp-season="halloween"] [fill="#00D64B" i],html[data-cashlarp-season="halloween"] [fill="#00E013" i]{fill:#ff7a18!important}
    html[data-cashlarp-season="halloween"] #app-root .cashlarp-logo{width:240px!important;height:68px!important}
  `;
  document.head.append(style);
  let timer;
  function refresh() {
    clearTimeout(timer);
    const now = Date.now() + offset;
    const active = now >= config.startsAt && now < config.endsAt;
    const season = active ? 'halloween' : '';
    if (document.documentElement.dataset.cashlarpSeason !== season) {
      document.documentElement.dataset.cashlarpSeason = season;
      for (const icon of document.querySelectorAll('link[rel="icon"],link[rel="shortcut icon"]')) {
        if (!icon.dataset.cashlarpDefaultHref) icon.dataset.cashlarpDefaultHref = icon.getAttribute('href');
        if (!icon.dataset.cashlarpDefaultType) icon.dataset.cashlarpDefaultType = icon.getAttribute('type') || '';
        icon.setAttribute('href',active ? '/local/brand/halloween/favicon.svg' : icon.dataset.cashlarpDefaultHref);
        if (active) icon.setAttribute('type','image/svg+xml');
        else if (icon.dataset.cashlarpDefaultType) icon.setAttribute('type',icon.dataset.cashlarpDefaultType);
        else icon.removeAttribute('type');
      }
      document.dispatchEvent(new Event('cashlarp:seasonchange'));
    }
    // Also expires on an already-open tab, without a reload or deployment.
    if (now < config.endsAt) timer = setTimeout(refresh,Math.max(1,Math.min(60000,(active?config.endsAt:config.startsAt)-now)));
  }
  document.addEventListener('visibilitychange',refresh);
  window.addEventListener('pageshow',refresh);
  refresh();
})();
