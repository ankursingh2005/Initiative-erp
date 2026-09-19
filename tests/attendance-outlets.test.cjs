const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
test('refresh loads the new outlet and its GPS coordinates for an existing session',async()=>{
  const element={};
  const context={profile:{id:1,store_id:2,role:'Employee'},liveStores:[],outlets:{},
    attendanceUrl:path=>path,localStorage:{getItem:key=>key==='role'?'Employee':'token'},$:()=>element,
    fetch:async path=>({ok:true,json:async()=>path==='/api/me'?{id:1,store_id:3,role:'Employee'}:[{id:3,name:'New outlet',latitude:26,longitude:81}]})};
  vm.createContext(context);vm.runInContext(fs.readFileSync('static/attendance-outlets.js','utf8'),context);
  await context.refreshAttendanceOutlet();
  assert.equal(context.profile.store_id,3);
  assert.equal(context.outlets['New outlet'][0],26);
  assert.match(element.textContent,/New outlet/);
});
