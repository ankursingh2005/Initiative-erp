const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('category refresh keeps weekly-off filter and ignores older responses',async()=>{
  const pending=[],metrics=[{},{},{}],body={innerHTML:'',querySelectorAll:()=>[]};
  const panel={querySelector:s=>s==='.admin-weekoff-filter'?{value:'Monday'}:body,querySelectorAll:()=>metrics};
  const context={URLSearchParams,localStorage:{getItem:()=> 'token'},
    safeText:v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),
    fetch:url=>new Promise(resolve=>pending.push({url,resolve})),sortAttendanceByCheckin:rows=>rows};
  vm.createContext(context);
  let helperStart=html.indexOf('function adminEmployeeLabel(');
  vm.runInContext(html.slice(helperStart,html.indexOf('function hasAttendanceDashboard()',helperStart)),context);
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

test('repeated refresh renders small designations and brands without displaying markup',async()=>{
  const body={innerHTML:'',querySelectorAll:()=>[]},metrics=[{},{},{}];
  const panel={querySelector:s=>s==='.admin-weekoff-filter'?null:body,querySelectorAll:()=>metrics};
  const rows=[{user_id:1,username:'Name <unsafe>',role:'Employee',designation:'Team Lead',status:'Present'}, {user_id:2,username:'Promoter',role:'BrandPartner',promoter_brand:'Haier & LG',status:'Present'}];
  const context={URLSearchParams,localStorage:{getItem:()=> 'token'},sortAttendanceByCheckin:r=>r,
    safeText:v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),
    formatTime:()=>'',liveDistanceHtml:()=>'',fetch:async()=>({ok:true,json:async()=>({total:2,present:2,absent:0,rows})})};
  vm.createContext(context);
  let start=html.indexOf('function adminEmployeeLabel(');
  vm.runInContext(html.slice(start,html.indexOf('function hasAttendanceDashboard()',start)),context);
  vm.runInContext(html.slice(html.indexOf('async function refreshAdminOutlet('),html.indexOf('function initializeAdminDashboard(')),context);
  for(const category of ['', 'brand_pro', '']){
    await context.refreshAdminOutlet(panel,'','','',category);
    assert.ok(body.innerHTML.includes('Name &lt;unsafe&gt;<small class="admin-employee-designation"> / Team Lead</small>'));
    assert.ok(body.innerHTML.includes('Promoter<small class="admin-employee-designation"> / Haier &amp; LG</small>'));
    assert.ok(!body.innerHTML.includes('&lt;small'));
    assert.ok(!body.innerHTML.includes('Name <unsafe>'));
  }
});

test('escaped employee label markup is repaired into small designation node',()=>{
  const cell={textContent:'Name <small class="admin-employee-designation"> / Team Lead</small>',innerHTML:''};
  const context={safeText:v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')};
  vm.createContext(context);
  const start=html.indexOf('function adminEmployeeLabel(');
  vm.runInContext(html.slice(start,html.indexOf('function hasAttendanceDashboard()',start)),context);
  context.repairAdminEmployeeLabels({querySelectorAll:()=>[cell]});
  assert.equal(cell.innerHTML,'Name<small class="admin-employee-designation"> / Team Lead</small>');
});
