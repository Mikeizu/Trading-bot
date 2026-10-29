'use strict';
// Presentation only. All trading permissions and durable limits are enforced by Python.
const terminalFields=[
 ['risk_per_trade_pct','Risk per order (%)',.5,.01,1,.01],
 ['daily_loss_pct','Daily loss stop (%)',2,.1,5,.1],
 ['weekly_loss_pct','Weekly loss stop (%)',5,.1,10,.1],
 ['max_drawdown_pct','Account drawdown stop (%)',10,.1,20,.1],
 ['max_positions','Maximum open contracts',3,1,3,1],
 ['max_trades_per_day','Maximum new orders / day',12,1,100,1],
 ['max_order_size','Maximum stake (account currency)',50,.01,50,.01],
 ['max_asset_exposure_pct','Maximum asset exposure (%)',1.5,.01,3,.1],
 ['max_group_exposure_pct','Maximum correlated-group exposure (%)',1.5,.01,3,.1],
 ['consecutive_loss_limit','Consecutive losses before cooldown',3,1,5,1],
 ['cooldown_minutes','Loss cooldown (minutes)',60,1,1440,1]
];
let terminalRisk=null,terminalAudit=null,terminalBusy=false,terminalConfigDirty=false,terminalAccountKey='';
const tc=id=>document.getElementById(id);
const tcText=value=>value==null?'Unavailable':String(value);
const tcNum=value=>value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString(undefined,{maximumFractionDigits:2});
const tcTime=value=>value==null?'Not recorded':new Date(Number(value)*1000).toLocaleString();
const tcEsc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function terminalRequest(path,payload){
 const options=payload===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store'};
 const controller=new AbortController();options.signal=controller.signal;
 const timeout=setTimeout(()=>controller.abort(),15000);
 try{const response=await fetch('/api/'+path,options);const data=await response.json();if(!response.ok)throw Error(data.error||'Local operation failed');return data;}
 finally{clearTimeout(timeout);}
}
function terminalMode(s){
 if(!s?.connected)return 'SYNTHETIC · NO BROKER';
 return s.mode==='real'?'REAL ACCOUNT · READ ONLY':'DERIV DEMO · AUTHORIZED SESSION';
}
function terminalRenderRisk(s){
 terminalRisk=s;const risk=s.risk||s;const config=risk.config||{};const connected=Boolean(s.connected);const key=`${s.account_id||''}:${s.mode||''}`;
 if(key!==terminalAccountKey){terminalConfigDirty=false;terminalAccountKey=key;}
 const killed=Boolean(risk.killed||risk.global?.killed||s.halted),decision=risk.last_decision;
 tc('workspace-mode').textContent=terminalMode(s);
 tc('risk-account-label').textContent=connected?`${s.mode==='real'?'READ ONLY':'DEMO'} · ${s.account_id}`:'No broker account connected';
 tc('risk-account-note').textContent=connected?'Risk settings and audit records are isolated to this account and broker mode.':'Connect a demo account for account-specific equity, limits and risk decisions. Synthetic research remains available.';
 tc('risk-state-label').textContent=killed?'EMERGENCY STOP':!connected?'NO ACCOUNT':decision?.allowed?'LAST CHECK PASSED':'GUARDED';
 tc('risk-state-label').classList.toggle('negative',killed);
 tc('global-risk-notice').classList.toggle('halted',killed);
 tc('global-risk-notice').textContent=killed?`Trading stopped: ${risk.kill_reason||risk.global?.kill_reason||s.halt_reason||'Operator emergency stop'}. Existing contracts are not closed. Explicit resume is required.`:!connected?'Research workspace · no broker session. Live execution is unavailable.':s.mode==='real'?'Real account is read-only. Live orders are unavailable in this release.':'Demo session · every order requires current broker information and independent risk approval. Live execution is unavailable.';
 tc('global-kill').textContent=killed?'■ Trading stopped':'■ Stop trading';
 tc('global-kill').setAttribute('aria-label',killed?'Emergency stop is active; stop all new trading again':'Emergency stop all new trading');
 tc('risk-config-fields').disabled=!connected||s.mode!=='demo';
 tc('risk-resume').disabled=s.mode==='real'||!killed;
 if(!terminalConfigDirty){
  terminalFields.forEach(([name])=>{const input=tc('limit-'+name);if(input&&config[name]!=null)input.value=config[name];});
  tc('limit-calendar_policy').value=config.calendar_policy||'required';
 }
 tc('risk-config-note').textContent=!connected?'Connect a demo account to edit its persistent risk limits.':s.mode==='real'?'Real accounts are read-only; demo configuration cannot authorize live orders.':`Saved limits loaded for ${s.account_id}. Changes apply to new orders; hard loss stops and unresolved execution still block trading.`;
 const values=[['Current broker equity',risk.last_equity],['Initial risk baseline',risk.baseline_equity],['Peak equity',risk.peak_equity],['Daily starting equity',risk.day_start_equity],['Weekly starting equity',risk.week_start_equity]];
 tc('risk-equity-summary').innerHTML=values.map(([label,value])=>`<div><span>${label}</span><strong>${tcNum(value)}</strong></div>`).join('')+`<div><span>Reserved / open / uncertain</span><strong>${tcEsc(risk.reservations?.pending??0)} / ${tcEsc(risk.reservations?.open??0)} / ${tcEsc(risk.reservations?.uncertain??0)}</strong></div>`;
 const reasons=decision?.reasons||[];
 tc('risk-decision').textContent=decision?(decision.allowed?'Last order check approved. Approval is not a fill.':'Last order check blocked. ')+(reasons.length?reasons.map(tcText).join(' · '):'No blocking reasons recorded.'):'No order approval recorded for this account. Missing information blocks new broker orders.';
 const calendar=risk.calendar||{};
 tc('risk-calendar').textContent=`${calendar.fresh?'Fresh calendar':'Calendar missing or stale'} · source: ${calendar.source||'not supplied'} · events: ${calendar.event_count??0} · valid until: ${tcTime(calendar.valid_until)} · policy: ${config.calendar_policy||'required'}.`;
}
function terminalSummary(value){
 if(value==null)return 'Unavailable';
 if(typeof value==='object')return JSON.stringify(value);
 return String(value);
}
function terminalRenderHealth(health,capabilities){
 const workerIssue=Object.values(health.workers||{}).some(value=>value===false);
 const attention=health.ok===false||health.audit_integrity===false||workerIssue;
 tc('engine-connectivity').textContent=attention?'LOCAL ENGINE NEEDS ATTENTION':'LOCAL ENGINE RESPONDING';
 tc('system-health-summary').textContent=(attention?'A worker, audit or service check needs attention. Inspect details before enabling automation.':'Local service responded to this health check. This does not verify broker availability or an order fill.')+` Broker: ${health.broker?.connected?health.broker.mode:'disconnected'}. Audit integrity: ${health.audit_integrity===true?'verified locally':health.audit_integrity===false?'failed':'unavailable'}.`;
 tc('system-health-details').textContent=JSON.stringify(health,null,2);
 const entries=capabilities.modes?Object.entries(capabilities.modes).map(([name,status])=>({name,status})):Array.isArray(capabilities)?capabilities:Object.entries(capabilities.features||capabilities.capabilities||capabilities).map(([name,v])=>({name,...(typeof v==='object'&&v!==null?v:{status:v})}));
 tc('capability-summary').replaceChildren();
 entries.forEach(item=>{const p=document.createElement('p');p.className='capability-item';const label=document.createElement('strong');label.textContent=(item.name||item.feature||item.id||'Capability').replaceAll('_',' ');const detail=document.createElement('span');detail.textContent=terminalSummary(item.status??item.available??item.implemented??item.verified??item);p.append(label,detail);tc('capability-summary').append(p);});
 if(capabilities.deployment){const p=document.createElement('p');p.className='disclaimer-tiny';p.textContent=capabilities.deployment;tc('capability-summary').append(p);}
}

