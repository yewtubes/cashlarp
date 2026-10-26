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
  const server = spawn(process.env.PYTHON || 'python3', ['-B', 'run.py', '--port', port, '--db', database], {cwd:root, env:{...process.env, CASHLARP_ACCESS_PASSWORD:'', CASHLARP_SECURE_COOKIES:'0'}});
  let serverLog = '', browser, page;
  server.stdout.on('data', b => {serverLog += b;});
  server.stderr.on('data', b => {serverLog += b;});
  const report = {pages:[], errors:[], failedRequests:[], externalRequests:[], screenshots:[]};
  async function record(name) {
    const snapshot = await page.locator('body').innerText();
    report.pages.push({name, url:page.url(), text:snapshot.slice(0,6000)});
    const filename = name + '.png';
    await page.screenshot({path:path.join(output,filename), fullPage:true});
    report.screenshots.push(filename);
    return snapshot;
  }
  async function submit(value, rpc) {
    const response = page.waitForResponse(r => new URL(r.url()).pathname === rpc, {timeout:20000});
    await page.locator('input:visible').first().fill(value);
    const button = page.getByRole('button', {name:/^(Continue|Next|Log in|Sign in)$/i}).first();
    if (await button.isVisible() && await button.isEnabled()) await button.click();
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
    browser = await chromium.launch({headless:true, args:['--no-sandbox']});
    const context = await browser.newContext({viewport:{width:1440,height:960}});
    page = await context.newPage();
    const loaded = new Set();
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('request', request => {
      const url=request.url();
      if (!url.startsWith(base+'/') && !url.startsWith('data:') && !url.startsWith('blob:')) report.externalRequests.push(url);
    });
    page.on('response', response => {
      loaded.add(new URL(response.url()).pathname);
      if(response.status()>=400) report.failedRequests.push({url:response.url(),status:response.status()});
    });
    await page.goto(base+'/account/card');
    await page.locator('input:visible').first().waitFor();
    assert(new URL(page.url()).pathname==='/login');
    await record('01-original-login');
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
    for (const route of ['money','activity','pay-and-request','card','bitcoin','settings','documents']) {
      await page.goto(base+'/account/'+route);
      await page.locator('#root a').first().waitFor();
      await page.waitForLoadState('networkidle');
      const text = await record('account-'+route);
      assert(text.length>100,route+' did not render');
      assert(!text.includes('$kotik') && !text.includes('$friend'), 'Demo accounts leaked into '+route);
      assert(!text.includes('Something went wrong'),route+' rendered an error');
    }
    const logout = page.getByRole('button',{name:/^(Sign out|Log out)$/i}).or(page.getByRole('link',{name:/^(Sign out|Log out)$/i}));
    await logout.first().click();
    await page.waitForURL(/\/login/,{timeout:20000});
    await page.locator('input:visible').first().waitFor();
    assert.equal((await context.request.get(base+'/api/me')).status(),401);
    await record('05-original-signed-out');
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
    throw error;
  } finally {
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
    fs.writeFileSync(path.join(output,'server.log'),serverLog);
    if(browser) await browser.close();
    server.kill();
    fs.rmSync(temporary,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
