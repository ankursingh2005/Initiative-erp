const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('category refresh keeps weekly-off filter and ignores older responses',async()=>{
  const pending=[],metrics=[{},{},{}],body={innerHTML:''};
  const panel={querySelector:s=>s==='.admin-weekoff-filter'?{value:'Monday'}:body,querySelectorAll:()=>metrics};
  const context={URLSearchParams,localStorage:{getItem:()=> 'token'},
    fetch:url=>new Promise(resolve=>pending.push({url,resolve})),sortAttendanceByCheckin:rows=>rows};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('async function refreshAdminOutlet('),html.indexOf('function initializeAdminDashboard(')),context);
  const first=context.refreshAdminOutlet(panel,'2','2026-09-22','2026-09-22','brand_pro');
  const second=context.refreshAdminOutlet(panel,'2','2026-09-22','2026-09-22','ac_retails');
  const query=new URL(pending[1].url,'https://example.test').searchParams;
  assert.equal(query.get('emp_category'),'ac_retails');
  assert.equal(query.get('store_id'),'2');assert.equal(query.get('weekoff_day'),'Monday');
  pending[1].resolve({ok:true,json:async()=>({total:2,present:1,absent:1,rows:[]})});await second;
  pending[0].resolve({ok:true,json:async()=>({total:99,present:99,absent:0,rows:[]})});await first;
  assert.equal(metrics[0].textContent,2);assert.equal(metrics[1].textContent,1);
});
