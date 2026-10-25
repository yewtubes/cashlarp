/* Cashlarp branding layer. Captured application components remain in use. */
(() => {
  const style = document.createElement('style');
  style.textContent = `
    #sandbox-disclosure,#sandbox-login-note{display:none!important}
    body{padding-top:0!important}
    .cashlarp-brand{background-color:transparent!important;flex-shrink:0}
    .cashlarp-brand svg,.cashlarp-brand img:not(.cashlarp-logo){display:none!important}
    .cashlarp-logo{display:block!important;width:148px!important;height:36px!important;object-fit:contain!important;pointer-events:none!important}
    .cashlarp-icon .cashlarp-logo{width:40px!important;height:40px!important}
  `;
  document.head.append(style);
  let queued = false;
  function syncLogo(anchor) {
    const image=anchor.querySelector('.cashlarp-logo');
    if(!image||anchor.dataset.cashlarpBrand!=='wordmark')return;
    const path=anchor.querySelector('svg path');
    const fill=path?.getAttribute('fill')?.toLowerCase();
    const dark=fill==='#ffffff'||fill==='#fff';
    const url='/local/brand/cashlarp-wordmark'+(dark?'-dark':'')+'.svg';
    if(image.getAttribute('src')!==url)image.src=url;
  }
  function brand() {
    queued = false;
    document.title='Cashlarp';
    for (const node of document.querySelectorAll('#sandbox-disclosure,#sandbox-login-note')) node.remove();
    const anchors=new Set(document.querySelectorAll('a[aria-label="Cash App Logo"],a[aria-label="Link to home page"],a[data-cashlarp-brand]'));
    for(const logo of document.querySelectorAll('svg[aria-label="Cash App Logo"],svg[aria-label="Cashlarp Logo"]')){
      const link=logo.closest('a');if(link)anchors.add(link);
    }
    for (const anchor of anchors) {
      if(anchor.dataset.cashlarpBrand && anchor.querySelector('.cashlarp-logo')){syncLogo(anchor);continue;}
      const login=anchor.getAttribute('aria-label')==='Link to home page';
      const original=anchor.querySelector('svg');
      anchor.dataset.cashlarpBrand=login?'icon':'wordmark';
      anchor.classList.add('cashlarp-brand',login?'cashlarp-icon':'cashlarp-wordmark');
      anchor.setAttribute('aria-label',login?'Cashlarp home':'Cashlarp Logo');
      const image=new Image();image.src='/local/brand/cashlarp-'+(login?'icon':'wordmark')+'.svg';image.alt='Cashlarp';image.className='cashlarp-logo';(original?.parentElement||anchor).append(image);syncLogo(anchor);
    }
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes){
      const parent=node.parentElement;
      if(!parent||/^(SCRIPT|STYLE|TEXTAREA|INPUT|PRE|CODE)$/.test(parent.tagName)||parent.closest('[data-cashlarp-legal]'))continue;
      let text=node.nodeValue;
      if(text.includes('Banking services provided by Cash App')){
        parent.dataset.cashlarpLegal='true';
        const about=document.createElement('a');about.href='/about';about.textContent='About Cashlarp';parent.replaceChildren(about);continue;
      }
      if(text.includes('By continuing, you also agree to receive'))text='Use a reserved @example.com email or a 202-555-0100–0199 number. Verification code: 123456. No messages are sent.';
      text=text.replace(/Cash App/g,'Cashlarp').replace(/Cash Sandbox/g,'Cashlarp').replace(/Cash\.app/g,'Cashlarp')
        .replace(/\bplay[- ]money\b/gi,'Cashlarp money').replace(/\bPLAY MONEY\b/g,'Cashlarp');
      if(text!==node.nodeValue)node.nodeValue=text;
    }
    for(const link of document.querySelectorAll('a[href^="https://cash.app/legal/"]'))link.setAttribute('href','/about');
    for(const element of document.querySelectorAll('[aria-label],[title],[alt]')){
      for(const attr of ['aria-label','title','alt']){
        const value=element.getAttribute(attr);if(value?.includes('Cash App'))element.setAttribute(attr,value.replace(/Cash App/g,'Cashlarp'));
      }
    }
  }
  new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(brand);}}).observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['fill']});
  brand();
  document.addEventListener('click',event=>{
    const link=event.target.closest?.('a[href]');
    if(link&&/^https:\/\/cash\.app\/legal\//.test(link.href)){
      event.preventDefault();event.stopImmediatePropagation();location.assign('/about');
    }
  },true);
})();
