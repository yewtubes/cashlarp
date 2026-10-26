#!/usr/bin/env node
// Browser regression test against the captured client, with a disposable database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'cashlarp-browser-'));
  const output = path.resolve(process.env.BROWSER_REPORT_DIR || path.join(temporary, 'report'));
  fs.mkdirSync(output, {recursive:true});
  const port = process.env.BROWSER_TEST_PORT || '3198';
  const base = 'http://127.0.0.1:' + port;
  const database = path.join(temporary, 'fresh.sqlite3');
  const server = spawn(process.env.PYTHON || 'python3', ['-B', 'run.py', '--port', port, '--db', database], {cwd:root, env:{...process.env, CASHLARP_ACCESS_PASSWORD:'', CASHLARP_SECURE_COOKIES:'0', CASHLARP_DEBUG_NATIVE:'1'}});
  let serverLog = '', browser, page;
  server.stdout.on('data', b => {serverLog += b;});
  server.stderr.on('data', b => {serverLog += b;});
  const report = {pages:[], errors:[], failedRequests:[], externalRequests:[], screenshots:[], flowInitiations:[]};
  async function record(name) {
    const snapshot = await page.locator('body').innerText();
    report.pages.push({name,url:page.url(),text:snapshot.slice(0,6000),controls:await page.locator('button,a,label,input,[role=button]').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().width>0).map(n=>({tag:n.tagName,role:n.getAttribute('role'),type:n.getAttribute('type'),label:n.getAttribute('aria-label'),placeholder:n.getAttribute('placeholder'),text:n.textContent.trim().slice(0,80)})))});
    const filename = name + '.png';
    await page.screenshot({path:path.join(output,filename), fullPage:true});
    report.screenshots.push(filename);
    return snapshot;
  }
  async function submit(value, rpc) {
    const response = page.waitForResponse(r => new URL(r.url()).pathname === rpc, {timeout:20000});
    response.catch(()=>{});
    await page.locator('input:visible:not([type=radio]):not([type=checkbox]):not([type=file])').first().fill(value);
    const button = page.getByRole('button', {name:/^(Continue|Next|Log in|Sign in|Add)$/i}).first();
    if (await button.isVisible()) await button.click();
    const result = await response;
    assert.equal(result.status(), 200, rpc + ': ' + await result.text());
  }
  try {
    for (let attempt=0; attempt<100; attempt++) {
      if (server.exitCode !== null) throw Error('Server exited: '+serverLog);
      try { if ((await fetch(base+'/api/health')).ok) break; } catch {}
      await new Promise(resolve=>setTimeout(resolve,100));
      if (attempt===99) throw Error('Server not ready: '+serverLog);
    }
    const check = spawnSync(process.env.PYTHON || 'python3', ['-c', 'import sqlite3,sys; assert sqlite3.connect(sys.argv[1]).execute("SELECT count(*) FROM users").fetchone()[0] == 0', database]);
    assert.equal(check.status,0,'Fresh installation must have zero accounts');
    browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL||undefined, args:['--no-sandbox']});
    const context = await browser.newContext({viewport:{width:1440,height:960}});
    page = await context.newPage();
    const loaded = new Set();
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('request', request => {
      const url=request.url();
      if(new URL(url).pathname==='/2.0/cash/get-flow'){try{const data=JSON.parse(request.postData()||'{}');const flow=data.initiation_data||data.flow_type;if(flow&&!report.flowInitiations.includes(flow))report.flowInitiations.push(flow);}catch{}}
      if (!url.startsWith(base+'/') && !url.startsWith('data:') && !url.startsWith('blob:')) report.externalRequests.push(url);
    });
    page.on('response', response => {
      loaded.add(new URL(response.url()).pathname);
      if(response.status()>=400) report.failedRequests.push({url:response.url(),status:response.status()});
    });
    await page.goto(base+'/account/card');
    await page.locator('input:visible:not([type=radio]):not([type=checkbox]):not([type=file])').first().waitFor();
    assert(new URL(page.url()).pathname==='/login');
    await record('01-original-login');
    await page.getByText('Create account',{exact:true}).click();
    await page.getByText('Email',{exact:true}).click();
    await submit('nativeqa@example.com','/2.0/cash/register-email');
    await record('02-original-verification');
    await submit('123456','/2.0/cash/verify-email');
    await record('03-original-name');
    await submit('Native QA Player','/2.0/cash/set-full-name');
    await record('04-original-cashtag');
    await submit('nativeqatag','/2.0/cash/set-cashtag');
    await page.waitForURL(/\/account\//, {timeout:20000});
    await page.locator('a[href="/account/money"]').first().waitFor();
    const profile = await context.request.get(base+'/api/me');
    const identity = (await profile.json()).user.id;
    for (const route of ['money','activity','pay-and-request','card','bitcoin','savings','settings','documents']) {
      await page.goto(base+'/account/'+route);
      await page.locator('#root a').first().waitFor();
      await page.waitForLoadState('networkidle');
      const text = await record('account-'+route);
      assert(text.length>100,route+' did not render');
      assert(!text.includes('$kotik') && !text.includes('$friend'), 'Demo accounts leaked into '+route);
      assert(!text.includes('Something went wrong'),route+' rendered an error');
      const broken=await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>i.getBoundingClientRect().width>0&&i.complete&&i.naturalWidth===0).map(i=>i.src));
      assert.equal(broken.length,0,'Broken images on '+route+': '+broken.join(', '));
      if(route==='activity'){assert(await page.getByTestId('savings-balance-card').isVisible());assert.equal(await page.getByTestId('bitcoin-balance-card').count(),0);}
    }
    await page.goto(base+'/account/settings');
    await page.locator('input[type=file]').first().setInputFiles(path.join(root,'local/brand/apple-touch-icon.png'));
    await page.getByTestId('profile-photo-modal-buttons').getByRole('button',{name:'Save',exact:true}).click();
    await page.waitForLoadState('networkidle');
    await page.reload();
    await page.locator('img[src*="/local-profile-photo/"]').first().waitFor();
    await record('profile-photo-saved');
    await page.goto(base+'/account/card?resume_order=true');
    await page.getByTestId('card-option-button-sim_cashlarp').waitFor();
    await page.getByTestId('card-option-button-sim_cashlarp').click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await record('original-card-customization');
    await page.getByRole('button',{name:'Customize',exact:true}).click();
    await page.waitForLoadState('networkidle');
    await record('cashlarp-card-editor');
    assert(await page.locator('canvas').count()>0,'Original card drawing canvas missing');
    await page.getByText('Stamps',{exact:true}).click();
    await page.getByTestId('stamp-cashlarp_netanyahu').click();
    await page.getByTestId('card-studio-customizations').click({position:{x:190,y:210},force:true});
    await record('cashlarp-outline-stamp');
    await page.getByText('Submit',{exact:true}).click();
    await page.waitForLoadState('networkidle');
    await record('cashlarp-card-submitted');
    await page.goto(base+'/account/settings');
    const logout = page.getByText(/^(Sign out|Log out)$/i,{exact:true});
    if(!await logout.first().isVisible()) await page.getByText('Native QA P.',{exact:true}).first().click();
    await logout.first().click();
    await page.waitForURL(/\/login/,{timeout:20000});
    await page.locator('input:visible:not([type=radio]):not([type=checkbox]):not([type=file])').first().waitFor();
    assert.equal((await context.request.get(base+'/api/me')).status(),401);
    await record('05-original-signed-out');
    await page.getByText('Email',{exact:true}).click();
    await submit('nativeqa@example.com','/2.0/cash/register-email');
    await submit('123456','/2.0/cash/verify-email');
    await page.waitForURL(/\/account\//,{timeout:20000});
    assert.equal((await (await context.request.get(base+'/api/me')).json()).user.id,identity);
    await record('06-original-repeat-login');
    assert([...loaded].some(s=>s.endsWith('main.1973b48deea66eb9.js')),'Original login bundle was not loaded');
    assert([...loaded].some(s=>s.endsWith('main.fa6baaec96a82623.js')),'Original account bundle was not loaded');
    assert.equal(report.errors.length,0,'Browser errors: '+report.errors.join('; '));
    assert.equal(report.externalRequests.length,0,'Client attempted external network requests');
    report.passed=true;
    console.log('Original-client browser checks passed: signup, account pages, sign-out, repeat login, empty installation.');
  } catch(error) {
    report.passed=false;
    report.failure=error.stack;
    if(page) await record('failure').catch(()=>{});
    console.error(JSON.stringify(report.pages.at(-1)));
    console.error(JSON.stringify(report.failedRequests));
    console.error(JSON.stringify(report.flowInitiations));
    console.error(serverLog.split('\n').filter(line=>line.includes('Native flow request:')).join('\n'));
    throw error;
  } finally {
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
    fs.writeFileSync(path.join(output,'server.log'),serverLog);
    if(browser) await browser.close();
    server.kill();
    fs.rmSync(temporary,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
