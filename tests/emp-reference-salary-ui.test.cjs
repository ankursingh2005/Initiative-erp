const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function setup(){
 const nodes=new Map(),listeners={};
 function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(type,fn){this[type]=fn;},focus(){},setAttribute(){},setCustomValidity(v){this.error=v;},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=element()})};}
 const context={console,Intl,Date,Number,String,Math,Set,Map,JSON,URL,setTimeout,clearTimeout,setInterval(){},Blob,location:{pathname:'/ems'},localStorage:{getItem(){return null;}},window:{addEventListener(){},matchMedia(){return {matches:false};}},document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(name,fn){(listeners[name]??=[]).push(fn);}}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);
 vm.runInContext(`state={month:'2026-09',closed_month:true,rows:[{user_id:1,name:'Synthetic Employee',employee_id:'TEST',category:'ids_emp',employment_category:'Regular',outlet:'Test',profile_id:1}],distribution:[{...salaryDistributionMath.calculateDistribution(1600000,0,0,10000),user_id:1,name:'Synthetic Employee',employee_id:'TEST',profile_id:1,missing_attendance:0,account_no:'000123456789',ifsc_code:'SBIN0001234'}]};renderDistribution();`,context);
 return {context,nodes,listeners,element};
}


test('reference salary is manual, persists through save, and ignores setup and month',async()=>{
 const {context,nodes}=setup();
 vm.runInContext("state.profiles=[{user_id:1,effective_month:'2026-01',basic:9000000,allowances:100000}];renderEmpSalary();",context);
 assert.doesNotMatch(nodes.get('empSalaryRows').innerHTML,/Not entered/);
 assert.doesNotMatch(nodes.get('empSalaryRows').innerHTML,/91000|91,000|Setup needed/);
 vm.runInContext("state.referenceSalaries=[{user_id:1,salary:3500050}];renderEmpSalary();",context);
 assert.match(nodes.get('empSalaryRows').innerHTML,/value="35000.50"/);
 vm.runInContext("state.month='2026-12';renderEmpSalary();",context);
 assert.match(nodes.get('empSalaryRows').innerHTML,/value="35000.50"/);
 const form={dataset:{referenceSalary:'1'},elements:{salary:{value:'42000.25',checkValidity(){return true;}}},reportValidity(){return true;},querySelector(selector){return selector==='button'?this.button:this.status;},button:{},status:{}};
 context.apiCalls=[];
 context.api=async(path,options)=>{context.apiCalls.push({path,options});return {user_id:1,salary:4200025};};
 let scheduled;context.setTimeout=fn=>{scheduled=fn;return 1;};context.clearTimeout=()=>{};
 nodes.get('empSalaryRows').input({target:{closest(){return form;}}});
 assert.equal(context.apiCalls.length,0);
 scheduled();await new Promise(resolve=>setImmediate(resolve));
 vm.runInContext('renderEmpSalary();',context);
 assert.equal(context.apiCalls.length,1);
 assert.equal(context.apiCalls[0].path,'/employee-reference-salaries/1');
 assert.deepEqual(JSON.parse(context.apiCalls[0].options.body),{salary:'42000.25'});
 assert.match(nodes.get('empSalaryRows').innerHTML,/value="42000.25"/);
 assert.match(nodes.get('empSalaryRows').innerHTML,/>Saved</);
 assert.equal(vm.runInContext('state.profiles[0].basic',context),9000000);
});
