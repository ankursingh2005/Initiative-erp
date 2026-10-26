const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const nodes=new Map();
function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(){},focus(){},setAttribute(){},setCustomValidity(){},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=(element())})};}
const context={console,Intl,Date,Number,String,Math,Set,JSON,URL,setTimeout,Blob,
 location:{pathname:'/ems'},localStorage:{getItem(){return null;}},
 document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(){}},
 window:{addEventListener(){},matchMedia(){return {matches:false};}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);
vm.runInContext(`state={month:'2026-09',closed_month:true,rows:[{user_id:1,name:'Synthetic employee',employee_id:'TEST',category:'ids_emp',employment_category:'Regular',outlet:'Test',counts:{weekoff:4},profile_id:1,basic:2000000,allowances:625000,net:2270000}],profiles:[{id:1,user_id:1,effective_month:'2026-09',basic:2000000,allowances:500000,deductions:100000,employment_category:'Regular'}],earnings:[],records:[]};$('month').value='2026-09';editSetup(1);render();`,context);
assert.match(nodes.get('profileRows').innerHTML,/Synthetic employee/);
assert.equal(vm.runInContext('salaryReportRows()[0].includes("Expected Basic INR")',context),true);
assert.equal(vm.runInContext('salaryReportRows()[0].includes("EPF INR")',context),false);
console.log('Salary setup rendering and export checks passed.');
// Exercise the employee cards, manual attendance UI and removed-list toggle.
for(const id of ['employeeListDialog','manualAttendanceDialog']){
 const node=context.document.getElementById(id);node.showModal=function(){this.open=true;};node.close=function(){this.open=false;};
}
vm.runInContext(`state.rows[0].manual_employee=true;state.rows[0].missing_attendance=1;state.rows[0].joining_date='2026-09-01';state.rows[0].days=[{day:'2026-09-01',status:'absent',entered:false,note:''}];state.rows.push({user_id:2,name:'Missing Setup',employee_id:'TEST-2',category:'ids_emp',outlet:'Test',counts:{weekoff:4}});showEmployeeList(false);`,context);
assert.match(nodes.get('employeeListRows').innerHTML,/Synthetic employee/);
assert.match(nodes.get('employeeListRows').innerHTML,/Missing Setup/);
vm.runInContext('showEmployeeList(true)',context);
assert.doesNotMatch(nodes.get('employeeListRows').innerHTML,/Synthetic employee/);
assert.match(nodes.get('employeeListRows').innerHTML,/Missing Setup/);
vm.runInContext('openManualAttendance(1)',context);
assert.match(nodes.get('manualAttendanceRows').innerHTML,/Not entered/);
assert.match(nodes.get('manualAttendanceRows').innerHTML,/data-manual-day="2026-09-01"/);
const html=fs.readFileSync('static/ems.html','utf8');
assert.match(html,/<details id="excludedSalaryEmployees">/);
assert.match(html,/Show removed employees/);
assert.doesNotMatch(fs.readFileSync('static/ems.js','utf8'),/\.open=excluded.length>0/);
console.log('Employee lists, manual attendance controls and collapsed removed list checks passed.');
(async()=>{
 vm.runInContext(`globalThis.calls=[];api=async(path,options={})=>{calls.push({path,...options});return {employee_id:'IDS-RBL-26001',message:'Saved'};};`,context);
 nodes.get('manualEmployeeStore').value='7';
 await vm.runInContext('updateManualEmployeeId()',context);
 assert.equal(nodes.get('manualEmployeeId').value,'IDS-RBL-26001');
 assert.equal(vm.runInContext('calls[0].path',context),'/manual-employee-id?store_id=7');
 vm.runInContext('resetSalaryRemovalVerification();salaryRemovalTarget=1;',context);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,true);
 nodes.get('removeSalaryPassword').value='SyntheticPassword123';
 await nodes.get('verifySalaryRemovalPassword').onclick();
 assert.equal(nodes.get('removeSalaryConfirmationStep').hidden,false);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,true);
 nodes.get('removeSalaryConfirmation').value='remove';vm.runInContext('syncSalaryRemovalButton()',context);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,true);
 nodes.get('removeSalaryConfirmation').value='REMOVE';vm.runInContext('syncSalaryRemovalButton()',context);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,false);
 const dialog=nodes.get('removeSalaryDialog');dialog.close=function(){this.open=false;};
 vm.runInContext('refresh=async()=>{};',context);
 await nodes.get('removeSalaryConfirm').onclick();
 const call=vm.runInContext('calls.find(c=>c.path.endsWith("/exclude"))',context);
 assert.equal(JSON.parse(call.body).confirmation,'REMOVE');
 assert.equal(JSON.parse(call.body).password,'SyntheticPassword123');
 assert.equal(nodes.get('removeSalaryPassword').value,'');
 assert.equal(nodes.get('removeSalaryConfirm').disabled,true);
 vm.runInContext('salaryRemovalPermanent=true;resetSalaryRemovalVerification();salaryRemovalTarget=2;',context);
 nodes.get('removeSalaryPassword').value='SyntheticPassword123';
 await nodes.get('verifySalaryRemovalPassword').onclick();
 nodes.get('removeSalaryConfirmation').value='REMOVE';vm.runInContext('syncSalaryRemovalButton()',context);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,true);
 nodes.get('removeSalaryConfirmation').value='DELETE';vm.runInContext('syncSalaryRemovalButton()',context);
 assert.equal(nodes.get('removeSalaryConfirm').disabled,false);
 await nodes.get('removeSalaryConfirm').onclick();
 const deletion=vm.runInContext('calls.find(c=>c.path==="/employees/2")',context);
 assert.equal(deletion.method,'DELETE');assert.equal(JSON.parse(deletion.body).confirmation,'DELETE');
 assert.equal(nodes.get('removeSalaryPassword').value,'');
 assert.match(nodes.get('profileRows').innerHTML,/Delete permanently/);
 console.log('Automatic outlet ID, password + REMOVE and permanent DELETE confirmation checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
