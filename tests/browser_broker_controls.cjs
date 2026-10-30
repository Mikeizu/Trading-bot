'use strict';
/* Connected-control acceptance uses ONLY tests/fake_broker_server.py.
 * This is an offline broker double, never authenticated Deriv evidence.
 * Run: node tests/browser_broker_controls.cjs
 * Optional: MIKEIZU_BROKER_BASE_URL=http://127.0.0.1:8892 for an existing fixture.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const base=process.env.MIKEIZU_BROKER_BASE_URL||'http://127.0.0.1:8892';
const reportPath=process.env.MIKEIZU_BROKER_REPORT||'/tmp/mikeizu-broker-controls-report.json';
const evidence={scope:'OFFLINE TEST DOUBLE: all broker balances, prices, markets, credentials and executions are fictional. No Deriv connection or broker trade.',
 tests:[],controls:{},browser_errors:[],external_browser_requests:[],network:'none'};
let fixture=null,browser=null,strategyIDs=[];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function api(route,body,expected=200){
 const response=await fetch(base+route,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await response.json();
 assert.equal(response.status,expected,`${route}: ${JSON.stringify(data)}`);
 return data;
}
async function check(name,controls,fn){
 const start=Date.now();
 console.log('CHECK:',name);
 try{await fn();evidence.tests.push({name,status:'passed_mocked',duration_ms:Date.now()-start});
  for(const control of controls){if(!['gate_verified_mocked','blocked_by_design_verified','external_link_inspected'].includes(evidence.controls[control]?.status))evidence.controls[control]={status:'passed_mocked',test:name};}
 }catch(error){evidence.tests.push({name,status:'failed',error:error.message});throw error;}
}
async function persist(){await fs.writeFile(reportPath,JSON.stringify(evidence,null,2));}
async function waitServer(){
 for(let n=0;n<100;n++){
  try{const r=await fetch(base+'/__test__/status');if(r.ok){const d=await r.json();assert.equal(d.fixture,true);assert.equal(d.network,'none');return;}}
  catch(error){if(fixture?.exitCode!=null)throw Error('Test-only fixture exited before ready');}
  await pause(100);
 }
 throw Error('Test-only fixture did not become ready');
}
(async()=>{
 if(!process.env.MIKEIZU_BROKER_BASE_URL){
  const python=process.env.MIKEIZU_TEST_PYTHON||path.join(root,'.venv','bin','python');
  fixture=spawn(python,['tests/fake_broker_server.py','--port','8892'],{cwd:root,stdio:['ignore','pipe','pipe']});
  let output='';fixture.stdout.on('data',b=>{output+=b});fixture.stderr.on('data',b=>{output+=b});
  fixture.on('error',error=>{evidence.fixture_error=error.message});
  evidence.fixture_output=()=>output;
 }
 await waitServer();
 const initial=await api('/__test__/status');
 assert.equal(initial.broker.connected,false,'Use a fresh disconnected test fixture only');
 browser=await chromium.launch({executablePath:process.env.MIKEIZU_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block',acceptDownloads:true});
 const page=await context.newPage();
 page.on('pageerror',error=>evidence.browser_errors.push(error.message));
 await context.route('**/*',route=>{const url=new URL(route.request().url());if(url.origin===new URL(base).origin||['data:','blob:'].includes(url.protocol))return route.continue();evidence.external_browser_requests.push(url.origin);return route.abort('blockedbyclient');});
 let acceptDialogs=true;
 page.on('dialog',dialog=>acceptDialogs?dialog.accept():dialog.dismiss());
 const nav=async name=>{await page.locator(`[data-page="${name}"]`).click();await page.locator('#page-'+name).waitFor({state:'visible'});};
 const refreshed=async()=>{await page.evaluate(async()=>{await loadDeriv();await terminalRefresh();await labPoll();});};
 const login=async mode=>{
  await nav('deriv');
  await page.locator('#deriv-app-id').fill('fixture-app');
  await page.locator('#deriv-pat').fill('fixture-pat-not-a-real-credential');
  const listed=page.waitForResponse(r=>r.url().endsWith('/api/deriv/accounts'));
  await page.locator('#deriv-list').click();await listed;
  await page.locator('#deriv-account').selectOption(mode==='real'?'REAL_TEST02':'DEMO_TEST01');
  const connected=page.waitForResponse(r=>r.url().endsWith('/api/deriv/connect'));
  await page.locator('#deriv-auth-form [type="submit"]').click();
  assert.equal((await connected).status(),200);
  await page.waitForFunction(m=>window.derivStatus?.connected&&window.derivStatus.mode===m,mode);
  await refreshed();
 };
 const quote=async()=>{
  const returned=page.waitForResponse(r=>r.url().endsWith('/api/deriv/quote'));
  await page.locator('#deriv-order-form [type="submit"]').click();
  const response=await returned;assert.equal(response.status(),200,await response.text());
  await page.locator('#deriv-quote-panel').waitFor({state:'visible'});
  return response.json();
 };
 await page.goto(base,{waitUntil:'networkidle'});
 strategyIDs=Object.keys((await api('/api/strategy/catalog')).strategies);assert.ok(strategyIDs.length>=18);
 await page.waitForFunction(()=>document.getElementById('engine-connectivity').textContent.includes('RESPONDING'));
 await nav('deriv');

 await check('Invalid broker authentication gives actionable error without a session',['deriv-app-id','deriv-pat','deriv-list'],async()=>{
  await page.locator('#deriv-app-id').fill('fixture-app');await page.locator('#deriv-pat').fill('invalid-fixture-token');
  const response=page.waitForResponse(r=>r.url().endsWith('/api/deriv/accounts'));
  await page.locator('#deriv-list').click();assert.equal((await response).status(),400);
  await page.locator('#deriv-auth-help').waitFor({state:'visible'});
  assert.equal((await api('/__test__/status')).broker.connected,false);
 });
 await check('Developer portal link is HTTPS and safely opens externally without network navigation',['a:https://developers.deriv.com/:Deriv Developer Portal'],async()=>{
  const link=page.locator('a[href="https://developers.deriv.com/"]');
  assert.equal(await link.getAttribute('target'),'_blank');
  const rel=(await link.getAttribute('rel')||'').split(/\s+/);
  assert.ok(rel.includes('noopener')&&rel.includes('noreferrer'));
  evidence.controls['a:https://developers.deriv.com/:Deriv Developer Portal']={status:'external_link_inspected',test:'HTTPS destination and safe target/rel inspected; external service not navigated or verified.'};
 });
 await check('Demo account discovery/connect clears browser credentials',['deriv-account','deriv-auth-form submit'],async()=>{
  await login('demo');assert.match(await page.locator('#deriv-top-status').innerText(),/DEMO/);
  assert.equal(await page.locator('#deriv-pat').inputValue(),'');assert.equal(await page.locator('#deriv-app-id').inputValue(),'');
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(k=>/token|credential|pat/i.test(k))),false);
 });
 await check('Market refresh updates catalogue as well as balance',['deriv-refresh','deriv-symbol'],async()=>{
  await api('/__test__/fault',{fault:'markets_empty'});
  const refreshedMarkets=page.waitForResponse(r=>r.url().endsWith('/api/deriv/markets'));
  await page.locator('#deriv-refresh').click();assert.equal((await refreshedMarkets).status(),200);
  await page.waitForFunction(()=>document.getElementById('deriv-symbol').options.length===1);
  await api('/__test__/fault',{fault:''});await page.locator('#deriv-refresh').click();
  await page.waitForFunction(()=>document.getElementById('deriv-symbol').options.length===4);
 });
 await check('No-offer market disables quoting; offered directions and all expiry choices work',['deriv-check-durations','deriv-symbol','deriv-side','deriv-minutes'],async()=>{
  await page.locator('#deriv-symbol').selectOption('NO_DURATION');
  await page.waitForFunction(()=>document.getElementById('deriv-duration-info').textContent.includes('no UP'));
  assert.equal(await page.locator('#deriv-order-form [type="submit"]').isDisabled(),true);
  await page.locator('#deriv-symbol').selectOption('R_100');
  await page.locator('#deriv-check-durations').click();
  await page.waitForFunction(()=>!document.querySelector('#deriv-order-form [type="submit"]').disabled);
  for(const side of ['DOWN','UP'])await page.locator('#deriv-side').selectOption(side);
  for(let minute=1;minute<=15;minute++)await page.locator('#deriv-minutes').selectOption(String(minute));
  await page.locator('#deriv-minutes').selectOption('2');
 });
 await check('Changing stake or expiry invalidates a previously reviewed quote',['deriv-stake','deriv-minutes','deriv-order-form submit'],async()=>{
  await quote();await page.locator('#deriv-stake').fill('2');assert.equal(await page.locator('#deriv-quote-panel').isVisible(),false);
  await quote();await page.locator('#deriv-minutes').selectOption('3');assert.equal(await page.locator('#deriv-quote-panel').isVisible(),false);
  await page.locator('#deriv-stake').fill('1');await page.locator('#deriv-minutes').selectOption('2');
 });
 await check('Manual review cancellation sends no buy; confirmed fixture order cannot replay',['deriv-buy'],async()=>{
  const q=await quote();acceptDialogs=false;await page.locator('#deriv-buy').click();await pause(100);acceptDialogs=true;
  assert.equal((await api('/__test__/status')).buy_count,0);
  const bought=page.waitForResponse(r=>r.url().endsWith('/api/deriv/buy'));
  await page.locator('#deriv-buy').click();assert.equal((await bought).status(),200);
  await page.waitForFunction(()=>document.getElementById('deriv-rows').textContent.includes('OPEN'));
  assert.equal((await api('/__test__/status')).buy_count,1);
  await api('/api/deriv/buy',{token:q.token},400);assert.equal((await api('/__test__/status')).buy_count,1);
  await api('/__test__/settle',{});await page.locator('#deriv-refresh').click();
  await page.waitForFunction(()=>document.getElementById('deriv-rows').textContent.includes('CLOSED'));
 });
 await check('Every indicator robot strategy configures and stops without autonomous fixture fills',['deriv-strategy','deriv-auto-stake','deriv-auto-start','deriv-auto-stop'],async()=>{
  for(const strategy of ['RSI','SMA','MACD','BOLLINGER','STOCHASTIC','CCI']){
   await page.locator('#deriv-strategy').selectOption(strategy);await page.locator('#deriv-auto-stake').fill(strategy==='RSI'?'0.35':'1');
   const start=page.waitForResponse(r=>r.url().endsWith('/api/deriv/automation'));
   await page.locator('#deriv-auto-start').click();assert.equal((await start).status(),200);
   await page.waitForFunction(()=>window.derivStatus?.automation===true);
   const stop=page.waitForResponse(r=>r.url().endsWith('/api/deriv/automation'));
   await page.locator('#deriv-auto-stop').click();assert.equal((await stop).status(),200);
   await page.waitForFunction(()=>window.derivStatus?.automation===false);
  }
  assert.equal((await api('/__test__/status')).buy_count,1,'Configuration controls do not manufacture signals');
 });
 await check('Candle history control loads well-formed closed fixture bars',['deriv-candle-fetch'],async()=>{
  await page.locator('#deriv-candle-fetch').click();
  await page.waitForFunction(()=>document.getElementById('deriv-candle-info').textContent.includes('Loaded 140'));
 });
 await nav('risk');await refreshed();
 await check('Connected default risk form is valid and saves every configurable hard limit',[
  'limit-risk_per_trade_pct','limit-daily_loss_pct','limit-weekly_loss_pct','limit-max_drawdown_pct',
  'limit-max_positions','limit-max_trades_per_day','limit-max_order_size','limit-max_asset_exposure_pct',
  'limit-max_group_exposure_pct','limit-consecutive_loss_limit','limit-cooldown_minutes','risk-config-form submit'],async()=>{
  assert.equal(await page.locator('#risk-config-form').evaluate(e=>e.checkValidity()),true,'Default numeric fields must be saveable');
  if(await page.locator('#view-toggle').getAttribute('aria-pressed')!=='true')await page.locator('#view-toggle').click();
  const inputs={risk_per_trade_pct:.4,daily_loss_pct:1.5,weekly_loss_pct:4,max_drawdown_pct:8,
   max_positions:2,max_trades_per_day:10,max_order_size:10,max_asset_exposure_pct:1.5,
   max_group_exposure_pct:1.5,consecutive_loss_limit:3,cooldown_minutes:90};
  for(const [name,value] of Object.entries(inputs))await page.locator('#limit-'+name).fill(String(value));
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/risk/config'));
  await page.locator('#risk-config-form [type="submit"]').click();assert.equal((await saved).status(),200);
  const state=await api('/api/risk/status');for(const [key,value] of Object.entries(inputs))assert.equal(state.risk.config[key],value);
 });
 await check('Synthetic calendar exception needs confirmation and persists only after approval',['limit-calendar_policy'],async()=>{
  await page.locator('#limit-calendar_policy').selectOption('synthetic_exempt');acceptDialogs=false;
  await page.locator('#risk-config-form [type="submit"]').click();await pause(100);acceptDialogs=true;
  assert.equal((await api('/api/risk/status')).risk.config.calendar_policy,'required');
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/risk/config'));
  await page.locator('#risk-config-form [type="submit"]').click();assert.equal((await saved).status(),200);
  assert.equal((await api('/api/risk/status')).risk.config.calendar_policy,'synthetic_exempt');
 });
 await check('Calendar import rejects malformed JSON and accepts explicit current fixture coverage',['risk-calendar-file'],async()=>{
  await page.locator('#risk-calendar-file').evaluate(e=>e.closest('details').open=true);
  await page.locator('#risk-calendar-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{}')});
  await page.waitForFunction(()=>document.getElementById('risk-calendar-import-note').textContent.includes('Import failed'));
  const now=Date.now()/1000;
  const payload={source:'Deterministic offline test fixture — not economic news',updated_at:now,valid_until:now+3600,events:[]};
  const imported=page.waitForResponse(r=>r.url().endsWith('/api/risk/calendar'));
  await page.locator('#risk-calendar-file').setInputFiles({name:'fixture-calendar.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(payload))});
  assert.equal((await imported).status(),200);
  assert.equal((await api('/api/risk/status')).risk.calendar.fresh,true);
 });
 await check('Connected risk refresh and audit download contain valid isolated records',['risk-refresh','audit-export'],async()=>{
  await page.locator('#risk-refresh').click();await page.waitForFunction(()=>document.getElementById('audit-export').disabled===false);
  const downloaded=page.waitForEvent('download');await page.locator('#audit-export').click();const download=await downloaded;
  const file=await download.path();const exported=JSON.parse(await fs.readFile(file,'utf8'));
  assert.equal(exported.integrity,true);assert.ok(exported.events.length>=3);
  assert.equal(JSON.stringify(exported).includes('fixture-pat-not-a-real-credential'),false);
 });

 await nav('strategies');await refreshed();
 await page.waitForFunction(()=>document.getElementById('lab-symbol').options.length===3);
 await page.locator('#lab-symbol').selectOption('R_100');await page.locator('#lab-source').selectOption('deriv');
 await check('Catalog indicator strategies can each start and stop monitor mode',['lab-strategy','lab-action','lab-start','lab-stop','lab-symbol'],async()=>{
  await page.locator('#lab-action').selectOption('monitor');
  for(const strategy of strategyIDs){
   await page.locator('#lab-strategy').selectOption(strategy);
   const start=page.waitForResponse(r=>r.url().endsWith('/api/strategy/start'));
   await page.locator('#lab-start').click();assert.equal((await start).status(),200);
   await page.waitForFunction(()=>document.getElementById('lab-stop').disabled===false);
   const state=await api('/api/strategy/status');assert.equal(state.strategy,strategy);assert.equal(state.action,'monitor');
   const stop=page.waitForResponse(r=>r.url().endsWith('/api/strategy/stop'));
   await page.locator('#lab-stop').click();assert.equal((await stop).status(),200);
  }
 });
 await check('Every trading horizon starts in monitor mode with broker fixture capability',['lab-profile','lab-timeframe'],async()=>{
  const profiles={scalping:['1m','5m'],intraday:['15m','1h'],swing:['4h','1d'],position:['1w','1mo']};
  for(const [profile,frames] of Object.entries(profiles)){
   await page.locator('#lab-profile').selectOption(profile);
   for(const frame of frames){
    await page.locator('#lab-timeframe').selectOption(frame);
    const start=page.waitForResponse(r=>r.url().endsWith('/api/strategy/start'));
    await page.locator('#lab-start').click();assert.equal((await start).status(),200);
    assert.equal((await api('/api/strategy/status')).frame,frame);
    const stop=page.waitForResponse(r=>r.url().endsWith('/api/strategy/stop'));await page.locator('#lab-stop').click();await stop;
   }
  }
 });
 await check('Paper/demo action and expiry controls configure separately from real execution',['lab-action','lab-expiry-minutes','lab-stake'],async()=>{
  await page.locator('#lab-profile').selectOption('scalping');await page.locator('#lab-timeframe').selectOption('1m');
  await page.locator('#lab-stake').fill('0.35');
  for(const action of ['paper_trade','demo_trade']){
   await page.locator('#lab-action').selectOption(action);
   if(action==='demo_trade')await page.locator('#lab-expiry-minutes').selectOption('2');
   const start=page.waitForResponse(r=>r.url().endsWith('/api/strategy/start'));await page.locator('#lab-start').click();assert.equal((await start).status(),200);
   assert.equal((await api('/api/strategy/status')).action,action);
   const stop=page.waitForResponse(r=>r.url().endsWith('/api/strategy/stop'));await page.locator('#lab-stop').click();await stop;
  }
  assert.equal((await api('/__test__/status')).buy_count,1,'No fictitious automatic signals are inserted for a control pass');
 });
 await check('Broker-data research comparison refuses unsupported strategy promotion',['lab-scan-all','lab-export-all','lab-start-best'],async()=>{
  const scanned=page.waitForResponse(r=>r.url().endsWith('/api/strategy/scan-all'));
  await page.locator('#lab-scan-all').click();const response=await scanned;assert.equal(response.status(),200);
  const report=await response.json();assert.equal(report.strategies_tested,strategyIDs.length);assert.equal(report.qualified,false);
  assert.equal(await page.locator('#lab-start-best').isDisabled(),true);
  await api('/api/strategy/start-best',{action:'demo_trade'},400);
  const downloaded=page.waitForEvent('download');await page.locator('#lab-export-all').click();
  const download=await downloaded;const data=JSON.parse(await fs.readFile(await download.path(),'utf8'));
  assert.equal(data.strategies_tested,strategyIDs.length);assert.equal(data.qualified,false);
  evidence.controls['lab-start-best']={status:'gate_verified_mocked',test:'No validated fixture strategy means activation remains disabled; no forged qualification.'};
 });
 await nav('risk');await refreshed();
 await check('Connected emergency stop persists and explicit resume restarts no robot',['global-kill','risk-resume-phrase','risk-resume'],async()=>{
  await page.locator('#global-kill').click();await page.waitForFunction(()=>document.getElementById('risk-state-label').textContent==='EMERGENCY STOP');
  await api('/api/deriv/quote',{symbol:'R_100',side:'UP',stake:1,minutes:2},400);
  await page.locator('#risk-resume-phrase').fill('WRONG PHRASE');await page.locator('#risk-resume').click();
  assert.equal((await api('/api/risk/status')).halted,true);
  await page.reload({waitUntil:'networkidle'});await nav('risk');await page.locator('#risk-resume-phrase').fill('RESUME DEMO TRADING');
  const resumed=page.waitForResponse(r=>r.url().endsWith('/api/risk/resume'));await page.locator('#risk-resume').click();assert.equal((await resumed).status(),200);
  const state=await api('/__test__/status');assert.equal(state.broker.automation,false);assert.equal(state.strategy.active,false);
 });
 await nav('deriv');
 await check('Account disconnect and real-account connection remain strictly read-only',['deriv-disconnect','deriv-account','deriv-arm','deriv-arm-phrase'],async()=>{
  await page.locator('#deriv-disconnect').click();await page.waitForFunction(()=>window.derivStatus?.connected===false);
  await login('real');
  assert.match(await page.locator('#deriv-top-status').innerText(),/READ ONLY/);
  assert.equal(await page.locator('#deriv-order-form [type="submit"]').isDisabled(),true);
  assert.equal(await page.locator('#deriv-arm').isVisible(),false);assert.equal(await page.locator('#deriv-arm').isDisabled(),true);
  assert.equal(await page.locator('#deriv-arm-phrase').isVisible(),false);
  await api('/api/deriv/arm',{phrase:'I AUTHORIZE ONE REAL TRADE'},400);
  await api('/api/deriv/quote',{symbol:'R_100',side:'UP',stake:1,minutes:2},400);
  await nav('risk');await refreshed();await page.waitForFunction(()=>document.getElementById('risk-config-fields').disabled===true&&document.getElementById('risk-account-label').textContent.includes('REAL_TEST02'));
  evidence.controls['deriv-arm']={status:'blocked_by_design_verified',test:'Live execution intentionally unsupported in production.'};
  evidence.controls['deriv-arm-phrase']={status:'blocked_by_design_verified',test:'Live execution intentionally unsupported in production.'};
  await nav('deriv');await page.locator('#deriv-disconnect').click();await page.waitForFunction(()=>window.derivStatus?.connected===false);
 });
 await login('demo');
 await check('Purchase timeout durably blocks retry and survives browser/account reconnect',['deriv-buy','deriv-refresh','deriv-disconnect'],async()=>{
  await page.locator('#deriv-symbol').selectOption('R_100');await page.locator('#deriv-check-durations').click();
  await page.waitForFunction(()=>!document.querySelector('#deriv-order-form [type="submit"]').disabled);
  const q=await quote();await api('/__test__/fault',{fault:'timeout'});
  const result=page.waitForResponse(r=>r.url().endsWith('/api/deriv/buy'));await page.locator('#deriv-buy').click();assert.equal((await result).status(),400);
  assert.equal((await api('/api/deriv/status')).orders[0].status,'UNCERTAIN');
  const before=(await api('/__test__/status')).buy_count;
  await api('/api/deriv/buy',{token:q.token},400);await api('/api/deriv/quote',{symbol:'R_100',side:'UP',stake:1,minutes:2},400);
  await api('/__test__/fault',{fault:''});await page.reload({waitUntil:'networkidle'});
  assert.equal((await api('/api/deriv/status')).orders[0].status,'UNCERTAIN');
  assert.equal((await api('/__test__/status')).buy_count,before);
  await page.locator('#deriv-disconnect').click();await page.waitForFunction(()=>window.derivStatus?.connected===false);
  await login('demo');
  assert.equal((await api('/api/deriv/status')).orders[0].status,'UNCERTAIN');
  await api('/api/deriv/quote',{symbol:'R_100',side:'UP',stake:1,minutes:2},400);
  assert.equal((await api('/__test__/status')).buy_count,before,'Reconnect is never permission to retry an uncertain purchase');
 });
 assert.deepEqual(evidence.browser_errors,[],'No JavaScript exceptions');
 assert.deepEqual(evidence.external_browser_requests,[],'Application should not attempt external browser requests');
 // Canonical aliases allow the offline DOM inventory to merge evidence for
 // forms and submit buttons without treating labels as stable element IDs.
 for(const form of ['deriv-auth-form','deriv-order-form','risk-config-form']){
  if(evidence.controls[form+' submit'])evidence.controls[form]=evidence.controls[form+' submit'];
 }
 evidence.controls['button:submit:2. Connect selected account']=evidence.controls['deriv-auth-form submit'];
 evidence.controls['button:submit:Get live broker price proposal']=evidence.controls['deriv-order-form submit'];
 evidence.controls['button:submit:Save account risk limits']=evidence.controls['risk-config-form submit'];
 evidence.controls['a:https://developers.deriv.com/:Deriv Developer Portal']={status:'external_link_inspected',test:'HTTPS destination and safe target/rel inspected; external service not navigated or verified.'};
 evidence.worker_scope='Fixture does not start autonomous worker loops. These checks verify actual HTTP control configuration and transitions; signal-to-order worker behavior needs the Python suites.';
 evidence.controls['lab-start-best']={status:'gate_verified_mocked',test:'No validated fixture strategy means activation stays disabled; no forged qualification or claimed successful deployment.'};
 evidence.summary={passed:evidence.tests.length,failed:0,controls:Object.keys(evidence.controls).filter(key=>!key.endsWith(' submit')).length,evidence_entries:Object.keys(evidence.controls).length,
  real_broker_verified:false,orders_submitted_to_broker:0,fixture_purchase_calls:(await api('/__test__/status')).buy_count};
 await persist();
 console.log(`PASS: ${evidence.tests.length} connected-control checks; ${evidence.summary.controls} canonical controls; only offline broker doubles; zero external orders. Report: ${reportPath}`);
})().catch(async error=>{evidence.error=error.stack;console.error(error);process.exitCode=1;await persist();}).finally(async()=>{
 if(browser)await browser.close();
 if(fixture){fixture.kill('SIGINT');await Promise.race([new Promise(r=>fixture.once('exit',r)),pause(3000)]);if(fixture.exitCode===null)fixture.kill('SIGTERM');}
});
