const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const scripts=[...fs.readFileSync('static/incentive.html','utf8').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).filter(Boolean);
async function scenario(shared){
 const nodes=new Map(),store=new Map(),original={name:'OCTOBER incentive Data 2026.xlsx'};
 const report={report_version:7};if(!shared)store.set('1',{file:original,report,profitRate:7,incentiveRate:2.5});
 let hasShared=shared,rendered=0;
 function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,addEventListener(type,fn){this[type]=fn;},setAttribute(){},contains(){return false;}});return nodes.get(id);}
 const db={transaction(){const tx={};const op=(fn)=>{const req={};queueMicrotask(()=>{req.result=fn();tx.oncomplete();});return req;};tx.objectStore=()=>({get:key=>op(()=>store.get(key)),put:(v,k)=>op(()=>store.set(k,v)),delete:k=>op(()=>store.delete(k))});return tx;}};
 const context={console,Intl,Date,Promise,JSON,String,Number,Set,RegExp,setTimeout,location:{},localStorage:{getItem:()=> 'token'},document:{getElementById:node,addEventListener(){},createElement:()=>node('temp')},indexedDB:{open(){const req={result:db};queueMicrotask(()=>req.onsuccess());return req;}},File:class{constructor(parts,name){this.name=name;}},fetch:async(url,opts={})=>{
  let data={};if(url==='/api/me')data={id:1};
  else if(url==='/api/incentive/saved'){if(opts.method==='DELETE')hasShared=false;else data={has_data:hasShared,file_name:original.name,report,profit_rate:7,incentive_rate:2.5};}
  return {ok:true,json:async()=>data,blob:async()=>({type:'application/octet-stream'})};
 }};
 vm.createContext(context);scripts.forEach(s=>vm.runInContext(s,context));
 vm.runInContext('renderIncentive=()=>{globalThis.rendered=(globalThis.rendered||0)+1;}',context);
 for(let i=0;i<15;i++)await new Promise(r=>setImmediate(r));
 assert.equal(node('allowMonth').value,'2026-10');assert.equal(context.rendered,1);
 assert.doesNotMatch(node('message').textContent,/Unable to restore/);
 assert.equal(vm.runInContext('selectedFile.name',context),original.name);
 await vm.runInContext('persistUpload()',context);assert.equal(store.get('1').file.name,original.name);
 // A second restore keeps the upload and report available.
 await vm.runInContext('restoreUpload()',context);assert.equal(vm.runInContext('selectedFile.name',context),original.name);
 await vm.runInContext('clearUpload()',context);
 assert.equal(vm.runInContext('selectedFile',context),null);assert.equal(store.has('1'),false);assert.equal(hasShared,false);assert.equal(node('allowMonth').value,'');
 assert.match(node('message').textContent,/cleared/);
}
(async()=>{await scenario(true);await scenario(false);console.log('Shared and local uploads restore, persist through reload, and clear successfully.');})().catch(e=>{console.error(e);process.exitCode=1;});
