'use strict';
const CACHE='mikeizu-tradelab-indicator-terminal-v6';
const SHELL=['/','/styles.css','/app.js','/deriv_ui.js','/strategies_ui.js','/terminal_controls.js','/icon.svg','/manifest.webmanifest'];
self.addEventListener('install',event=>{
 event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
 event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 // Never cache broker credentials, risk decisions, balances, or API responses.
 if(url.origin!==self.location.origin||url.pathname.startsWith('/api/')||event.request.method!=='GET')return;
 if(!SHELL.includes(url.pathname))return;
 event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));
});
