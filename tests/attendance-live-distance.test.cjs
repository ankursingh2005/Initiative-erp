const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('heartbeat requests fresh GPS only during a shift and ignores fixes after punch-out',()=>{
  let record=null,tick,success,requests=0,uploads=0;
  const context={currentAttendance:()=>record,setInterval:fn=>{tick=fn},
    navigator:{geolocation:{getCurrentPosition:(ok,error,options)=>{requests++;success=ok;assert.equal(options.maximumAge,0)}}},
    window:{addEventListener(){}},document:{addEventListener(){}},
    meters:()=>42,outlets:{Store:[0,0]},assignedOutlet:()=> 'Store',
    $:()=>({}),formatDistance:String,uploadWorkingLocation:()=>uploads++,setGps(){}};
  vm.runInNewContext(html.match(/\(function keepWorkingLocationFresh\(\)\{[\s\S]*?\}\)\(\);/)[0],context);
  tick();assert.equal(requests,0);
  record={at:'2026-09-22'};tick();assert.equal(requests,1);
  tick();assert.equal(requests,1);
  success({coords:{latitude:0,longitude:0}});assert.equal(uploads,1);
  tick();record.out='2026-09-22';success({coords:{latitude:0,longitude:0}});
  assert.equal(uploads,1);tick();assert.equal(requests,2);
});
test('distance stays visible without signal-status badges',()=>{
  const context={safeText:String};
  vm.runInNewContext(html.slice(html.indexOf('function liveDistanceHtml('),html.indexOf('function adminEmployeeLabel(')),context);
  assert.match(context.liveDistanceHtml({current_distance_from_store_m:0,location_tracking_status:'Active'}),/0 m/);
  assert.equal(context.liveDistanceHtml({current_distance_from_store_m:42,location_tracking_status:'Inactive'}),'<span class="live-distance">42 m</span>');
  assert.equal(context.liveDistanceHtml({current_distance_from_store_m:42,location_tracking_status:'Completed'}),'<span class="live-distance">42 m</span>');
});

test('live location upload rejects inaccurate and stale fixes',async()=>{
  const page=fs.readFileSync('static/attendance.html','utf8');
  const calls=[],now=Date.now();
  const context={Date,Number,lastLocationUploadAt:0,currentAttendance:()=>({at:'saved'}),localStorage:{getItem:()=> 'token'},fetch:async(url,options)=>{calls.push(JSON.parse(options.body));return {ok:true}}};
  vm.createContext(context);
  const start=page.indexOf('async function uploadWorkingLocation(');
  vm.runInContext(page.slice(start,page.indexOf('\n',start)),context);
  for(const [accuracy,timestamp] of [[7000,now],[null,now],[0,now],[10,now-180000]])await context.uploadWorkingLocation({timestamp,coords:{latitude:26,longitude:80,accuracy}},7326);
  assert.equal(calls.length,0);
  await context.uploadWorkingLocation({timestamp:now,coords:{latitude:26,longitude:80,accuracy:10}},12);
  assert.equal(calls.length,1);
  assert.equal(calls[0].captured_at,new Date(now).toISOString());
});
