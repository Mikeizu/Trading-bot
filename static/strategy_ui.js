'use strict';
// Standalone Naked Forex workspace. Research mode is never a broker order.
const ns=id=>document.getElementById(id);
let nakedReport=null,nakedCSV=null,nakedStatus=null,allScan=null;
let nakedCatalog=null;
const nEsc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nMoney=n=>Number(n||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
async function nakedReq(route,payload){const op=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
 const res=await fetch('/api/strategy/'+route,op);const data=await res.json();if(!res.ok)throw Error(data.error||'Strategy request failed');return data}
function nakedNotice(text,isError=false){ns('naked-feedback').textContent=text;ns('naked-feedback').classList.toggle('naked-alert',isError);if(window.toast)toast(text,isError)}
function loadNakedSymbols(){const sel=ns('naked-symbol');if(!sel)return;
 const list=window.derivStatus?.symbols||[];const old=sel.value;
 if(list.length===0){sel.replaceChildren(new Option('Connect to Deriv in the Broker tab',''));return}
 if(list.map(x=>x.symbol).join('|')===Array.from(sel.options).map(x=>x.value).join('|'))return;
 sel.replaceChildren(...list.map(x=>new Option(`${x.name} (${x.symbol})`,x.symbol)));
 if(list.some(x=>x.symbol===old))sel.value=old;
}
function chooseNakedProfile(){let profile=ns('naked-profile').value;
 const frames=nakedCatalog?.profiles?.[profile]?.timeframes||['5m'];const sel=ns('naked-timeframe'),old=sel.value;
 sel.replaceChildren(...frames.map(f=>new Option(({'1m':'1 minute','5m':'5 minutes','15m':'15 minutes','1h':'1 hour','4h':'4 hours','1d':'Daily','1w':'Weekly','1mo':'Monthly'})[f]||f,f)));
 if(frames.includes(old))sel.value=old;else sel.value=nakedCatalog.profiles[profile].default;
 ns('naked-profile-note').textContent=nakedCatalog.profiles[profile].description;
 updateNakedControls()}
function updateNakedControls(){const f=ns('naked-timeframe').value;
 const canTrade=['1m','5m','15m'].includes(f) && window.derivStatus?.connected===true && window.derivStatus.mode==='demo';
 const mode=ns('naked-action');
 mode.querySelector('option[value="demo_trade"]').disabled=!canTrade;
 if(!canTrade && mode.value==='demo_trade')mode.value='monitor';
 ns('naked-auto-rule').textContent=canTrade?
  'Demo orders can be enabled. Deriv buys are placed only after the next completed candle confirms a pattern; the contract is a short-expiry Rise/Fall option, NOT the book’s original stop-loss trade.':
  'Higher timeframes support broker-data monitoring and simulated PAPER positions only. No weekly/monthly options orders; live automation is disabled.';
 ns('naked-order-settings').hidden=mode.value!=='demo_trade';
 ns('naked-file-panel').hidden=ns('naked-source').value!=='csv';
 ns('naked-data-warning').textContent=({synthetic:'Artificial sample history: useful for checking the software, NOT forecasting markets.',
 deriv:'Authentic broker candles via the official Deriv connection. History may be limited by the broker.',
 csv:'Use your own OHLC data. CSV must contain time/open/high/low/close; timestamps may be Unix seconds or ISO dates.'})[ns('naked-source').value];
 const pat=nakedCatalog?.strategies?.[ns('naked-strategy').value];
 if(pat)ns('naked-strategy-info').textContent=`${pat.name} • Chapter ${pat.chapter} • ${pat.description}. Automated rules are transparent approximations, not author-endorsed signals.`;
}
function nPercent(v){return v==null?'—':Number(v).toFixed(2)+'%'}
function nStats(stats){
 const fields=[['Trades',stats.trades],['Win rate',nPercent(stats.win_rate_pct)],['Loss rate',nPercent(stats.loss_rate_pct)],['Net P&L',nMoney(stats.pnl)],['Return',nPercent(stats.roi_pct)],['Average win',stats.average_winning_trade==null?'—':nMoney(stats.average_winning_trade)],['Average loss',stats.average_losing_trade==null?'—':nMoney(stats.average_losing_trade)],['Expected value / trade',stats.expected_value_per_trade==null?'—':nMoney(stats.expected_value_per_trade)],['Profit factor',stats.profit_factor==null?'Undefined':Number(stats.profit_factor).toFixed(2)],['Maximum drawdown',nPercent(stats.max_drawdown_pct)],['Recovery factor',stats.recovery_factor==null?'Undefined':Number(stats.recovery_factor).toFixed(2)],['Risk-adjusted return',stats.risk_adjusted_return==null?'Undefined':Number(stats.risk_adjusted_return).toFixed(2)],['Exposure',nPercent(stats.exposure_pct)],['Stake turnover',stats.stake_turnover==null?'—':nMoney(stats.stake_turnover)],['Trading costs',stats.trading_costs==null?'—':nMoney(stats.trading_costs)],['Longest win / loss streak',`${stats.longest_winning_streak??'—'} / ${stats.longest_losing_streak??'—'}`],['95% win-rate interval',`${nPercent(stats.wilson_lower_95_pct)} – ${nPercent(stats.wilson_upper_95_pct)}`]];
 return '<div class="naked-stats-grid">'+fields.map(([name,value])=>`<div><span>${nEsc(name)}</span><strong>${nEsc(value??'—')}</strong></div>`).join('')+'</div>';
}
function nCurve(values,label='Backtested theoretical equity curve'){if(!values||values.length<2)return '<p class="muted-description">No completed trades available for a curve.</p>';
 const min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min);
 const d=values.map((p,i)=>(i?'L':'M')+(14+i*790/(values.length-1)).toFixed(2)+','+(180-(p-min)/span*150).toFixed(2)).join(' ');
 return `<svg viewBox="0 0 820 196" preserveAspectRatio="none" role="img" aria-label="${nEsc(label)}"><path d="M14 180H804" stroke="#3b5360" fill="none"/><path d="M14 30H804" stroke="#213a4a" stroke-dasharray="5 6" fill="none"/><path d="${d}" stroke="#43e8bc" stroke-width="2.2" fill="none"/></svg>`;
}
function renderNakedReport(r){nakedReport=r;
 ns('naked-result').hidden=false;
 ns('naked-verdict').textContent=r.research_pass?'RESEARCH THRESHOLDS MET — NOT A FORECAST':'NOT VALIDATED — DEMO TESTING REQUIRED';
 ns('naked-verdict').className='naked-verdict '+(r.research_pass?'naked-conditional':'naked-denied');
 ns('naked-assessment').textContent=r.assessment;
 ns('naked-origin').textContent=`${r.source} · ${r.bars} closed bars · ${r.timeframe} · ${r.model}`+(r.capital_model?` · Capital: ${nMoney(r.capital_model.initial_balance_per_split)} independently allocated to each split; ${nMoney(r.capital_model.combined_funded_capital)} combined funded capital. ${r.capital_model.description||''}`:'');
 ns('naked-breakeven').textContent=`Theoretical break-even: ${r.break_even_win_rate_pct}% at ${r.assumed_payout_pct}% payout; research benchmark: ${r.target_win_rate_pct}% wins. The benchmark is informational and never authorizes execution. Costs and actual payout can change break-even.`;
 ns('naked-in-sample').innerHTML=nStats(r.train);
 ns('naked-out-sample').innerHTML=nStats(r.test);
 ns('naked-equity').innerHTML=nCurve(r.overall.equity_curve);
 ns('naked-drawdown').innerHTML=nCurve((r.overall.drawdown_curve||[]).map(value=>-Number(value)),'Backtested drawdown percentage below prior equity peak');
 const regime=r.market_regime;
 ns('research-regime').textContent=regime?`${regime.regime.replaceAll('_',' ')} · ${(regime.reasons||[]).join(' · ')}. Eligible programmed rules: ${(regime.eligible_strategies||[]).join(', ')||'none'}. Classification is uncertain and is not a forecast.`:'No regime assessment returned.';
 const walk=r.walk_forward;
 ns('research-walk-forward').textContent=walk?`${walk.passed?'Research criteria met':'Research criteria not met'} · ${walk.passes??0} qualifying folds / ${(walk.folds||[]).length} folds. ${walk.method||''}. This is historical simulation, not demo forward testing.`:'Walk-forward evaluation was not returned.';
 ns('research-provenance').textContent=JSON.stringify({provenance:r.provenance||null,capital_model:r.capital_model||null,costs:r.costs||null,validation:r.validation||null,walk_forward:walk||null},null,2);
 const row=r.trades_detail.slice(-50).reverse().map(t=>`<tr><td>${new Date(t.entered_at*1000).toLocaleString()}</td><td class="${t.side==='UP'?'positive':'negative'}">${t.side}</td><td>${t.entry}</td><td>${t.exit}</td><td class="${t.pnl>=0?'positive':'negative'}">${t.pnl>=0?'+':''}${nMoney(t.pnl)}</td></tr>`).join('');
 ns('naked-trades').innerHTML=row||'<tr><td colspan="5" class="empty-row">No completed test trades. This strategy may have no qualifying patterns.</td></tr>';
 ns('naked-report-note').textContent=r.warning;
}
function nCSV(text,frame){const lines=text.replace(/^\uFEFF/,'').replace(/\r/g,'').trim().split('\n');if(lines.length<2)throw Error('CSV file is empty');
 const head=lines.shift().split(',').map(x=>x.trim().toLowerCase());const find=(a)=>head.findIndex(x=>a.includes(x));
 const ids=['open','high','low','close'].map(n=>find([n]));let dateId=find(['time','timestamp','epoch','date','datetime']);
 if(ids.some(i=>i<0)||dateId<0)throw Error('CSV must contain time, open, high, low and close columns.');
 const candles=lines.filter(x=>x.trim()).map((line,j)=>{const fields=line.split(',');let t=fields[dateId]?.trim();let time=/^\d+(\.\d+)?$/.test(t)?Number(t):Date.parse(t)/1000;
 if(time>1e12)time/=1000;if(!Number.isFinite(time))throw Error(`Invalid timestamp at CSV row ${j+2}`);
 return {time:Math.floor(time),open:Number(fields[ids[0]]),high:Number(fields[ids[1]]),low:Number(fields[ids[2]]),close:Number(fields[ids[3]])}});
 if(candles.length>10000)throw Error('CSV maximum is 10,000 rows');if(candles.length<100)throw Error('CSV needs 100 or more candles');
 return candles;
}
function nakedBuild(){return {strategy:ns('naked-strategy').value,profile:ns('naked-profile').value,
 timeframe:ns('naked-timeframe').value,source:ns('naked-source').value,symbol:ns('naked-symbol').value,
 payout:Number(ns('naked-payout').value)/100,stake:Number(ns('naked-stake').value),
 expiry_bars:Number(ns('naked-expiry-bars').value),target_win_rate:Number(ns('naked-target').value),
 commission_per_trade:Number(ns('research-commission').value),spread_bps:Number(ns('research-spread').value),slippage_bps:Number(ns('research-slippage').value),
 candles:nakedCSV};}
