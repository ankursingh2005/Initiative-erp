const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(){
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{disabled:true,classList:{add(){},remove(){}},style:{}});return elements.get(id)};
  let resolveMedia, posts=0, stopped=0;
  const track={readyState:'live',stop(){stopped++}};
  const media={getTracks:()=>[track],getVideoTracks:()=>[track]};
  Object.assign($('camera'),{readyState:2,videoWidth:480,videoHeight:640,play:async()=>{}});
  const context={$,AbortSignal,profile:{id:1,role:'Employee'},stream:null,position:null,
    closeModal(){context.stream?.getTracks().forEach(t=>t.stop());context.stream=null;$('camera').srcObject=null;$('capture').disabled=true},
    beginAction:null,checkoutButton:$('checkout'),assignedOutlet:()=> 'Store',outlets:{Store:[0,0]},meters:()=>0,
    setGps(){},syncAttendanceHistory:async()=>true,localStorage:{getItem:()=> 'token'},
    navigator:{onLine:true,geolocation:{getCurrentPosition:resolve=>resolve({timestamp:Date.now(),coords:{latitude:0,longitude:0,accuracy:5}})},mediaDevices:{getUserMedia:()=>new Promise(r=>resolveMedia=r)}},
    document:{hidden:false,createElement:()=>({getContext:()=>({drawImage(){}}),toDataURL:()=> 'data:image/jpeg;base64,fresh'})},
    fetch:async()=>{posts++;return {ok:true,json:async()=>({})}}};
  vm.createContext(context);vm.runInContext(fs.readFileSync('static/attendance-capture.js','utf8'),context);
  return {context,$,media,resolve:()=>resolveMedia(media),posts:()=>posts,stopped:()=>stopped};
}
test('cancel while camera permission pending stops late stream and never submits',async()=>{
  const t=setup(), opening=t.context.beginAction('checkout');await Promise.resolve();
  t.$('cancel').onclick();t.resolve();await opening;
  await t.$('capture').onclick();assert.equal(t.posts(),0);assert.equal(t.stopped(),1);
});
test('opening camera does not punch; explicit double tap submits once',async()=>{
  const t=setup(),opening=t.context.beginAction('checkout');await Promise.resolve();t.resolve();await opening;
  assert.equal(t.posts(),0);assert.equal(t.$('capture').disabled,false);
  await Promise.all([t.$('capture').onclick(),t.$('capture').onclick()]);assert.equal(t.posts(),1);
});
test('missing video frame blocks capture',async()=>{
  const t=setup();t.$('camera').videoWidth=0;
  const opening=t.context.beginAction('checkout');await Promise.resolve();t.resolve();await opening;
  await t.$('capture').onclick();assert.equal(t.posts(),0);assert.equal(t.$('capture').disabled,true);
});
test('all attendance inline scripts parse',()=>{
  const html=fs.readFileSync('static/attendance.html','utf8');
  for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
});
async function openCamera(t,action='checkout'){
  const opening=t.context.beginAction(action);await Promise.resolve();t.resolve();await opening;
}
test('account switching while camera open cannot submit',async()=>{
  const t=setup();await openCamera(t);t.context.localStorage.getItem=()=> 'different-token';
  await t.$('capture').onclick();assert.equal(t.posts(),0);
});
test('offline capture cannot create or queue a punch',async()=>{
  const t=setup();await openCamera(t);t.context.navigator.onLine=false;
  await t.$('capture').onclick();assert.equal(t.posts(),0);
});
test('backgrounded page cannot capture',async()=>{
  const t=setup();await openCamera(t);t.context.document.hidden=true;
  await t.$('capture').onclick();assert.equal(t.posts(),0);
});
test('expired capture location blocks submission',async()=>{
  const t=setup();await openCamera(t);t.context.position.timestamp=Date.now()-61000;
  await t.$('capture').onclick();assert.equal(t.posts(),0);
});
test('tracking update cannot replace verified capture coordinates',async()=>{
  const t=setup();await openCamera(t);t.context.position={timestamp:Date.now(),coords:{latitude:80,longitude:80,accuracy:5}};
  let payload;t.context.fetch=async(url,options)=>{payload=JSON.parse(options.body);return {ok:true,json:async()=>({})}};
  await t.$('capture').onclick();assert.equal(payload.latitude,0);assert.equal(payload.longitude,0);
});
test('successful punch with failed refresh reports saved rather than failure',async()=>{
  const t=setup();await openCamera(t);t.context.syncAttendanceHistory=async()=>false;
  await t.$('capture').onclick();assert.equal(t.posts(),1);assert.match(t.$('sync').textContent,/Attendance saved/);
});
test('lost response is not retried automatically',async()=>{
  const t=setup();await openCamera(t);let attempts=0;
  t.context.fetch=async()=>{attempts++;throw new Error('Connection lost')};
  await t.$('capture').onclick();assert.equal(attempts,1);
});
test('invalid GPS and permission denial never enable capture',async()=>{
  for(const gps of [null,{timestamp:Date.now(),coords:{latitude:NaN,longitude:0,accuracy:5}},{timestamp:Date.now(),coords:{latitude:0,longitude:0,accuracy:Infinity}}]){
    const t=setup();t.context.navigator.geolocation.getCurrentPosition=(resolve,reject)=>gps?resolve(gps):reject(new Error('Permission denied'));
    await t.context.beginAction('checkin');assert.equal(t.$('capture').disabled,true);assert.equal(t.posts(),0);
  }
});
test('old history does not invent a punch-out time',()=>{
  const html=fs.readFileSync('static/attendance.html','utf8');
  const source=html.match(/function effectiveOut\(item\)\{[^}]+\}/)[0];
  const ctx={};vm.createContext(ctx);vm.runInContext(source,ctx);
  assert.equal(ctx.effectiveOut({date:'2026-01-01',at:'2026-01-01T10:00:00'}),null);
});
test('corrupt local storage cannot prevent attendance page initialization',()=>{
  const html=fs.readFileSync('static/attendance.html','utf8');
  const source=html.slice(html.indexOf('function readAttendanceCache()'),html.indexOf('function save()'));
  for(const value of ['invalid json','{"records":null}','{"records":[null,5,{"date":"2026-01-01"}]}']){
    const ctx={key:'attendance',localStorage:{getItem:()=>value}};vm.createContext(ctx);vm.runInContext(source,ctx);
    assert.ok(Array.isArray(ctx.readAttendanceCache().records));assert.equal(ctx.readAttendanceCache().queue.length,0);
  }
});
test('late history response cannot erase a newer punch-out',async()=>{
  const html=fs.readFileSync('static/attendance.html','utf8');
  const source=html.slice(html.indexOf('let attendanceRefreshVersion=0;'),html.indexOf('setTimeout(syncAttendanceHistory,1200)'));
  const pending=[],context={AbortSignal,profile:{id:1,username:'employee'},localStorage:{getItem:()=> 'token'},
    state:{records:[],queue:[]},fetch:()=>new Promise(resolve=>pending.push(resolve)),
    assignedOutlet:()=> 'Store',save(){},render(){},updateStages(){},$:()=>({})};
  vm.createContext(context);vm.runInContext(source,context);
  const old=context.syncAttendanceHistory(),fresh=context.syncAttendanceHistory();
  const record={id:1,user_id:1,attendance_date:'2026-09-08',checkin_at:'2026-09-08T10:00:00',checkout_at:'2026-09-08T19:00:00'};
  pending[1]({ok:true,json:async()=>[record]});assert.equal(await fresh,true);
  pending[0]({ok:true,json:async()=>[{...record,checkout_at:null}]});assert.equal(await old,false);
  assert.equal(context.state.records[0].out,'2026-09-08T19:00:00+05:30');
});
