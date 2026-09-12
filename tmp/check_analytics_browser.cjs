const fs=require('fs');
(async()=>{
 const targets=await(await fetch('http://127.0.0.1:9227/json')).json();
 const target=targets.find(x=>x.url.includes('analytics-preview.html'));
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));
 let id=0;const waits=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(waits.has(m.id)){const {resolve,reject}=waits.get(m.id);waits.delete(m.id);m.error?reject(Error(JSON.stringify(m.error))):resolve(m.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;waits.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
 const evaluate=async(expression)=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 await new Promise(r=>setTimeout(r,1800));
 console.log('Desktop:',await evaluate('JSON.stringify({result:document.body.dataset.qa,errors:window.qaErrors,message:document.getElementById("qa-result")?.textContent})'));
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await call('Page.reload',{ignoreCache:true});
 await new Promise(r=>setTimeout(r,1800));
 console.log('Mobile:',await evaluate('JSON.stringify({result:document.body.dataset.qa,errors:qaErrors,message:document.getElementById("qa-result")?.textContent,width:document.documentElement.scrollWidth,viewport:innerWidth})'));
 const screenshot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 fs.writeFileSync('tmp/analytics-mobile.png',Buffer.from(screenshot.data,'base64'));
 await call('Browser.close');ws.close();
})().catch(e=>{console.error(e);process.exit(1);});
