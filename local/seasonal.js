/* One-time seasonal artwork. Never changes account data or native controls. */
(() => {
  const config = window.cashlarpSeasonalConfig;
  if (!config) return;
  // Use the server's UTC clock, avoiding browser timezone/clock differences.
  const offset = config.serverTime - Date.now();
  const style = document.createElement('style');
  style.textContent = `
    .cashlarp-pumpkins{position:fixed;inset:0;pointer-events:none!important;z-index:999;overflow:hidden}
    .cashlarp-pumpkins img{position:absolute;bottom:18px;width:124px;height:124px;opacity:.12;pointer-events:none!important;user-select:none}
    .cashlarp-pumpkins img:first-child{left:14px;transform:rotate(-14deg)}
    .cashlarp-pumpkins img:last-child{right:18px;transform:rotate(12deg);width:94px;height:94px}
    @media(max-width:640px){.cashlarp-pumpkins img:first-child{width:64px;height:64px;left:6px;bottom:8px;opacity:.09}.cashlarp-pumpkins img:last-child{display:none}}
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
      document.querySelector('.cashlarp-pumpkins')?.remove();
      if (active) {
        const decorations = document.createElement('div');
        decorations.className = 'cashlarp-pumpkins';
        decorations.setAttribute('aria-hidden','true');
        for (let i=0;i<2;i++) {
          const pumpkin = new Image();
          pumpkin.src = '/local/brand/halloween/pumpkin.svg';
          pumpkin.alt = ''; pumpkin.draggable = false;
          decorations.append(pumpkin);
        }
        document.body.append(decorations);
      }
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
