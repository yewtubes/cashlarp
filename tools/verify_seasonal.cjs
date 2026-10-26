// Exercise the shipped browser script across UTC expiry without waiting overnight.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function run(initial) {
  let now=Date.parse(initial), decoration, timer, events=0;
  const handlers={};
  const icons=['/favicon.png','/favicon.ico'].map(href=>({dataset:{},attrs:{href,type:'image/png'},getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}}));
  const document={
    documentElement:{dataset:{}}, head:{append(){}},body:{append(node){decoration=node;}},
    createElement(){return {children:[],setAttribute(){},append(node){this.children.push(node);},remove(){decoration=undefined;}};},
    querySelector(){return decoration;},querySelectorAll(){return icons;},
    addEventListener(name,fn){handlers[name]=fn;},dispatchEvent(){events++;}
  };
  const config={startsAt:Date.parse('2026-10-01T00:00:00Z'),endsAt:Date.parse('2026-11-01T00:00:00Z'),serverTime:now};
  const context={document,window:{cashlarpSeasonalConfig:config,addEventListener(name,fn){handlers[name]=fn;}},Image:class{},Date:{now:()=>now},Event:class{},setTimeout(fn,delay){timer={fn,delay};return 1;},clearTimeout(){timer=undefined;}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../local/seasonal.js'),'utf8'),context);
  return {document,icons,get decoration(){return decoration;},get timer(){return timer;},get events(){return events;},setTime(value){now=Date.parse(value);},wake(){handlers.visibilitychange();}};
}
const page=run('2026-10-31T23:59:59Z');
assert.equal(page.document.documentElement.dataset.cashlarpSeason,'halloween');
assert.equal(page.decoration,undefined); // pumpkins are part of the generated logo, never floating overlays
assert(page.icons.every(i=>i.attrs.href.endsWith('/halloween/favicon.svg')));
assert.equal(page.timer.delay,1000);
page.setTime('2026-11-01T00:00:00Z');
page.timer.fn();
assert.equal(page.document.documentElement.dataset.cashlarpSeason,'');
assert.equal(page.decoration,undefined);
assert.deepEqual(page.icons.map(i=>i.attrs.href),['/favicon.png','/favicon.ico']);
assert.equal(page.timer,undefined);
assert.equal(page.events,2);
const sleeping=run('2026-10-31T19:00:00Z');
sleeping.setTime('2026-11-02T12:00:00Z');sleeping.wake();
assert.equal(sleeping.decoration,undefined);
assert.equal(run('2027-10-26T00:00:00Z').decoration,undefined);
console.log('Seasonal checks passed: Halloween assets, exact UTC expiry, open/sleeping tabs, default favicon restoration, no annual recurrence.');