async function nakedResearch(){ns('naked-backtest').disabled=true;ns('naked-feedback').textContent='Evaluating completed candles...';
 try{const q=nakedBuild();if(q.source==='csv'&&!nakedCSV)throw Error('Choose a CSV file first');
 const r=await nakedReq('backtest',q);renderNakedReport(r);
 nakedNotice(`Backtest completed: ${r.overall.trades} trades; held-out win rate ${nPercent(r.test.win_rate_pct)}. ${r.research_pass?'Research thresholds met.':'Not validated.'}`);
 }catch(e){nakedNotice(e.message,true)}finally{ns('naked-backtest').disabled=false}}

function nakedInvalidateSelection(){
 allScan=null;
 ns('naked-start-best').disabled=true;
 ns('naked-best-rule').textContent='Comparison needs to be rerun';
 ns('naked-auto-advice').textContent='Inputs changed. Run the seven-strategy comparison again to update the validated choice.';
}
function nakedRenderLeaderboard(r){
 allScan=r;
 ns('naked-export-all').disabled=false;
 ns('naked-auto-verdict').textContent=r.verdict;
 ns('naked-auto-verdict').className='auto-verdict naked-verdict '+(r.auto_eligible?'naked-conditional':'naked-denied');
 ns('naked-auto-source').textContent=`${r.source} • ${r.bars} completed ${r.timeframe} candles • ${r.selection_method} • payout assumption ${r.assumed_payout_pct}% • ${r.deployment_note}`;
 const rows=r.ranked.map(item=>{
  const train=item.train, test=item.holdout;
  const chosen=item.strategy===r.training_candidate;
  const verdict=!item.training_eligible?'Insufficient evidence':chosen?(r.qualified?'SELECTED / RESEARCH PASS':'TRAIN WINNER / HOLDOUT FAIL'):'Not selected';
  const css=chosen?'auto-winner':!item.training_eligible?'auto-unqualified':'';
  return `<tr class="${css}"><td>#${item.rank}</td><td><strong>${nEsc(item.name)}</strong>${chosen?' ★':''}</td><td>${train.trades}</td><td>${nPercent(train.win_rate_pct)}</td><td class="${train.pnl>=0?'positive':'negative'}">${nMoney(train.pnl)}</td><td>${item.training_score==null?'—':item.training_score.toFixed(2)}</td><td>${test.trades}</td><td>${nPercent(test.win_rate_pct)}</td><td class="${test.pnl>=0?'positive':'negative'}">${nMoney(test.pnl)}</td><td><span class="auto-table-tag ${chosen&&r.qualified?'pass':'fail'}">${nEsc(verdict)}</span></td></tr>`;
 });
 ns('naked-leaderboard').innerHTML=rows.join('');
 const winner=r.training_candidate? r.ranked.find(x=>x.strategy===r.training_candidate):null;
 ns('naked-best-rule').textContent=r.winner?`${r.auto_eligible?'Best eligible':'Research leader'}: ${winner.name}`:winner?`Training leader: ${winner.name} (not validated)`:'No qualified training candidate';
 ns('naked-auto-advice').textContent=r.deployment_note;
 ns('naked-start-best').disabled=!r.auto_eligible;
 if(r.auto_eligible){
  const minutes=(r.expiry_bars*({'1m':1,'5m':5,'15m':15,'1h':60,'4h':240,'1d':1440,'1w':10080,'1mo':43200}[r.timeframe]||0));
  const expiry=ns('naked-expiry-minutes');
  if(Array.from(expiry.options).some(o=>Number(o.value)===minutes))expiry.value=String(minutes);
 }
 if(r.winner){ns('naked-strategy').value=r.winner;updateNakedControls()}
}
async function nakedScanAll(){
 ns('naked-scan-all').disabled=true;
 ns('naked-start-best').disabled=true;
 nakedNotice('Comparing all seven strategies on the same completed candles. No orders will be sent.');
 try{
  const query=nakedBuild();
  if(query.source==='csv'&&!nakedCSV)throw Error('Please load OHLC CSV candles first');
  const result=await nakedReq('scan-all',query);
  nakedRenderLeaderboard(result);
  nakedNotice(result.auto_eligible?`Qualified best candidate: ${result.ranked.find(x=>x.strategy===result.winner).name}. Choose your action, then confirm Start Best.`:'All seven strategies compared. None authorized for automatic activation: '+result.verdict);
 }catch(e){nakedInvalidateSelection();nakedNotice(e.message,true)}
 finally{ns('naked-scan-all').disabled=false}
}
async function nakedStartBest(){
 if(!allScan?.auto_eligible)return nakedNotice('Run a qualifying Deriv-history comparison before starting the winner.',true);
 if(!window.derivStatus?.connected)return nakedNotice('Reconnect your broker and scan again.',true);
 const action=ns('naked-action').value;
 const name=allScan.ranked.find(x=>x.strategy===allScan.winner)?.name;
 if(action==='demo_trade'){
  const duration=allScan.expiry_bars*({'1m':1,'5m':5,'15m':15}[allScan.timeframe]||1000);
  if(duration>15)return nakedNotice(`Tested expiry ${duration} minutes is unsupported for automated demo. Select a shorter research holding period (1–15 min), rescan, then try again.`,true);
  if(Number(ns('naked-expiry-minutes').value)!==duration)return nakedNotice(`For faithful demo activation, set broker expiry to ${duration} minutes (research bars × candle minutes).`,true);
 }
 const msg=`Start the automatically selected ${name} strategy on ${allScan.symbol}, timeframe ${allScan.timeframe}? Mode: ${action}. ${action==='demo_trade'?'This WILL submit virtual-money options orders to the connected Deriv DEMO broker.':'No Deriv broker orders will be sent.'} Real-money execution is unavailable in this release.`;
 if(!confirm(msg))return;
 try{
  const response=await nakedReq('start-best',{action,stake:Number(ns('naked-stake').value),expiry_minutes:Number(ns('naked-expiry-minutes').value)});
  nakedRenderStatus(response);
  nakedNotice(`Selected-best automation started: ${name} / ${response.action}`);
 }catch(e){nakedNotice(e.message,true)}
}
function nakedExportAll(){
 if(!allScan)return nakedNotice('Compare all strategies first',true);
 const blob=new Blob([JSON.stringify(allScan,null,2)],{type:'application/json'}),u=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=u;a.download='MIKEIZU_ALL_SEVEN_STRATEGY_COMPARISON.json';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u)
}

