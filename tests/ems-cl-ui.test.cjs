const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const nodes=new Map();
function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(){},focus(){},setAttribute(){},setCustomValidity(){},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=(element())})};}
const context={console,Intl,Date,Number,String,Math,Set,JSON,URL,setTimeout,setInterval(){},Blob,
 location:{pathname:'/ems'},localStorage:{getItem(){return null;}},
 document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(){}},
 window:{addEventListener(){},matchMedia(){return {matches:false};}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);

assert.equal(vm.runInContext("attendanceStatus(' cl ')",context),'casual_leave');
vm.runInContext("state.month='2026-09'; state.rows=[{user_id:1,name:'Test',employee_id:'TEST',outlet:'Test',joining_date:'2026-01-01',days:[{day:'2026-09-01',status:'casual_leave'},{day:'2026-09-02',status:'absent'},{day:'2026-09-03',status:'weekoff'}]}]; renderAttendanceRecord();",context);
assert.match(nodes.get('attendanceSheetHead').innerHTML,/<th>A<\/th><th>CL<\/th><th>WO<\/th>/);
assert.match(nodes.get('attendanceRecordRows').innerHTML,/value="CL"/);
assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).casual_leave',context),1);
vm.runInContext("attendanceDrafts.set(attendanceKey(1,'2026-09-02'),{status:'casual_leave',value:'CL'});",context);
assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).casual_leave',context),2);
assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).absent',context),0);
console.log('CL parsing, display order and draft totals passed.');
