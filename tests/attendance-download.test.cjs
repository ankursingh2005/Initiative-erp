const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
for(const ok of [true,false])test(`employee download ${ok?'uses ID and saves file':'displays server error and restores button'}`,async()=>{
  let clicked=false,message;
  const menu={open:true},button={textContent:'Excel',disabled:false,closest:()=>menu};
  const context={alert:text=>{message=text},localStorage:{getItem:()=> 'token'},encodeURIComponent,
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setTimeout:fn=>fn(),
    document:{body:{appendChild(){}},createElement:()=>({click(){clicked=true},remove(){}})},
    fetch:async path=>{assert.equal(path,'/api/attendance/admin-user-export?user_id=7&format=xlsx');return{ok,status:400,json:async()=>({detail:'Select all categories.'}),blob:async()=>({})}}};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('async function downloadFullUserAttendance('),html.indexOf('function enhanceAdminHistoryCounter')),context);
  await context.downloadFullUserAttendance({dataset:{userId:'7',username:'New name'}},button,'xlsx');
  assert.equal(button.disabled,false);assert.equal(button.textContent,'Excel');assert.equal(clicked,ok);
  if(!ok)assert.equal(message,'Select all categories.');
});
