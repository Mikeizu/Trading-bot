'use strict';
// Standalone Indicator Research workspace. Research mode is never a broker order.
const ns=id=>document.getElementById(id);
let labReport=null,labCSV=null,labStatus=null,allScan=null;
let labCatalog=null;
let labInputRevision=0;
let labAccountKey=null;
const labParameterCache={};
const nEsc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nMoney=n=>Number(n||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
async function labReq(route,payload){const op=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
 const res=await fetch('/api/strategy/'+route,op);const data=await res.json();if(!res.ok)throw Error(data.error||'Strategy request failed');return data}
function labNotice(text,isError=false){ns('lab-feedback').textContent=text;ns('lab-feedback').classList.toggle('lab-alert',isError);if(window.toast)toast(text,isError)}
function loadStrategySymbols(){const sel=ns('lab-symbol');if(!sel)return;
 const list=window.derivStatus?.symbols||[];const old=sel.value;
 if(list.length===0){sel.replaceChildren(new Option('Connect to Deriv in the Broker tab',''));return}
 if(list.map(x=>x.symbol).join('|')===Array.from(sel.options).map(x=>x.value).join('|'))return;
 sel.replaceChildren(...list.map(x=>new Option(`${x.name} (${x.symbol})`,x.symbol)));
 if(list.some(x=>x.symbol===old))sel.value=old;
}
function strategyLabel(key){return labCatalog?.strategies?.[key]?.name||key}
function selectedLabParameters(){
 const values={};
 for(const input of ns('lab-parameters').querySelectorAll('input[data-parameter]')){
  if(!input.checkValidity())throw Error(`Check strategy parameter: ${input.dataset.parameter.replaceAll('_',' ')}`);
  values[input.dataset.parameter]=Number(input.value);
 }
 return values;
}
function renderLabParameters(reset=false){
 const key=ns('lab-strategy').value,item=labCatalog?.strategies?.[key];
 const target=ns('lab-parameters');target.replaceChildren();
 if(!item){ns('lab-rules').textContent='No strategy matches this filter.';return;}
 const saved=reset?{}:(labParameterCache[key]||{});
 for(const [name,spec] of Object.entries(item.parameters||{})){
  const label=document.createElement('label');label.append(document.createTextNode(name.replaceAll('_',' ')));
  const input=document.createElement('input');input.type='number';input.required=true;input.id='lab-param-'+name;
  input.dataset.parameter=name;input.min=String(spec.min);input.max=String(spec.max);input.step=String(spec.step??(spec.type==='int'?1:.1));input.value=String(saved[name]??spec.default);
  input.addEventListener('input',()=>{labParameterCache[key]={...(labParameterCache[key]||{}),[name]:Number(input.value)};labInvalidateSelection();});
  const note=document.createElement('small');note.textContent=spec.description||`Allowed range ${spec.min}–${spec.max}.`;
  label.append(input,note);target.append(label);
 }
 if(reset)delete labParameterCache[key];
 ns('lab-rules').textContent=Array.isArray(item.rules)?item.rules.join(' · '):item.rules||item.description||'No rule summary returned.';
}
function populateStrategyLibrary(){
 const family=ns('lab-family').value,query=ns('lab-search').value.trim().toLowerCase(),select=ns('lab-strategy'),old=select.value;
 const entries=Object.entries(labCatalog?.strategies||{}).filter(([id,item])=>(family==='all'||item.family===family)&&(!query||`${id} ${item.name} ${item.family} ${item.description}`.toLowerCase().includes(query)));
 select.replaceChildren(...entries.map(([id,item])=>new Option(item.name,id)));
 if(entries.some(([id])=>id===old))select.value=old;
 ns('lab-catalog-summary').textContent=`${entries.length} of ${Object.keys(labCatalog?.strategies||{}).length} independently defined strategies · no accuracy guarantee`;
 select.disabled=entries.length===0;ns('lab-backtest').disabled=entries.length===0;
 ns('lab-start').disabled=entries.length===0||Boolean(labStatus?.active);
 if(entries.length===0)select.add(new Option('No matching strategy',''));
 renderLabParameters();updateStrategyControls();
}
function populateSharedStrategyChoices(){
 window.strategyCatalog=labCatalog?.strategies||{};
 for(const id of ['robot-strategy','test-strategy','deriv-strategy']){
  const select=document.getElementById(id);if(!select)continue;const current=select.value;
  select.replaceChildren(...Object.entries(window.strategyCatalog).map(([key,item])=>new Option(item.name,key)));
  if(window.strategyCatalog[current])select.value=current;
 }
}
function chooseStrategyProfile(){let profile=ns('lab-profile').value;
 const frames=labCatalog?.profiles?.[profile]?.timeframes||['5m'];const sel=ns('lab-timeframe'),old=sel.value;
 sel.replaceChildren(...frames.map(f=>new Option(({'1m':'1 minute','5m':'5 minutes','15m':'15 minutes','1h':'1 hour','4h':'4 hours','1d':'Daily','1w':'Weekly','1mo':'Monthly'})[f]||f,f)));
 if(frames.includes(old))sel.value=old;else sel.value=labCatalog.profiles[profile].default;
 ns('lab-profile-note').textContent=labCatalog.profiles[profile].description;
 updateStrategyControls()}
function updateStrategyControls(){const f=ns('lab-timeframe').value;
 const canTrade=['1m','5m','15m'].includes(f) && window.derivStatus?.connected===true && window.derivStatus.mode==='demo';
 const mode=ns('lab-action');
 mode.querySelector('option[value="demo_trade"]').disabled=!canTrade;
 if(!canTrade && mode.value==='demo_trade')mode.value='monitor';
 ns('lab-auto-rule').textContent=!window.derivStatus?.connected?
  'Connect an authorized broker account to monitor authentic candles or run virtual paper positions. Broker purchases require an explicitly connected demo account.':window.derivStatus.mode==='real'?
  'This real account is read-only. Authentic monitoring and separate virtual paper positions are available; broker purchases are disabled.':canTrade?
  'Authorized demo orders require a completed-candle indicator signal, compatible regime, current calendar and independent risk approval. These are short-expiry Rise/Fall options.':
  'This timeframe supports broker-data monitoring and simulated PAPER positions only. No weekly/monthly options orders; live automation is disabled.';
 ns('lab-order-settings').hidden=mode.value!=='demo_trade';
 ns('lab-file-panel').hidden=ns('lab-source').value!=='csv';
 ns('lab-data-warning').textContent=({synthetic:'Artificial sample history: useful for checking the software, NOT forecasting markets.',
 deriv:'Authentic broker candles via the official Deriv connection. History may be limited by the broker.',
 csv:'Use your own OHLC data. CSV must contain time/open/high/low/close; timestamps may be Unix seconds or ISO dates.'})[ns('lab-source').value];
 const item=labCatalog?.strategies?.[ns('lab-strategy').value];
 if(item)ns('lab-strategy-info').textContent=`${item.name} · ${String(item.family||'indicator').replaceAll('_',' ')} · default warm-up ${item.warmup_bars??'not supplied'} closed bars; custom parameters can require more history. ${item.description} Eligible regimes: ${(item.eligible_regimes||[]).join(', ')||'See rules'}.`;
}
function nPercent(v){return v==null?'—':Number(v).toFixed(2)+'%'}
function nStats(stats){
 const fields=[['Trades',stats.trades],['Win rate',nPercent(stats.win_rate_pct)],['Loss rate',nPercent(stats.loss_rate_pct)],['Net P&L',nMoney(stats.pnl)],['Return',nPercent(stats.roi_pct)],['Average win',stats.average_winning_trade==null?'—':nMoney(stats.average_winning_trade)],['Average loss',stats.average_losing_trade==null?'—':nMoney(stats.average_losing_trade)],['Expected value / trade',stats.expected_value_per_trade==null?'—':nMoney(stats.expected_value_per_trade)],['Profit factor',stats.profit_factor==null?'Undefined':Number(stats.profit_factor).toFixed(2)],['Maximum drawdown',nPercent(stats.max_drawdown_pct)],['Recovery factor',stats.recovery_factor==null?'Undefined':Number(stats.recovery_factor).toFixed(2)],['Risk-adjusted return',stats.risk_adjusted_return==null?'Undefined':Number(stats.risk_adjusted_return).toFixed(2)],['Exposure',nPercent(stats.exposure_pct)],['Stake turnover',stats.stake_turnover==null?'—':nMoney(stats.stake_turnover)],['Trading costs',stats.trading_costs==null?'—':nMoney(stats.trading_costs)],['Longest win / loss streak',`${stats.longest_winning_streak??'—'} / ${stats.longest_losing_streak??'—'}`],['95% win-rate interval',`${nPercent(stats.wilson_lower_95_pct)} – ${nPercent(stats.wilson_upper_95_pct)}`]];
 return '<div class="lab-stats-grid">'+fields.map(([name,value])=>`<div><span>${nEsc(name)}</span><strong>${nEsc(value??'—')}</strong></div>`).join('')+'</div>';
}
function nCurve(values,label='Backtested theoretical equity curve'){if(!values||values.length<2)return '<p class="muted-description">No completed trades available for a curve.</p>';
 const min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min);
 const d=values.map((p,i)=>(i?'L':'M')+(14+i*790/(values.length-1)).toFixed(2)+','+(180-(p-min)/span*150).toFixed(2)).join(' ');
 return `<svg viewBox="0 0 820 196" preserveAspectRatio="none" role="img" aria-label="${nEsc(label)}"><path d="M14 180H804" stroke="#3b5360" fill="none"/><path d="M14 30H804" stroke="#213a4a" stroke-dasharray="5 6" fill="none"/><path d="${d}" stroke="#43e8bc" stroke-width="2.2" fill="none"/></svg>`;
}
function renderStrategyReport(r){labReport=r;
 ns('lab-result').hidden=false;
 ns('lab-verdict').textContent=r.research_pass?'RESEARCH THRESHOLDS MET — NOT A FORECAST':'NOT VALIDATED — DEMO TESTING REQUIRED';
 ns('lab-verdict').className='lab-verdict '+(r.research_pass?'lab-conditional':'lab-denied');
 ns('lab-assessment').textContent=r.assessment;
 ns('lab-origin').textContent=`${r.source} · ${r.bars} closed bars · ${r.timeframe} · ${r.model}`+(r.capital_model?` · Capital: ${nMoney(r.capital_model.initial_balance_per_split)} independently allocated to each split; ${nMoney(r.capital_model.combined_funded_capital)} combined funded capital. ${r.capital_model.description||''}`:'');
 ns('lab-breakeven').textContent=`Theoretical break-even: ${r.break_even_win_rate_pct}% at ${r.assumed_payout_pct}% payout; research benchmark: ${r.target_win_rate_pct}% wins. The benchmark is informational and never authorizes execution. Costs and actual payout can change break-even.`;
 ns('lab-in-sample').innerHTML=nStats(r.train);
 ns('lab-out-sample').innerHTML=nStats(r.test);
 ns('lab-equity').innerHTML=nCurve(r.overall.equity_curve);
 ns('lab-drawdown').innerHTML=nCurve((r.overall.drawdown_curve||[]).map(value=>-Number(value)),'Backtested drawdown percentage below prior equity peak');
 const regime=r.market_regime;
 ns('research-regime').textContent=regime?`${regime.regime.replaceAll('_',' ')} · ${(regime.reasons||[]).join(' · ')}. Eligible programmed rules: ${(regime.eligible_strategies||[]).join(', ')||'none'}. Classification is uncertain and is not a forecast.`:'No regime assessment returned.';
 const walk=r.walk_forward;
 ns('research-walk-forward').textContent=walk?`${walk.passed?'Research criteria met':'Research criteria not met'} · ${walk.passes??0} qualifying folds / ${(walk.folds||[]).length} folds. ${walk.method||''}. This is historical simulation, not demo forward testing.`:'Walk-forward evaluation was not returned.';
 ns('research-provenance').textContent=JSON.stringify({provenance:r.provenance||null,capital_model:r.capital_model||null,costs:r.costs||null,validation:r.validation||null,walk_forward:walk||null},null,2);
 const row=r.trades_detail.slice(-50).reverse().map(t=>`<tr><td>${new Date(t.entered_at*1000).toLocaleString()}</td><td class="${t.side==='UP'?'positive':'negative'}">${t.side}</td><td>${t.entry}</td><td>${t.exit}</td><td class="${t.pnl>=0?'positive':'negative'}">${t.pnl>=0?'+':''}${nMoney(t.pnl)}</td></tr>`).join('');
 ns('lab-trades').innerHTML=row||'<tr><td colspan="5" class="empty-row">No completed test trades. This strategy may have no qualifying rule signals.</td></tr>';
 ns('lab-report-note').textContent=r.warning;
}
function nCSV(text){
 const table=[];let row=[],field='',quoted=false;const source=text.replace(/^\uFEFF/,'');
 for(let i=0;i<source.length;i++){
  const char=source[i];
  if(char==='"'){
   if(quoted&&source[i+1]==='"'){field+='"';i++;}else if(!quoted&&field.trim()!=='')throw Error('Invalid quoted CSV field');else quoted=!quoted;
  }else if(char===','&&!quoted){row.push(field);field='';}
  else if((char==='\n'||char==='\r')&&!quoted){if(char==='\r'&&source[i+1]==='\n')i++;row.push(field);field='';if(row.some(value=>value.trim()))table.push(row);row=[];}
  else field+=char;
 }
 if(quoted)throw Error('CSV has an unfinished quoted field');
 row.push(field);if(row.some(value=>value.trim()))table.push(row);
 if(table.length<2)throw Error('CSV file is empty');
 const head=table.shift().map(x=>x.trim().toLowerCase());
 if(new Set(head).size!==head.length||head.some(name=>!name))throw Error('CSV headers must be unique and nonempty');
 const find=(a)=>head.findIndex(x=>a.includes(x));
 const ids=['open','high','low','close'].map(n=>find([n]));let dateId=find(['time','timestamp','epoch','date','datetime']);
 if(ids.some(i=>i<0)||dateId<0)throw Error('CSV must contain time, open, high, low and close columns.');
 let previous=null;
 const candles=table.map((fields,j)=>{
  if(fields.length!==head.length)throw Error(`CSV column count differs at row ${j+2}`);
  const t=fields[dateId].trim();let time;
  if(/^-?\d+(\.\d+)?$/.test(t))time=Number(t);
  else{if(!/(Z|[+-]\d\d:\d\d)$/i.test(t))throw Error(`ISO timestamps need an explicit timezone at row ${j+2}`);time=Date.parse(t)/1000;}
  if(time>1e12)time/=1000;
  if(!Number.isFinite(time)||!Number.isInteger(time)||time< -62135596800||time>253370764800||(previous!==null&&time<=previous))throw Error(`Invalid or unordered timestamp at CSV row ${j+2}`);
  previous=time;
  const values=ids.map(index=>fields[index].trim()===''?NaN:Number(fields[index]));
  if(values.some(value=>!Number.isFinite(value)||value<1e-100||value>1e100))throw Error(`Invalid OHLC price at CSV row ${j+2}`);
  const [open,high,low,close]=values;
  if(low>Math.min(open,close)||high<Math.max(open,close))throw Error(`Inconsistent OHLC values at CSV row ${j+2}`);
  return {time,open,high,low,close};
 });
 if(candles.length>10000)throw Error('CSV maximum is 10,000 rows');if(candles.length<100)throw Error('CSV needs 100 or more candles');
 return candles;
}
function labBuild(){return {strategy:ns('lab-strategy').value,profile:ns('lab-profile').value,
 timeframe:ns('lab-timeframe').value,source:ns('lab-source').value,symbol:ns('lab-symbol').value,
 payout:Number(ns('lab-payout').value)/100,stake:Number(ns('lab-stake').value),
 expiry_bars:Number(ns('lab-expiry-bars').value),target_win_rate:Number(ns('lab-target').value),
 commission_per_trade:Number(ns('research-commission').value),spread_bps:Number(ns('research-spread').value),slippage_bps:Number(ns('research-slippage').value),
 parameters:selectedLabParameters(),regime_filter:ns('lab-regime-filter').checked,candles:labCSV};}
