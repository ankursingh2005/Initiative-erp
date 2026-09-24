const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('manager dashboard is enabled for CategoryManager without changing stored role',()=>{
  let role='CategoryManager';const context={localStorage:{getItem:()=>role}};vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('function hasAttendanceDashboard('),html.indexOf('function showAdminLoading(')),context);
  assert.equal(context.hasAttendanceDashboard(),true);
  assert.equal(context.attendanceDashboardTitle(),'Manager Attendance Dashboard');
  role='Employee';assert.equal(context.hasAttendanceDashboard(),false);
  role='Admin';assert.equal(context.attendanceDashboardTitle(),'Admin Attendance Dashboard');
  assert.doesNotMatch(html,/localStorage.setItem\('role', 'Admin'\)/);
});

test('service manager dashboard reuses manager controls with a locked AC Projects category',()=>{
  const context={localStorage:{getItem:()=> 'Service Manager A'}};vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('function hasAttendanceDashboard('),html.indexOf('function showAdminLoading(')),context);
  assert.equal(context.hasAttendanceDashboard(),true);
  assert.equal(context.attendanceDashboardTitle(),'Service Manager Attendance Dashboard');
  assert.ok(html.includes("!['ac_projects','ac_retails'].includes(actor.service_dashboard_category)"));
  assert.ok(html.includes("empCategorySelect.value=category;empCategorySelect.disabled=true"));
});

test('Noor can reach the dashboard using profile permission without an email field',async()=>{
  for(const role of ['Service Manager A','Service Manager B']) for(const allowed of [true,false]){
    const requests=[];
    const context={localStorage:{getItem:key=>key==='role'?role:'token'},
      hasAttendanceDashboard:()=>true,showAdminLoading:()=>{},
      document:{getElementById:()=>({remove(){}}),querySelector:()=>null,body:{classList:{remove(){}}}},
      fetch:async url=>{requests.push(url);return url==='/api/me'
        ?{ok:true,json:async()=>({role,service_dashboard_category:allowed?(role==='Service Manager A'?'ac_projects':'ac_retails'):null})}
        :{ok:false,json:async()=>({detail:'Stop after access check'})};}};
    vm.createContext(context);
    const start=html.indexOf('async function loadAdminSummary()');
    vm.runInContext(html.slice(start,html.indexOf('if(hasAttendanceDashboard()){',start)),context);
    await context.loadAdminSummary();
    assert.deepEqual(requests,allowed?['/api/me','/api/attendance/admin-summary']:['/api/me']);
  }
});

test('CEO Director and Accounts Manager can open the full attendance dashboard',()=>{
  for(const role of ['CEO','Director','AccountsManager']){
    const context={localStorage:{getItem:()=>role}};vm.createContext(context);
    vm.runInContext(html.slice(html.indexOf('function hasAttendanceDashboard('),html.indexOf('function showAdminLoading(')),context);
    assert.equal(context.hasAttendanceDashboard(),true);
    assert.equal(context.attendanceDashboardTitle(),'Attendance Dashboard');
  }
});
