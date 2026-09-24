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
  const context={localStorage:{getItem:()=> 'ServiceManager'}};vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('function hasAttendanceDashboard('),html.indexOf('function showAdminLoading(')),context);
  assert.equal(context.hasAttendanceDashboard(),true);
  assert.equal(context.attendanceDashboardTitle(),'Service Manager Attendance Dashboard');
  assert.ok(html.includes("actor.ac_project_dashboard!==true"));
  assert.ok(html.includes("empCategorySelect.value='ac_projects';empCategorySelect.disabled=true"));
});

test('Noor can reach the dashboard using profile permission without an email field',async()=>{
  for(const allowed of [true,false]){
    const requests=[];
    const context={localStorage:{getItem:key=>key==='role'?'ServiceManager':'token'},
      hasAttendanceDashboard:()=>true,showAdminLoading:()=>{},
      document:{getElementById:()=>({remove(){}}),querySelector:()=>null,body:{classList:{remove(){}}}},
      fetch:async url=>{requests.push(url);return url==='/api/me'
        ?{ok:true,json:async()=>({role:'ServiceManager',ac_project_dashboard:allowed})}
        :{ok:false,json:async()=>({detail:'Stop after access check'})};}};
    vm.createContext(context);
    const start=html.indexOf('async function loadAdminSummary()');
    vm.runInContext(html.slice(start,html.indexOf('if(hasAttendanceDashboard()){',start)),context);
    await context.loadAdminSummary();
    assert.deepEqual(requests,allowed?['/api/me','/api/attendance/admin-summary']:['/api/me']);
  }
});
