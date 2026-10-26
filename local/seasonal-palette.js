/* Orange seasonal accent overrides; native styles remain intact for November. */
(() => {
  const sheet=document.createElement('style');
  sheet.dataset.cashlarpPalette='true';document.head.append(sheet);
  const scope='html[data-cashlarp-season="halloween"]';
  let queued=false;
  function halloween(value,property) {
    return value.replace(/#[\da-f]{8}\b|#[\da-f]{6}\b|#[\da-f]{3}\b|rgba?\([^)]*\)/gi,color=>{
      let rgb,alpha='';
      if(color[0]==='#') {
        let hex=color.slice(1);if(hex.length===3)hex=[...hex].map(c=>c+c).join('');
        rgb=[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16));if(hex.length===8)alpha=(parseInt(hex.slice(6),16)/255).toString();
      } else {const components=color.match(/[\d.]+/g);if(!components||components.length<3)return color;rgb=components.slice(0,3).map(Number);alpha=components[3]||'';}
      const [r,g,b]=rgb;
      let target;
      if(g>=65&&g>=r*1.18&&g>=b*1.15) target=[245,122,24];
      else if(Math.max(...rgb)-Math.min(...rgb)<38){
        const light=(r+g+b)/3;
        if(property.includes('background')) target=light>210?[24,17,13]:light>120?[53,38,29]:light<20?[10,7,5]:null;
        else if(property.includes('border')||property.includes('outline'))target=[93,61,39];
        else if(property==='color'||property==='fill'||property==='stroke')target=light<140?[255,240,225]:light<220?[207,181,158]:null;
      }
      if(!target)return color;
      return alpha?`rgba(${target.join(',')},${alpha})`:`rgb(${target.join(',')})`;
    });
  }
  function copy(rules) {
    let result='';
    for(const rule of rules) {
      if(rule.selectorText&&rule.style){
        let declarations='';
        for(const property of rule.style){
          const value=rule.style.getPropertyValue(property);
          const replacement=halloween(value,property);
          if(value!==replacement)declarations+=`${property}:${replacement}!important;`;
          if(property==='background-color'&&replacement==='rgb(245,122,24)')declarations+='color:#1b1008!important;';
        }
        if(declarations)result+=rule.selectorText.split(',').map(s=>`${scope} ${s}`).join(',')+'{'+declarations+'}';
      } else if(rule.cssRules&&rule.conditionText) result+=`@media ${rule.conditionText}{${copy(rule.cssRules)}}`;
    }
    return result;
  }
  function refresh(){
    queued=false;let css='';
    if(document.documentElement.dataset.cashlarpSeason==='halloween')for(const source of document.styleSheets){
      if(source.ownerNode===sheet)continue;
      try{css+=copy(source.cssRules);}catch{}
    }
    if(sheet.textContent!==css)sheet.textContent=css;
  }
  function schedule(){if(!queued){queued=true;queueMicrotask(refresh);}}
  const insertRule=CSSStyleSheet.prototype.insertRule;
  CSSStyleSheet.prototype.insertRule=function(...args){const result=insertRule.apply(this,args);schedule();return result;};
  new MutationObserver(schedule).observe(document.head,{childList:true,subtree:true,characterData:true});
  document.addEventListener('cashlarp:seasonchange',schedule);
  document.addEventListener('load',schedule,true);
  schedule();
})();
