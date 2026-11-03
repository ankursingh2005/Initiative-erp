const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const nodes=new Map();
function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(type,fn){this[type]=fn;},focus(){},setAttribute(){},setCustomValidity(){},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=(element())})};}
const context={setInterval(){},console,Intl,Date,Number,String,Math,Set,JSON,URL,setTimeout,Blob,
 location:{pathname:'/ems'},localStorage:{getItem(){return null;}},
 document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(){}},
 window:{addEventListener(){},matchMedia(){return {matches:false};}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);


const html=fs.readFileSync('static/ems.html','utf8');
assert.ok(html.includes('data-tab="earnings">W/O &amp; Incentive</button><button data-tab="totalSalary">Total Salary'));
vm.runInContext(`
 state.month='2026-11';state.closed_month=false;
 globalThis.salaryRows=[{user_id:1,employee_id:'IDS-001',name:'Aditi <Test>',profile_id:1,absent:2,working_days:28,net_amount:2000000,actual_gross_earning:2400000,weekoff_availed:3},{user_id:2,employee_id:'IDS-002',name:'Setup Missing',profile_id:null,absent:0,working_days:30,net_amount:999999,actual_gross_earning:0,weekoff_availed:4}];
 currentDistributionRows=()=>salaryRows;
 filtered=()=>salaryRows;
 state.weekoffIncentives=[{user_id:1,incentive:10000}];
 renderWeekoffTable();
`,context);
// 24,000 gross / 30 * 1 credit + 100 incentive = 900 payable; 20,000 + 900 = 20,900.
assert.equal(vm.runInContext('currentTotalSalaryRows()[0].total_salary',context),2090000);
assert.equal(vm.runInContext('currentTotalSalaryRows()[0].weekoff_credit',context),1);
assert.match(nodes.get('totalSalaryRows').innerHTML,/20,900.00/);
assert.match(nodes.get('totalSalaryRows').innerHTML,/Aditi &lt;Test&gt;/);
assert.match(nodes.get('totalSalaryRows').innerHTML,/Setup needed/);
assert.match(nodes.get('totalSalaryTotals').innerHTML,/20,900.00/);
vm.runInContext("weekoffDrafts.set('2026-11:1',20000);renderWeekoffTotals();",context);
assert.match(nodes.get('totalSalaryRows').innerHTML,/21,000.00/);
assert.match(nodes.get('totalSalaryRows').innerHTML,/Unsaved inputs/);
vm.runInContext("salaryRows=[{...salaryRows[0],net_amount:1800000,absent:4,working_days:26}];renderWeekoffTable();",context);
assert.equal(vm.runInContext('currentTotalSalaryRows()[0].total_salary',context),1900000);
vm.runInContext("state.month='2026-12';state.weekoffIncentives=[];renderWeekoffTable();",context);
assert.equal(vm.runInContext('currentTotalSalaryRows()[0].total_salary',context),1880000);
assert.match(nodes.get('totalSalaryNote').textContent,/2026-12/);
vm.runInContext('salaryRows=[];renderWeekoffTable();',context);
assert.match(nodes.get('totalSalaryRows').innerHTML,/colspan="8"/);
console.log('Total Salary source amounts, live updates, month changes, missing setup and totals passed.');
