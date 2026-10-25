/* The original client writes HTTPS preference cookies; keep local HTTP previews usable. */
(() => {
  const cookie=Object.getOwnPropertyDescriptor(Document.prototype,'cookie');
  if(!cookie?.get||!cookie?.set)return;
  Object.defineProperty(Document.prototype,'cookie',{
    configurable:cookie.configurable,enumerable:cookie.enumerable,
    get(){return cookie.get.call(this);},
    set(value){
      if(typeof value==='string'&&/^cash-web-preference--/.test(value)){
        value=value.replace(/;\s*domain=[^;]*/gi,'');
        if(location.protocol==='http:')value=value.replace(/;\s*secure\b/gi,'');
      }
      cookie.set.call(this,value);
    }
  });
})();