function terminalRenderAudit(audit){
 terminalAudit=audit;const events=[...(audit.events||[]),...(audit.risk_events||[])].sort((a,b)=>(b.event_at??b.timestamp??b.created_at??b.time??0)-(a.event_at??a.timestamp??a.created_at??a.time??0));
 tc('audit-export').disabled=false;
 const valid=audit.integrity??audit.valid??audit.audit?.valid;
 tc('audit-integrity').textContent=valid===true?'Local order and risk audit hash chains verified. Records may include multiple accounts; use mode and account identifiers to separate histories.':valid===false?'Audit integrity check failed. Investigate records before permitting new orders.':'Integrity status unavailable; exported data is not independently verified.';
 tc('audit-integrity').classList.toggle('negative',valid===false);
 tc('risk-audit-rows').innerHTML=events.length?events.slice(0,75).map(e=>`<tr><td>${tcEsc(tcTime(e.timestamp??e.created_at??e.event_at??e.time))}</td><td>${tcEsc(e.event_type??e.event??e.action??e.kind??'Event')}</td><td>${tcEsc(e.mode||'')} ${tcEsc(e.account_id||'')}</td><td class="audit-detail">${tcEsc(terminalSummary(e.details??e.detail??e.payload??e.data??e))}</td></tr>`).join(''):'<tr><td colspan="4" class="empty-row">No audit events returned for this account.</td></tr>';
}
async function terminalRefresh(){
 if(terminalBusy)return;terminalBusy=true;
 const results=await Promise.allSettled([terminalRequest('risk/status'),terminalRequest('system/health'),terminalRequest('capabilities'),terminalRequest('audit')]);
 try{
  if(results[0].status==='fulfilled')terminalRenderRisk(results[0].value);
  else{tc('workspace-mode').textContent='ACCOUNT STATUS UNAVAILABLE';tc('global-risk-notice').textContent='Risk service unavailable. Do not enable orders until the service recovers.';tc('global-risk-notice').classList.add('halted');tc('risk-config-fields').disabled=true;tc('risk-resume').disabled=true;tc('risk-state-label').textContent='UNAVAILABLE';}
  if(results[1].status==='fulfilled'&&results[2].status==='fulfilled')terminalRenderHealth(results[1].value,results[2].value);
  else{tc('engine-connectivity').textContent='HEALTH CHECK INCOMPLETE';tc('system-health-summary').textContent='Health or capability information is unavailable. No readiness conclusion can be drawn.';}
  if(results[3].status==='fulfilled')terminalRenderAudit(results[3].value);
  else{tc('audit-integrity').textContent='Audit records unavailable. No integrity check completed.';tc('audit-export').disabled=true;}
 }finally{terminalBusy=false;}
}
async function terminalKill(){
 const button=tc('global-kill');button.disabled=true;
 try{await terminalRequest('risk/kill',{reason:'Operator emergency stop from trading terminal'});toast('Emergency stop saved. No new trades; open contracts remain subject to broker settlement.');await Promise.allSettled([typeof loadDeriv==='function'?loadDeriv():null,typeof nakedPoll==='function'?nakedPoll():null,typeof refresh==='function'?refresh():null]);}
 catch(error){toast('Emergency stop could not be confirmed: '+error.message+'. Stop the server and inspect the broker account.',true);tc('global-risk-notice').textContent='Emergency stop unconfirmed. Stop the server and inspect the broker account; existing contracts may remain open.';tc('global-risk-notice').classList.add('halted');}
 finally{button.disabled=false;await terminalRefresh();}
}
function terminalSetView(advanced){
 document.body.classList.toggle('beginner-view',!advanced);tc('view-toggle').textContent=advanced?'Beginner view':'Advanced view';tc('view-toggle').setAttribute('aria-pressed',String(advanced));
 try{localStorage.setItem('mikeizu-view',advanced?'advanced':'beginner');}catch(_){/* A display preference is optional. Credentials are never stored here. */}
}
document.addEventListener('DOMContentLoaded',()=>{
 const fields=tc('risk-limit-inputs');
 terminalFields.forEach(([name,label,value,min,max,step],index)=>{
  const wrapper=document.createElement('label');wrapper.textContent=label;if(index>5)wrapper.className='advanced-only';
  const input=document.createElement('input');input.type='number';input.id='limit-'+name;input.name=name;input.value=value;input.min=min;input.max=max;input.step=step;input.required=true;wrapper.append(input);fields.append(wrapper);
 });
 const policy=document.createElement('label');policy.className='advanced-only';policy.textContent='Economic-calendar policy';const select=document.createElement('select');select.id='limit-calendar_policy';select.name='calendar_policy';select.add(new Option('Require fresh calendar for orders','required'));select.add(new Option('Explicit synthetic-market exception','synthetic_exempt'));policy.append(select);fields.append(policy);
 tc('risk-config-form').addEventListener('input',()=>{terminalConfigDirty=true;});
 tc('risk-config-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!event.currentTarget.reportValidity())return;
  const payload={};terminalFields.forEach(([name])=>{payload[name]=Number(tc('limit-'+name).value);});payload.calendar_policy=tc('limit-calendar_policy').value;
  if(payload.calendar_policy==='synthetic_exempt'&&terminalRisk?.risk?.config?.calendar_policy!=='synthetic_exempt'&&!confirm('Enable the synthetic-market exception? Fresh calendar checks remain required for forex. Use this only for broker-identified synthetic markets, and review market-specific risks.'))return;
  try{await terminalRequest('risk/config',payload);terminalConfigDirty=false;toast('Account risk limits saved. This does not start trading.');await terminalRefresh();}catch(error){toast(error.message,true);}
 });
 tc('risk-resume-form').addEventListener('submit',async event=>{
  event.preventDefault();const confirmation=tc('risk-resume-phrase').value.trim();if(confirmation!=='RESUME DEMO TRADING')return toast('Type RESUME DEMO TRADING exactly to clear the emergency stop.',true);
  try{await terminalRequest('risk/resume',{confirmation});tc('risk-resume-phrase').value='';toast('Emergency stop cleared. Robots remain stopped and order checks still apply.');await terminalRefresh();}catch(error){toast(error.message,true);}
 });
 tc('risk-calendar-file').addEventListener('change',async event=>{
  const file=event.target.files?.[0];if(!file)return;
  try{
   if(file.size>500000)throw Error('Calendar snapshot exceeds 500 KB.');
   const payload=JSON.parse(await file.text());
   if(!payload||typeof payload!=='object'||Array.isArray(payload)||!Array.isArray(payload.events)||typeof payload.source!=='string'||!Number.isFinite(payload.updated_at)||!Number.isFinite(payload.valid_until))throw Error('Expected JSON object with source, events, updated_at and valid_until in UTC seconds.');
   if(!terminalRisk?.connected||terminalRisk.mode!=='demo')throw Error('Connect a demo account before importing its economic calendar.');
   await terminalRequest('risk/calendar',payload);tc('risk-calendar-import-note').textContent=`Imported ${file.name}. Calendar freshness and event restrictions remain enforced.`;toast('Economic-calendar snapshot imported. No trades started.');await terminalRefresh();
  }catch(error){tc('risk-calendar-import-note').textContent='Import failed: '+error.message;toast(error.message,true);}finally{event.target.value='';}
 });
 tc('global-kill').addEventListener('click',terminalKill);tc('risk-refresh').addEventListener('click',terminalRefresh);
 tc('view-toggle').addEventListener('click',()=>terminalSetView(document.body.classList.contains('beginner-view')));
 let advanced=false;try{advanced=localStorage.getItem('mikeizu-view')==='advanced';}catch(_){}terminalSetView(advanced);
 tc('audit-export').addEventListener('click',()=>{if(!terminalAudit)return;const blob=new Blob([JSON.stringify(terminalAudit,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='MIKEIZU_Account_Audit.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),0);});
 terminalRefresh();setInterval(()=>{if(!document.hidden)terminalRefresh();},15000);
});
