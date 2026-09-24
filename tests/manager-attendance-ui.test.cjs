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
  assert.ok(html.includes("actor.email||''"));
  assert.ok(html.includes("empCategorySelect.value='ac_projects';empCategorySelect.disabled=true"));
});
