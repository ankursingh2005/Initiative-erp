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
  const context={$,profile:{id:1,role:'Employee'},stream:null,position:null,
    closeModal(){context.stream?.getTracks().forEach(t=>t.stop());context.stream=null;$('camera').srcObject=null;$('capture').disabled=true},
    beginAction:null,checkoutButton:$('checkout'),assignedOutlet:()=> 'Store',outlets:{Store:[0,0]},meters:()=>0,
    setGps(){},syncAttendanceHistory:async()=>{},localStorage:{getItem:()=> 'token'},
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
