'use strict';
/* Optional browser acceptance check. Requires Playwright and a Chromium binary.
 * Start an isolated app first, then:
 *   MIKEIZU_BASE_URL=http://127.0.0.1:8765 node tests/browser_smoke.cjs
 * It uses synthetic research and the global stop/resume controls only.
 * Never run against a session with an active broker or automation.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.MIKEIZU_BASE_URL||'http://127.0.0.1:8765';
const executablePath=process.env.MIKEIZU_CHROMIUM||'/usr/bin/chromium';
(async()=>{
 const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox']});
 const errors=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  const before=await fetch(base+'/api/deriv/status').then(r=>r.json());
  assert.equal(before.connected,false,'Browser smoke must use an isolated, disconnected application');
  const initial=await fetch(base+'/api/bootstrap').then(r=>r.json());
  assert.equal(initial.robot.active,false,'Browser smoke must not stop existing automation');
  await page.goto(base,{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.getElementById('metric-balance').textContent!=='—');
  await page.waitForFunction(()=>document.getElementById('engine-connectivity').textContent.includes('RESPONDING'));
  assert.match(await page.locator('#workspace-mode').innerText(),/SYNTHETIC/);
  for(const name of ['overview','strategies','deriv','robot','backtest','history','risk','settings']){
   await page.locator(`[data-page="${name}"]`).click();
   await page.locator('#page-'+name).waitFor({state:'visible'});
   assert.equal(await page.locator('#global-kill').isVisible(),true,'Emergency stop must remain visible on '+name);
  }
  await page.locator('[data-page="strategies"]').click();
  await page.waitForFunction(()=>document.getElementById('lab-strategy').options.length>=18);
  await page.locator('#lab-source').selectOption('synthetic');
  await page.locator('#lab-backtest').click();
  await page.locator('#lab-result').waitFor({state:'visible',timeout:30000});
  assert.match(await page.locator('#lab-origin').innerText(),/Synthetic/);
  assert.match(await page.locator('#lab-breakeven').innerText(),/informational/);
  assert.match(await page.locator('#research-regime').innerText(),/Classification is uncertain/);
  assert.match(await page.locator('#research-walk-forward').innerText(),/historical simulation/);
  assert.match(await page.locator('#lab-in-sample').innerText(),/Trading costs/);
  await page.locator('#view-toggle').click();
  await page.locator('.research-assumptions summary').click();
  await page.locator('#research-commission').waitFor({state:'visible'});
  await page.locator('[data-page="risk"]').click();
  assert.equal(await page.locator('#limit-risk_per_trade_pct').isDisabled(),true,'Disconnected accounts cannot edit broker limits');
  await page.locator('#global-kill').click();
  await page.waitForFunction(()=>document.getElementById('risk-state-label').textContent==='EMERGENCY STOP');
  let risk=await fetch(base+'/api/risk/status').then(r=>r.json());
  assert.equal(risk.halted,true,'Emergency stop must persist through the API');
  await page.reload({waitUntil:'networkidle'});
  await page.locator('[data-page="risk"]').click();
  await page.waitForFunction(()=>document.getElementById('risk-state-label').textContent==='EMERGENCY STOP');
  await page.locator('#risk-resume-phrase').fill('RESUME DEMO TRADING');
  await page.locator('#risk-resume').click();
  await page.waitForFunction(()=>document.getElementById('risk-state-label').textContent==='NO ACCOUNT');
  risk=await fetch(base+'/api/risk/status').then(r=>r.json());
  assert.equal(risk.halted,false,'Explicit resume clears the stop without starting automation');
  assert.equal((await fetch(base+'/api/bootstrap').then(r=>r.json())).robot.active,false);
  await page.setViewportSize({width:390,height:844});
  for(const name of ['overview','strategies','deriv','risk','settings']){
   await page.locator(`[data-page="${name}"]`).click();
   assert.equal(await page.locator('#global-kill').isVisible(),true,'Stop control must be visible on mobile');
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
   assert.equal(overflow,false,'Page must not cause horizontal viewport overflow: '+name);
  }
  const workerContext=await browser.newContext();
  const workerPage=await workerContext.newPage();
  workerPage.on('pageerror',error=>errors.push(error.message));
  await workerPage.goto(base,{waitUntil:'networkidle'});
  await workerPage.waitForFunction(()=>navigator.serviceWorker.controller!==null,null,{timeout:15000});
  await workerContext.close();
  assert.deepEqual(errors,[],'No browser JavaScript exceptions');
  console.log('PASS: 8 pages; synthetic backtest metrics/regime/walk-forward; view switch; durable kill/reload/resume; 5 mobile pages; service worker install; no JS errors.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