async function labResearch(){ns('lab-backtest').disabled=true;ns('lab-feedback').textContent='Evaluating completed candles...';
 const revision=labInputRevision;
 try{const q=labBuild();if(q.source==='csv'&&!labCSV)throw Error('Choose a CSV file first');
 const r=await labReq('backtest',q);if(revision!==labInputRevision)return labNotice('Research inputs changed during the request. Run again to display matching results.');renderStrategyReport(r);
 labNotice(`Backtest completed: ${r.overall.trades} trades; held-out win rate ${nPercent(r.test.win_rate_pct)}. ${r.research_pass?'Research thresholds met.':'Not validated.'}`);
 }catch(e){labNotice(e.message,true)}finally{ns('lab-backtest').disabled=!labCatalog?.strategies?.[ns('lab-strategy').value]}}

function labInvalidateSelection(){
 labInputRevision++;
 allScan=null;
 ns('lab-start-best').disabled=true;
 ns('lab-best-rule').textContent='Comparison needs to be rerun';
 ns('lab-auto-advice').textContent='Inputs changed. Compare the strategy library again to update the validated choice.';
}
function labRenderLeaderboard(r){
 allScan=r;
 ns('lab-export-all').disabled=false;
 ns('lab-auto-verdict').textContent=r.verdict;
 ns('lab-auto-verdict').className='auto-verdict lab-verdict '+(r.auto_eligible?'lab-conditional':'lab-denied');
 ns('lab-auto-source').textContent=`${r.source} • ${r.bars} completed ${r.timeframe} candles • ${r.selection_method} • payout assumption ${r.assumed_payout_pct}% • ${r.deployment_note}`;
 const rows=r.ranked.map(item=>{
  const train=item.train, test=item.holdout;
  const chosen=item.strategy===r.training_candidate;
  const verdict=!item.training_eligible?'Insufficient evidence':chosen?(r.qualified?'SELECTED / RESEARCH PASS':'TRAIN WINNER / HOLDOUT FAIL'):'Not selected';
  const css=chosen?'auto-winner':!item.training_eligible?'auto-unqualified':'';
  return `<tr class="${css}"><td>#${item.rank}</td><td><strong>${nEsc(item.name)}</strong>${chosen?' ★':''}</td><td>${train.trades}</td><td>${nPercent(train.win_rate_pct)}</td><td class="${train.pnl>=0?'positive':'negative'}">${nMoney(train.pnl)}</td><td>${item.training_score==null?'—':item.training_score.toFixed(2)}</td><td>${test.trades}</td><td>${nPercent(test.win_rate_pct)}</td><td class="${test.pnl>=0?'positive':'negative'}">${nMoney(test.pnl)}</td><td><span class="auto-table-tag ${chosen&&r.qualified?'pass':'fail'}">${nEsc(verdict)}</span></td></tr>`;
 });
 ns('lab-leaderboard').innerHTML=rows.join('');
 const winner=r.training_candidate? r.ranked.find(x=>x.strategy===r.training_candidate):null;
 ns('lab-best-rule').textContent=r.winner?`${r.auto_eligible?'Best eligible':'Research leader'}: ${winner.name}`:winner?`Training leader: ${winner.name} (not validated)`:'No qualified training candidate';
 ns('lab-auto-advice').textContent=r.deployment_note;
 ns('lab-start-best').disabled=!r.auto_eligible;
 if(r.auto_eligible){
  const minutes=(r.expiry_bars*({'1m':1,'5m':5,'15m':15,'1h':60,'4h':240,'1d':1440,'1w':10080,'1mo':43200}[r.timeframe]||0));
  const expiry=ns('lab-expiry-minutes');
  if(Array.from(expiry.options).some(o=>Number(o.value)===minutes))expiry.value=String(minutes);
 }
 if(r.winner){ns('lab-family').value='all';ns('lab-search').value='';populateStrategyLibrary();ns('lab-strategy').value=r.winner;renderLabParameters(true);updateStrategyControls()}
}
async function labScanAll(){
 ns('lab-scan-all').disabled=true;
 ns('lab-start-best').disabled=true;
 const revision=labInputRevision;
 labNotice(`Comparing ${Object.keys(labCatalog?.strategies||{}).length} catalog-default strategies on the same completed candles. No orders will be sent.`);
 try{
  const query=labBuild();
  delete query.parameters; // Each strategy uses its own catalog defaults in this comparison.
  if(query.source==='csv'&&!labCSV)throw Error('Please load OHLC CSV candles first');
  const result=await labReq('scan-all',query);
  if(revision!==labInputRevision)return labNotice('Inputs changed during comparison. Run again before activating a candidate.');
  labRenderLeaderboard(result);
  labNotice(result.auto_eligible?`Qualified research candidate: ${result.ranked.find(x=>x.strategy===result.winner).name}. Choose your action, then explicitly confirm.`:'Strategy library compared. No automatic activation authorized: '+result.verdict);
 }catch(e){labInvalidateSelection();labNotice(e.message,true)}
 finally{ns('lab-scan-all').disabled=false}
}
async function labStartBest(){
 if(!allScan?.auto_eligible)return labNotice('Run a qualifying Deriv-history comparison before starting the winner.',true);
 if(!window.derivStatus?.connected)return labNotice('Reconnect your broker and scan again.',true);
 const action=ns('lab-action').value;
 const name=allScan.ranked.find(x=>x.strategy===allScan.winner)?.name;
 if(action==='demo_trade'){
  const duration=allScan.expiry_bars*({'1m':1,'5m':5,'15m':15}[allScan.timeframe]||1000);
  if(duration>15)return labNotice(`Tested expiry ${duration} minutes is unsupported for automated demo. Select a shorter research holding period (1–15 min), rescan, then try again.`,true);
  if(Number(ns('lab-expiry-minutes').value)!==duration)return labNotice(`For faithful demo activation, set broker expiry to ${duration} minutes (research bars × candle minutes).`,true);
 }
 const msg=`Start the automatically selected ${name} strategy on ${allScan.symbol}, timeframe ${allScan.timeframe}? Mode: ${action}. ${action==='demo_trade'?'This WILL submit virtual-money options orders to the connected Deriv DEMO broker.':'No Deriv broker orders will be sent.'} Real-money execution is unavailable in this release.`;
 if(!confirm(msg))return;
 try{
  const response=await labReq('start-best',{action,stake:Number(ns('lab-stake').value),expiry_minutes:Number(ns('lab-expiry-minutes').value)});
  labRenderStatus(response);
  labNotice(`Selected-best automation started: ${name} / ${response.action}`);
 }catch(e){labNotice(e.message,true)}
}
function labExportAll(){
 if(!allScan)return labNotice('Compare all strategies first',true);
 const blob=new Blob([JSON.stringify(allScan,null,2)],{type:'application/json'}),u=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=u;a.download='MIKEIZU_INDICATOR_STRATEGY_COMPARISON.json';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u)
}