function nakedExport(){if(!nakedReport)return nakedNotice('Run a backtest first',true);
 const blob=new Blob([JSON.stringify(nakedReport,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=url;a.download='MIKEIZU_NakedForex_Research_Report.json';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url)}
function nakedRenderStatus(s){nakedStatus=s;ns('naked-engine-pill').textContent=s.active?(s.action==='demo_trade'?'DERIV DEMO AUTO':s.action==='paper_trade'?'VIRTUAL POSITION AUTO':'AUTO MONITOR ACTIVE'):'STOPPED';
 ns('naked-engine-pill').className='naked-engine-pill '+(s.active?'on':'');
 ns('naked-current-rule').textContent=s.active?`${s.strategy.toUpperCase()} · ${s.symbol} · ${s.frame} · ${s.action==='demo_trade'?'DEMO CONTRACTS':s.action==='paper_trade'?'PAPER POSITIONS':'SIGNALS ONLY'}`:'No automated strategy running';
 ns('naked-run-status').textContent=s.error||s.message;
 ns('naked-last').textContent=s.last_check?`Last checked ${new Date(s.last_check*1000).toLocaleString()}`:'No completed-bar scan yet';
 ns('naked-start').disabled=s.active;
 ns('naked-stop').disabled=!s.active;
 ns('naked-paper-balance').textContent=s.paper_balance==null?'PAPER BALANCE —':`$${nMoney(s.paper_balance)} PAPER`;
 ns('naked-paper-rows').innerHTML=(s.paper_positions||[]).slice(0,30).map(p=>`<tr><td>${nEsc(p.symbol)} / ${nEsc(p.timeframe)}</td><td class="${p.side==='UP'?'positive':'negative'}">${nEsc(p.side)}</td><td>${Number(p.entry).toPrecision(6)}</td><td>${Number(p.stop).toPrecision(6)}</td><td>${Number(p.target).toPrecision(6)}</td><td>${nEsc(p.status)}</td><td class="${p.pnl>0?'positive':p.pnl<0?'negative':''}">${p.pnl==null?'—':nMoney(p.pnl)}</td></tr>`).join('')||'<tr><td colspan="7" class="empty-row">No automatic virtual positions recorded.</td></tr>';
 ns('naked-events').innerHTML=(s.events||[]).slice(0,25).map(ev=>`<tr><td>${new Date(ev.event_at*1000).toLocaleString()}</td><td>${nEsc(ev.symbol)} / ${nEsc(ev.timeframe)}</td><td>${nEsc(ev.strategy)}</td><td class="${ev.side==='UP'?'positive':'negative'}">${nEsc(ev.side)}</td><td>${nEsc(ev.action)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty-row">No genuine broker-based strategy signals saved yet.</td></tr>';
}
async function nakedPoll(){try{loadNakedSymbols();nakedRenderStatus(await nakedReq('status'));updateNakedControls()}catch(e){ns('naked-run-status').textContent='Strategy monitor unavailable: '+e.message}}
async function nakedActivate(){const q=nakedBuild();q.action=ns('naked-action').value;q.expiry_minutes=Number(ns('naked-expiry-minutes').value);
 if(!window.derivStatus?.connected)return nakedNotice('Connect your official Deriv account in the Broker tab before enabling the automated monitor.',true);
 const msg=q.action==='demo_trade'?`Start automated purchases on your Deriv DEMO account? Strategy ${q.strategy}, ${q.timeframe}, ${q.symbol}, stake ${q.stake}. These are broker virtual-money options orders, not stop-loss forex trades.`:
 q.action==='paper_trade'?`Start automatic VIRTUAL positions on ${q.symbol} ${q.timeframe}? Next-bar-open entry, pattern-extreme stop, fixed 2R target, risk 0.5% of paper equity with estimated costs. No broker orders will be placed.`:`Start automatic signal monitoring on ${q.symbol} ${q.timeframe}? No trades will be placed.`;
 if(!confirm(msg))return;
 try{const result=await nakedReq('start',q);nakedRenderStatus(result);nakedNotice('Automation activated: '+result.action.toUpperCase())}catch(e){nakedNotice(e.message,true)}
}
async function nakedDeactivate(){try{const result=await nakedReq('stop',{});nakedRenderStatus(result);nakedNotice('Automation stopped; any previously purchased broker contracts remain open until settlement.')}catch(e){nakedNotice(e.message,true)}}
async function initNaked(){try{nakedCatalog=await nakedReq('catalog');const sel=ns('naked-strategy');sel.replaceChildren(...Object.entries(nakedCatalog.strategies).map(([key,item])=>new Option(item.name,key)));chooseNakedProfile();updateNakedControls();await nakedPoll();}catch(e){nakedNotice(e.message,true);return}
 ns('naked-profile').addEventListener('change',chooseNakedProfile);
 ['naked-timeframe','naked-source','naked-strategy','naked-action'].forEach(id=>ns(id).addEventListener('change',updateNakedControls));
 ns('naked-backtest').addEventListener('click',nakedResearch);
 ns('naked-scan-all').addEventListener('click',nakedScanAll);
 ns('naked-start-best').addEventListener('click',nakedStartBest);
 ns('naked-export-all').addEventListener('click',nakedExportAll);
 ['naked-profile','naked-timeframe','naked-source','naked-symbol','naked-payout','naked-target','naked-stake','naked-expiry-bars','research-commission','research-spread','research-slippage'].forEach(id=>ns(id).addEventListener('change',nakedInvalidateSelection));
 ns('naked-report-export').addEventListener('click',nakedExport);
 ns('naked-start').addEventListener('click',nakedActivate);
 ns('naked-stop').addEventListener('click',nakedDeactivate);
 ns('naked-csv-input').addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;
  try{if(file.size>1050000)throw Error('CSV maximum file size is 1 MB');nakedCSV=nCSV(await file.text());
  ns('naked-csv-label').textContent=`${file.name} · ${nakedCSV.length} rows ready for research`;
  nakedInvalidateSelection();nakedNotice(`Loaded ${nakedCSV.length} CSV candles locally.`)}catch(err){nakedCSV=null;nakedNotice(err.message,true)}});
 setInterval(()=>{if(!document.hidden)nakedPoll()},12000);
}
document.addEventListener('DOMContentLoaded',initNaked);
