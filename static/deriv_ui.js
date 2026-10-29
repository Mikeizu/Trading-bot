'use strict';
// Broker controls are separate from the local synthetic trading workspace.
let derivStatus=null, derivQuote=null, derivAccounts=[], derivDurations=null, derivDurationKey="", derivDurationError="";
let derivOrderRevision=0;
const d=id=>document.getElementById(id);
async function derivReq(route,payload){
  const options=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
  const resp=await fetch('/api/deriv/'+route,options);
  const data=await resp.json();
  if(!resp.ok)throw Error(data.error||'Deriv request failed');
  return data;
}
async function derivAction(route,payload,success){
  try{const data=await derivReq(route,payload);if(success)toast(success);await loadDeriv();return data;}
  catch(err){toast(err.message,true);await loadDeriv();return null;}
}
function renderDeriv(s){
  const previousAccount=`${derivStatus?.account_id||''}:${derivStatus?.mode||''}`;
  if(previousAccount!==`${s.account_id||''}:${s.mode||''}`||!s.connected){
    derivOrderRevision++;derivQuote=null;d('deriv-quote-panel').hidden=true;
  }
  derivStatus=s;window.derivStatus=s;
  const connected=s.connected, live=s.mode==='real';
  d('deriv-top-status').textContent=!connected?'DERIV NOT CONNECTED':`DERIV ${s.mode==='real'?'REAL · READ ONLY':s.mode.toUpperCase()} CONNECTED`;
  d('deriv-top-note').textContent=connected?`Account ${s.account_id}. Broker funds and orders appear below; the simulation is separate.`:'No broker account is linked. No orders can be executed.';
  d('deriv-mode-pill').textContent=connected?s.mode.toUpperCase():'DISCONNECTED';
  d('deriv-balance').textContent=connected && s.balance!==null?`${Number(s.balance).toFixed(2)} ${s.currency}`:'—';
  d('deriv-mode').textContent=connected?s.mode.toUpperCase():'Disconnected';
  d('deriv-account-label').textContent=connected?s.account_id:'NO BROKER SESSION';
  d('deriv-auto-state').textContent=s.automation?'RUNNING (DEMO)':'Stopped';
  d('deriv-live-state').textContent='UNAVAILABLE · REAL ACCOUNTS READ ONLY';
  d('deriv-message').textContent=s.error||s.message;
  d('deriv-arm-panel').hidden=!live;
  d('deriv-buy').textContent=live?'Real-money orders unavailable':'Confirm and buy with DEMO funds';
  d('deriv-buy').disabled=live;
  const selected=d('deriv-symbol').value;
  const symbolList=(s.symbols||[]).map(x=>({symbol:x.symbol,name:x.name}));
  if(symbolList.length!==d('deriv-symbol').options.length-1 || symbolList.map(x=>x.symbol).join('|')!==[...d('deriv-symbol').options].slice(1).map(x=>x.value).join('|')){
    d('deriv-symbol').replaceChildren(new Option(connected?'Select a Deriv market':'Connect to see markets',''));
    symbolList.forEach(x=>d('deriv-symbol').add(new Option(`${x.name} (${x.symbol})`,x.symbol)));
    if(symbolList.some(x=>x.symbol===selected))d('deriv-symbol').value=selected;
    else if(symbolList.length)d('deriv-symbol').selectedIndex=1;
  }
  const orders=s.orders||[];
  d('deriv-rows').innerHTML=orders.length?orders.map(o=>`<tr><td>#${o.id}</td><td>${escapeHTML(o.account_id)}</td><td>${escapeHTML(o.mode.toUpperCase())}</td><td>${escapeHTML(o.symbol)}</td><td>${escapeHTML(o.direction)}</td><td>${Number(o.stake).toFixed(2)}</td><td><span class="tag-status">${escapeHTML(o.status)}</span></td><td>${o.pnl==null?'—':Number(o.pnl).toFixed(2)}</td></tr>`).join(''):'<tr><td colspan="8" class="empty-row">No broker order journal entries for this account.</td></tr>';
  if(!connected){derivQuote=null;d('deriv-quote-panel').hidden=true;}
  if(!connected){derivDurations=null;derivDurationKey='';}
  derivUpdateDurationUI();
}
function derivUpdateDurationUI(){
  const label=d('deriv-duration-info');
  const select=d('deriv-minutes');
  const side=d('deriv-side').value;
  const currentSymbol=d('deriv-symbol').value;
  const key=`${derivStatus?.account_id||''}:${currentSymbol}`;
  const valid=derivDurations && derivDurationKey===key ? derivDurations[side] : null;
  for(const option of select.options){
    const n=Number(option.value);
    option.disabled=Array.isArray(valid) && !valid.includes(n);
  }
  const button=d('deriv-order-form').querySelector('[type="submit"]');
  const selectedValid=Array.isArray(valid)&&valid.includes(Number(select.value));
  if(button)button.disabled=(!derivStatus?.connected || derivStatus.mode!=='demo' || !selectedValid);
  if(!derivStatus?.connected){label.textContent='Connect your Deriv account to inspect contract durations.';return;}
  if(!valid){label.textContent=derivDurationError || 'Check supported expiries for this market and direction before requesting a quote.';return;}
  label.textContent=valid.length
    ?`Deriv advertises ${side} expiry minute(s): ${valid.join(', ')}. ${selectedValid?'Quote availability must still be confirmed.':'Select a supported expiry; the current choice is unavailable.'}`
    :`Deriv currently advertises no ${side} Rise/Fall contracts lasting 1–15 minutes on this asset. Choose another asset or direction.`;
}
async function derivCheckDurations(){
  if(!derivStatus?.connected)return toast('Connect a Deriv account before checking supported expiries.',true);
  const symbol=d('deriv-symbol').value;
  if(!symbol)return toast('Select a broker market before checking supported expiries.',true);
  const key=`${derivStatus.account_id}:${symbol}`;
  d('deriv-duration-info').textContent='Checking current Deriv contract offers…';
  derivDurations=null;derivDurationKey='';derivDurationError='';
  try{
    const offers=await derivReq('durations',{symbol});
    if(d('deriv-symbol').value!==symbol || !derivStatus?.connected || derivStatus?.mode!==offers.mode)return;
    derivDurations=offers;derivDurationKey=key;
  }catch(err){
    derivDurationError=`Cannot check offers: ${err.message}. No order should be submitted until checked.`;
    derivUpdateDurationUI();
    return;
  }
  derivUpdateDurationUI();
}
async function loadDeriv(){
  try{renderDeriv(await derivReq('status'));}catch(e){derivStatus=null;window.derivStatus=null;derivQuote=null;d('deriv-quote-panel').hidden=true;d('deriv-top-status').textContent='LOCAL BROKER MODULE OFFLINE';d('deriv-top-note').textContent='Broker status could not be refreshed. Displayed account values may be stale; orders are unavailable until connectivity recovers.';d('deriv-buy').disabled=true;derivUpdateDurationUI();}
}
function derivHandlers(){
  d('deriv-list').addEventListener('click',async()=>{
    const app_id=d('deriv-app-id').value.trim(),token=d('deriv-pat').value.trim();
    if(!app_id||!token)return toast('Enter App ID and PAT first.',true);
    const help=d('deriv-auth-help');
    if(help)help.hidden=true;
    try{
      const r=await derivReq('accounts',{app_id,token});derivAccounts=r.accounts||[];
      d('deriv-account').replaceChildren(new Option('Choose a demo account',''));
      derivAccounts.forEach(a=>d('deriv-account').add(new Option(`${a.account_type.toUpperCase()} · ${a.account_id} · ${a.currency}`,a.account_id)));
      const demo=derivAccounts.find(a=>a.account_type==='demo');if(demo)d('deriv-account').value=demo.account_id;
      toast(`Found ${derivAccounts.length} authorized Deriv accounts`);
    }catch(err){
      derivAccounts=[];
      d('deriv-account').replaceChildren(new Option('Find accounts first',''));
      if(help && /(?:401|authenticat|token|App ID|PAT)/i.test(err.message))help.hidden=false;
      toast(err.message,true);
    }
  });
  d('deriv-auth-form').addEventListener('submit',async e=>{
    e.preventDefault();const account_id=d('deriv-account').value;
    const found=derivAccounts.find(a=>a.account_id===account_id);
    if(!found)return toast('Select an account returned by Deriv',true);
    if(found.account_type==='real' && !confirm('This is a REAL account. It will be read-only: live order execution is unavailable in this release. Connect to inspect its data?'))return;
    const out=await derivAction('connect',{app_id:d('deriv-app-id').value.trim(),token:d('deriv-pat').value.trim(),account_id,mode:found.account_type},'Broker account connected');
    if(out){d('deriv-pat').value='';d('deriv-app-id').value='';derivAccounts=[];d('deriv-account').replaceChildren(new Option('Already connected; disconnect to change accounts',''));}
  });
  d('deriv-disconnect').addEventListener('click',()=>{
    if(confirm('Disconnect the broker session? Any existing Deriv contracts will continue to expiry.')){
      derivOrderRevision++;
      derivAction('disconnect',{},'Broker disconnected');derivQuote=null;d('deriv-quote-panel').hidden=true;
      d('deriv-pat').value='';d('deriv-app-id').value='';derivAccounts=[];d('deriv-account').replaceChildren(new Option('Find accounts first',''));
    }
  });
  d('deriv-refresh').addEventListener('click',async()=>{
    if(!derivStatus?.connected){await loadDeriv();toast('Connect a Deriv account to refresh its balance and markets.',true);return;}
    derivOrderRevision++;
    derivQuote=null;d('deriv-quote-panel').hidden=true;
    try{
      const result=await derivReq('snapshot',{});
      renderDeriv(await derivReq('markets',{}));
      toast(`Broker balance, markets and journal refreshed: ${Number(result.balance).toFixed(2)} ${result.currency}`);
    }catch(error){toast(error.message,true);await loadDeriv();}
  });
  d('deriv-arm').addEventListener('click',async()=>{
    const phrase=d('deriv-arm-phrase').value.trim();
    const out=await derivAction('arm',{phrase},'Live trading armed for one order (45 seconds)');
    if(out)d('deriv-arm-phrase').value='';
  });
  d('deriv-check-durations').addEventListener('click',()=>derivCheckDurations());
  d('deriv-symbol').addEventListener('change',()=>{derivOrderRevision++;derivQuote=null;d('deriv-quote-panel').hidden=true;derivCheckDurations()});
  d('deriv-side').addEventListener('change',()=>{derivOrderRevision++;derivQuote=null;d('deriv-quote-panel').hidden=true;derivUpdateDurationUI()});
  ['deriv-stake','deriv-minutes'].forEach(id=>d(id).addEventListener('input',()=>{derivOrderRevision++;derivQuote=null;d('deriv-quote-panel').hidden=true;derivUpdateDurationUI();}));
  d('deriv-order-form').addEventListener('submit',async e=>{
    e.preventDefault();derivQuote=null;d('deriv-quote-panel').hidden=true;
    const revision=++derivOrderRevision,account_id=derivStatus?.account_id;
    const data={symbol:d('deriv-symbol').value,side:d('deriv-side').value,stake:Number(d('deriv-stake').value),minutes:Number(d('deriv-minutes').value)};
    if(derivDurations && derivDurationKey===`${derivStatus?.account_id}:${data.symbol}` &&
        !derivDurations[data.side].includes(data.minutes))return toast('Unsupported duration: check the available expiries and choose one offered for this direction.',true);
    const p=await derivAction('quote',data);
    if(p&&revision===derivOrderRevision&&derivStatus?.connected&&account_id===derivStatus.account_id&&p.mode===derivStatus.mode){derivQuote=p;d('deriv-quote-panel').hidden=false;
      d('deriv-quote-details').textContent=`${p.mode.toUpperCase()} | ${p.symbol} | ${p.side} | ${p.minutes} minute(s) | Max buy price ${p.ask_price} | Indicative payout ${p.payout??'unavailable'}`;
    }else if(p)toast('Order inputs or account changed while pricing. Request a fresh quote.',true);
  });
  d('deriv-buy').addEventListener('click',async()=>{
    if(!derivQuote)return toast('Request a fresh quote first',true);
    const live=derivQuote.mode==='real';
    if(live)return toast('Real-money execution is unavailable; this account is read-only.',true);
    if(!confirm('Confirm purchase with Deriv DEMO virtual funds?'))return;
    const token=derivQuote.token;derivQuote=null;d('deriv-quote-panel').hidden=true;
    await derivAction('buy',{token},'Demo order submitted to Deriv; inspect its broker status');
  });
  d('deriv-auto-start').addEventListener('click',async()=>{
    if(derivStatus?.mode!=='demo')return toast('Broker robot is only available for Deriv DEMO accounts',true);
    if(!confirm('Start automated DEMO purchases when a completed-candle signal appears?'))return;
    await derivAction('automation',{active:true,symbol:d('deriv-symbol').value,strategy:d('deriv-strategy').value,stake:Number(d('deriv-auto-stake').value)},'Deriv demo robot activated');
  });
  d('deriv-auto-stop').addEventListener('click',()=>derivAction('automation',{active:false},'Demo robot stopped'));
  d('deriv-candle-fetch').addEventListener('click',async()=>{
    try{const r=await derivReq('candles',{symbol:d('deriv-symbol').value});const candles=r.candles||[];
      const last=candles[candles.length-1];d('deriv-candle-info').textContent=last?`Loaded ${candles.length} authentic Deriv 1-minute candles. Last close: ${last.close} at ${new Date(last.time*1000).toLocaleString()}. They are not imported into the simulator.`:'No candle history returned by Deriv.';
    }catch(e){toast(e.message,true)}
  });
}
document.addEventListener('DOMContentLoaded',()=>{derivHandlers();loadDeriv();setInterval(()=>{if(!document.hidden)loadDeriv()},7000)});