function labExport(){if(!labReport)return labNotice('Run a backtest first',true);
 const blob=new Blob([JSON.stringify(labReport,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=url;a.download='MIKEIZU_Indicator_Research_Report.json';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url)}
function labRenderStatus(s){labStatus=s;ns('lab-engine-pill').textContent=s.active?(s.action==='demo_trade'?'DERIV DEMO AUTO':s.action==='paper_trade'?'VIRTUAL POSITION AUTO':'AUTO MONITOR ACTIVE'):'STOPPED';
 ns('lab-engine-pill').className='lab-engine-pill '+(s.active?'on':'');
 ns('lab-current-rule').textContent=s.active?`${strategyLabel(s.strategy)} · ${s.symbol} · ${s.frame} · ${s.action==='demo_trade'?'DEMO CONTRACTS':s.action==='paper_trade'?'PAPER POSITIONS':'SIGNALS ONLY'}`:'No automated strategy running';
 ns('lab-signal-evidence').textContent=JSON.stringify({strategy:s.strategy,strategy_version:s.strategy_version,parameters:s.parameters,regime:s.regime,calendar:s.calendar,explanation:s.explanation,last_check:s.last_check},null,2);
 ns('lab-run-status').textContent=s.error||s.message;
 ns('lab-last').textContent=s.last_check?`Last checked ${new Date(s.last_check*1000).toLocaleString()}`:'No completed-bar scan yet';
 ns('lab-start').disabled=s.active||!labCatalog?.strategies?.[ns('lab-strategy').value];
 ns('lab-stop').disabled=!s.active;
 ns('lab-paper-balance').textContent=s.paper_balance==null?'PAPER BALANCE —':`$${nMoney(s.paper_balance)} PAPER`;
 ns('lab-paper-rows').innerHTML=(s.paper_positions||[]).slice(0,30).map(p=>`<tr><td>${nEsc(p.symbol)} / ${nEsc(p.timeframe)}</td><td class="${p.side==='UP'?'positive':'negative'}">${nEsc(p.side)}</td><td>${Number(p.entry).toPrecision(6)}</td><td>${Number(p.stop).toPrecision(6)}</td><td>${Number(p.target).toPrecision(6)}</td><td>${nEsc(p.status)}</td><td class="${p.pnl>0?'positive':p.pnl<0?'negative':''}">${p.pnl==null?'—':nMoney(p.pnl)}</td></tr>`).join('')||'<tr><td colspan="7" class="empty-row">No automatic virtual positions recorded.</td></tr>';
 ns('lab-events').innerHTML=(s.events||[]).slice(0,25).map(ev=>`<tr><td>${new Date(ev.event_at*1000).toLocaleString()}</td><td>${nEsc(ev.symbol)} / ${nEsc(ev.timeframe)}</td><td>${nEsc(ev.strategy)}</td><td class="${ev.side==='UP'?'positive':'negative'}">${nEsc(ev.side)}</td><td>${nEsc(ev.action)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty-row">No genuine broker-based strategy signals saved yet.</td></tr>';
}
async function labPoll(){try{const accountKey=`${window.derivStatus?.connected===true}:${window.derivStatus?.account_id||''}:${window.derivStatus?.mode||''}`;if(labAccountKey!==null&&accountKey!==labAccountKey)labInvalidateSelection();labAccountKey=accountKey;loadStrategySymbols();labRenderStatus(await labReq('status'));updateStrategyControls()}catch(e){ns('lab-run-status').textContent='Strategy monitor unavailable: '+e.message}}
async function labActivate(){
 try{
 const q=labBuild();q.action=ns('lab-action').value;q.expiry_minutes=Number(ns('lab-expiry-minutes').value);
 if(!window.derivStatus?.connected)return labNotice('Connect your official Deriv account in the Broker tab before enabling the automated monitor.',true);
 const msg=q.action==='demo_trade'?`Start automated purchases on your Deriv DEMO account? Strategy ${q.strategy}, ${q.timeframe}, ${q.symbol}, stake ${q.stake}. These are broker virtual-money options orders, not stop-loss forex trades.`:
 q.action==='paper_trade'?`Start automatic VIRTUAL positions on ${q.symbol} ${q.timeframe}? Next-bar-open entry, volatility-based stop, fixed 2R target, risk 0.5% of paper equity with estimated costs. No broker orders will be placed.`:`Start automatic signal monitoring on ${q.symbol} ${q.timeframe}? No trades will be placed.`;
 if(!confirm(msg))return;
 const result=await labReq('start',q);labRenderStatus(result);labNotice('Automation activated: '+result.action.toUpperCase());
 }catch(e){labNotice(e.message,true)}
}
async function labDeactivate(){try{const result=await labReq('stop',{});labRenderStatus(result);labNotice('Automation stopped; any previously purchased broker contracts remain open until settlement.')}catch(e){labNotice(e.message,true)}}
async function initStrategy(){try{labCatalog=await labReq('catalog');window.strategyCatalog=labCatalog.strategies;const families=[...new Set(Object.values(labCatalog.strategies).map(item=>item.family||'indicator'))];ns('lab-family').replaceChildren(new Option('All families','all'),...families.map(family=>new Option(family.replaceAll('_',' '),family)));populateStrategyLibrary();populateSharedStrategyChoices();ns('lab-scan-all').textContent=`⌁ Compare all ${Object.keys(labCatalog.strategies).length} strategies`;chooseStrategyProfile();updateStrategyControls();await labPoll();}catch(e){labNotice(e.message,true);return}
 ns('lab-family').addEventListener('change',()=>{populateStrategyLibrary();labInvalidateSelection()});
 ns('lab-search').addEventListener('input',()=>{populateStrategyLibrary();labInvalidateSelection()});
 ns('lab-strategy').addEventListener('change',()=>{renderLabParameters();updateStrategyControls();labInvalidateSelection()});
 ns('lab-reset-parameters').addEventListener('click',()=>{renderLabParameters(true);labInvalidateSelection();labNotice('Selected strategy defaults restored. Rerun research before activation.')});
 ns('lab-regime-filter').addEventListener('change',labInvalidateSelection);
 ns('lab-profile').addEventListener('change',chooseStrategyProfile);
 ['lab-timeframe','lab-source','lab-strategy','lab-action'].forEach(id=>ns(id).addEventListener('change',updateStrategyControls));
 ns('lab-backtest').addEventListener('click',labResearch);
 ns('lab-scan-all').addEventListener('click',labScanAll);
 ns('lab-start-best').addEventListener('click',labStartBest);
 ns('lab-export-all').addEventListener('click',labExportAll);
 ['lab-profile','lab-timeframe','lab-source','lab-symbol','lab-payout','lab-target','lab-stake','lab-expiry-bars','research-commission','research-spread','research-slippage'].forEach(id=>ns(id).addEventListener('change',labInvalidateSelection));
 ['lab-payout','lab-target','lab-stake','research-commission','research-spread','research-slippage'].forEach(id=>ns(id).addEventListener('input',labInvalidateSelection));
 ns('lab-report-export').addEventListener('click',labExport);
 ns('lab-start').addEventListener('click',labActivate);
 ns('lab-stop').addEventListener('click',labDeactivate);
 ns('lab-csv-input').addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;
  try{if(file.size>1050000)throw Error('CSV maximum file size is 1 MB');labCSV=nCSV(await file.text());
  ns('lab-csv-label').textContent=`${file.name} · ${labCSV.length} rows ready for research`;
  labInvalidateSelection();labNotice(`Loaded ${labCSV.length} CSV candles locally.`)}catch(err){labCSV=null;labNotice(err.message,true)}});
 setInterval(()=>{if(!document.hidden)labPoll()},12000);
}
document.addEventListener('DOMContentLoaded',initStrategy);
