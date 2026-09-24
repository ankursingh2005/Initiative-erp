const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('renamed users retain their saved local attendance by permanent ID',()=>{
  const saved={userId:7,user:'Old name',date:'2026-09-23',at:'09:00'};
  const context={state:{records:[{userId:8,user:'New name',date:saved.date},saved]},profile:{id:7,username:'New name'},today:saved.date};
  vm.createContext(context);
  const start=html.indexOf('function currentAttendance()');
  vm.runInContext(html.slice(start,html.indexOf('function updateStages()',start)),context);
  assert.equal(context.currentAttendance(),saved);
});
test('calendar preserves historical week off after schedule changes',()=>{
  const context={};vm.createContext(context);
  const start=html.indexOf('function monthlyAttendanceCalendar(');
  vm.runInContext(html.slice(start,html.indexOf('async function openAdminRecord(',start)),context);
  const calendar=context.monthlyAttendanceCalendar({weekoff_day:'Wednesday',weekoff_history:[{from:'0001-01-01',day:'Monday'},{from:'2026-09-23',day:'Wednesday'}],history:[{attendance_date:'2026-09-22',checkin_at:'09:00'}]},'2026-09','2026-09-30');
  assert.match(calendar,/data-date="2026-09-21" data-status="Week Off"/);
  assert.match(calendar,/data-date="2026-09-22" data-status="Present"/);
  assert.match(calendar,/data-date="2026-09-23" data-status="Week Off"/);
  assert.match(calendar,/data-date="2026-09-28" data-status="Absent"/);
});

test('dashboard labels prefer saved profile names and show smaller designations or brands',()=>{
  const context={safeText:v=>String(v)};vm.createContext(context);
  const start=html.indexOf('function adminEmployeeLabel(');
  vm.runInContext(html.slice(start,html.indexOf('\n',start)),context);
  const user={username:'MSINGH',display_name:'MAHESH PRATAP SINGH',role:'Employee'};
  for(const category of ['', 'ids_emp'])assert.equal(context.adminEmployeeLabel(user,category),'MAHESH PRATAP SINGH<small class="admin-employee-designation"> / Employee</small>');
  assert.equal(context.adminEmployeeLabel({...user,role:'BrandPartner',promoter_brand:'Samsung'},'brand_pro'),'MAHESH PRATAP SINGH<small class="admin-employee-designation"> / Samsung</small>');
});
