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
test('distance renders zero, stale state and completed reading',()=>{
  const context={safeText:String};
  vm.runInNewContext(html.slice(html.indexOf('function liveDistanceHtml('),html.indexOf('function adminEmployeeLabel(')),context);
  assert.match(context.liveDistanceHtml({current_distance_from_store_m:0,location_tracking_status:'Active'}),/0 m/);
  assert.match(context.liveDistanceHtml({current_distance_from_store_m:42,location_tracking_status:'Inactive'}),/Signal stale/);
  assert.match(context.liveDistanceHtml({current_distance_from_store_m:42,location_tracking_status:'Completed'}),/Completed/);
});
