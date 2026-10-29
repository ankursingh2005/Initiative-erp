const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function setup(){
 const nodes=new Map(),listeners={};
 function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(){},focus(){},setAttribute(){},setCustomValidity(v){this.error=v;},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=element()})};}
 const context={console,Intl,Date,Number,String,Math,Set,Map,JSON,URL,setTimeout,setInterval(){},Blob,location:{pathname:'/ems'},localStorage:{getItem(){return null;}},window:{addEventListener(){},matchMedia(){return {matches:false};}},document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(name,fn){(listeners[name]??=[]).push(fn);}}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);
 vm.runInContext(`state={month:'2026-09',closed_month:true,rows:[{user_id:1,name:'Synthetic Employee',employee_id:'TEST',category:'ids_emp',outlet:'Test',profile_id:1}],distribution:[{...salaryDistributionMath.calculateDistribution(1600000,0,0,10000),user_id:1,name:'Synthetic Employee',employee_id:'TEST',profile_id:1,missing_attendance:0,account_no:'000123456789',ifsc_code:'SBIN0001234'}]};renderDistribution();`,context);
 return {context,nodes,listeners,element};
}

test('manual employee attendance opens the Excel sheet with calculated totals and keeps the selected employee on refresh',()=>{
 const {context,nodes}=setup();
 context.document.querySelector=()=>({click(){}});
 context.document.getElementById('attendanceRecord').scrollIntoView=()=>{};
 vm.runInContext(`state.rows=[{user_id:1,manual_employee:true,name:'Manual Person',employee_id:'M001',outlet:'Main',joining_date:'2026-09-01',counts:{present:0,absent:0,weekoff:0,leave:0},days:[{day:'2026-09-01',status:'unrecorded',entered:false}]},{user_id:2,name:'Other Person',days:[]}];openManualAttendance(1);`,context);
 for(const kind of ['present','absent','weekoff','leave'])assert.match(nodes.get('attendanceRecordRows').innerHTML,new RegExp('data-sheet-count="1:'+kind+'"'));
 assert.doesNotMatch(nodes.get('attendanceRecordRows').innerHTML,/data-total-kind/);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/Manual Person/);
 assert.doesNotMatch(nodes.get('attendanceRecordRows').innerHTML,/Other Person/);
 vm.runInContext('renderAttendanceRecord();',context);
 assert.doesNotMatch(nodes.get('attendanceRecordRows').innerHTML,/Other Person/);
 assert.equal(nodes.get('showAllAttendanceEmployees').hidden,false);
 nodes.get('showAllAttendanceEmployees').onclick();
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/Other Person/);
 assert.equal(nodes.get('showAllAttendanceEmployees').hidden,true);
});
test('distribution renders all 20 cells, leading-zero bank account and totals',()=>{
 const {nodes}=setup(),html=nodes.get('distributionRows').innerHTML;
 assert.equal((html.match(/<td\b/g)||[]).length,20);assert.match(html,/000123456789/);assert.match(html,/SBIN0001234/);assert.match(html,/data-dist-input="other_allowances"/);assert.match(html,/data-dist-save="1"/);
 assert.equal(nodes.get('distributionCount').textContent,1);assert.equal(nodes.get('distributionNet').textContent,new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(16137.98));
});
test('editing allowances updates calculated cells and saves only monthly inputs',async()=>{
 const {context,nodes,listeners,element}=setup(),cells=new Map();
 const row={dataset:{distUser:'1'},querySelector(selector){if(!cells.has(selector))cells.set(selector,element());return cells.get(selector);},querySelectorAll(){return [allowance,advance];}};
 const allowance={...element(),value:'2000.00',dataset:{distInput:'other_allowances'},closest:()=>row};
 const advance={...element(),value:'100.00',dataset:{distInput:'staff_advance'},closest:()=>row};
 for(const fn of listeners.input||[])fn({target:{closest:selector=>selector==='[data-dist-input]'?allowance:null}});
 assert.equal(cells.get('[data-dist-value="net_amount"]').textContent,new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(18122.98));
 assert.equal(cells.get('[data-dist-status]').textContent,'Unsaved inputs');
 vm.runInContext(`globalThis.saved=null;api=async(path,options)=>{saved={path,body:JSON.parse(options.body)};return {message:'Saved'};};refresh=async()=>{};`,context);
 const button={...element(),dataset:{distSave:'1'},closest:()=>row};
 for(const fn of listeners.click||[])await fn({target:{closest:selector=>selector==='[data-dist-save]'?button:null}});
 const saved=vm.runInContext('saved',context);assert.equal(saved.path,'/salary-distribution/1');assert.equal(saved.body.month,'2026-09');assert.equal(saved.body.other_allowances,'2000.00');assert.equal(saved.body.staff_advance,'100.00');assert.equal(Object.keys(saved.body).length,3);
 assert.equal(button.disabled,false);assert.equal(allowance.disabled,false);
});
test('distribution applies existing employee filters and labels missing setup',()=>{
 const {context,nodes}=setup();vm.runInContext(`$('group').value='ac_projects';renderDistribution();`,context);assert.match(nodes.get('distributionRows').innerHTML,/No records/);
 vm.runInContext(`$('group').value='';state.distribution[0].profile_id=null;renderDistribution();`,context);assert.match(nodes.get('distributionRows').innerHTML,/Salary setup needed/);assert.match(nodes.get('distributionRows').innerHTML,/disabled/);
});
test('Expected Basic automatically follows the effective salary setup and recalculates',()=>{
 const {context}=setup();
 vm.runInContext(`state.profiles=[{id:10,user_id:1,effective_month:'2026-08',basic:1900000,allowances:100000},{id:11,user_id:1,effective_month:'2026-10',basic:3000000,allowances:0}];renderDistribution();`,context);
 assert.equal(vm.runInContext('currentDistributionRows()[0].expected_basic',context),2000000);
 assert.equal(vm.runInContext('currentDistributionRows()[0].actual_basic',context),2000000);
 assert.equal(vm.runInContext('currentDistributionRows()[0].profile_id',context),10);
 vm.runInContext('state.profiles[0].basic=2100000;renderDistribution();',context);
 assert.equal(vm.runInContext('currentDistributionRows()[0].expected_basic',context),2200000);
 vm.runInContext("state.month='2026-10';renderDistribution();",context);
 assert.equal(vm.runInContext('currentDistributionRows()[0].expected_basic',context),3000000);
});


test('attendance sheet renders daily codes, totals and locked published rows',()=>{
 const {context,nodes}=setup();
 vm.runInContext(`state.rows=[{user_id:1,name:'Sheet Employee',employee_id:'E001',outlet:'Main',joining_date:'2026-09-01',counts:{present:1,absent:1,weekoff:0,leave:0},days:[{day:'2026-09-01',status:'present',entered:true},{day:'2026-09-02',status:'absent',entered:true}]}];renderAttendanceRecord();`,context);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/value="P"/);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/value="A"/);
 assert.match(nodes.get('attendanceSheetHead').innerHTML,/01/);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/Sheet Employee/);
 vm.runInContext('state.rows[0].published_id=4;renderAttendanceRecord();',context);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/ disabled/);
});

test('attendance sheet accepts codes and preserves unsaved edits across rendering',()=>{
 const {context,nodes}=setup();
 assert.equal(vm.runInContext("attendanceStatus('p')",context),'present');
 assert.equal(vm.runInContext("attendanceStatus('WO')",context),'weekoff');
 assert.equal(vm.runInContext("attendanceStatus('AUTO')",context),undefined);
 assert.equal(vm.runInContext("attendanceStatus('invalid')",context),undefined);
 vm.runInContext(`state.rows=[{user_id:1,name:'Sheet Employee',employee_id:'E001',outlet:'Main',joining_date:'2026-09-01',counts:{present:1,absent:0,weekoff:0,leave:0},days:[{day:'2026-09-01',status:'present',entered:true}]}];attendanceDrafts.set(attendanceKey(1,'2026-09-01'),{value:'L',status:'leave'});renderAttendanceRecord();`,context);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/value="L"/);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/sheet-dirty/);
 assert.equal(nodes.get('attendanceSheetStatus').textContent,'1 unsaved cells');
});


test('editing attendance immediately changes colors and totals and schedules automatic saving',()=>{
 const {context,nodes}=setup();
 context.clearTimeout=()=>{};context.setTimeout=fn=>{context.scheduledSave=fn;return 1;};
 vm.runInContext(`state.rows=[{user_id:1,name:'Test',joining_date:'2026-09-01',counts:{present:0,absent:1,weekoff:0,leave:0},days:[{day:'2026-09-01',status:'absent',entered:true}]}];`,context);
 const classes=new Set(['absent']);const counts={};nodes.get('attendanceRecordRows').querySelector=selector=>counts[selector]??={textContent:''};
 context.input={value:'p',dataset:{sheetUser:'1',sheetDay:'2026-09-01'},setCustomValidity(){},classList:{add:v=>classes.add(v),toggle:(v,on)=>on?classes.add(v):classes.delete(v)}};
 vm.runInContext('stageAttendanceCell(input)',context);
 assert.ok(classes.has('present'));assert.ok(!classes.has('absent'));assert.equal(typeof context.scheduledSave,'function');
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).present',context),1);
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).absent',context),0);
 context.input.value='WO';vm.runInContext('stageAttendanceCell(input)',context);
 assert.ok(classes.has('weekoff'));assert.ok(!classes.has('present'));
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).weekoff',context),1);
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).present',context),0);
});


test('typing a new attendance code selects the old code for replacement',()=>{
 const {context}=setup();let selected=0;
 context.cell={value:'A',select(){selected++;}};
 vm.runInContext("replaceAttendanceCode(cell,'p')",context);assert.equal(selected,1);
 context.cell.value='P';vm.runInContext("replaceAttendanceCode(cell,'a')",context);assert.equal(selected,2);
 context.cell.value='WO';vm.runInContext("replaceAttendanceCode(cell,'p')",context);assert.equal(selected,3);
 context.cell.value='W';vm.runInContext("replaceAttendanceCode(cell,'o')",context);assert.equal(selected,3);
 vm.runInContext("replaceAttendanceCode(cell,'ArrowRight')",context);assert.equal(selected,3);
});


test('weekoff uses distribution gross, four days and monthly incentive',()=>{
 const {context,nodes}=setup();
 vm.runInContext(`state.rows[0].counts={weekoff:1};state.weekoffIncentives=[{user_id:1,incentive:50000}];renderWeekoffTable();`,context);
 const expected=vm.runInContext('Math.round(currentDistributionRows()[0].actual_gross_earning*3/30)+50000',context);
 assert.equal(vm.runInContext('currentWeekoffRows()[0].payable',context),expected);
 assert.match(nodes.get('weekoffRows').innerHTML,/value="500.00"/);
 assert.equal(vm.runInContext('currentWeekoffRows()[0].credit',context),3);
 assert.equal(vm.runInContext('weekoffValues(3000000,4,10000).payable',context),10000);
 assert.equal(vm.runInContext('weekoffValues(3000000,5,0).pay',context),0);
 vm.runInContext("weekoffDrafts.set(state.month+':1',75000)",context);
 assert.equal(vm.runInContext('currentWeekoffRows()[0].incentive',context),75000);
});


test('salary download All includes both categories regardless of dashboard category filter',()=>{
 const {context,nodes}=setup();
 vm.runInContext(`state.rows=[{user_id:1,name:'Contract Employee',category:'ids_emp',employment_category:'Contract',counts:{weekoff:0,present:1,absent:0,leave:0}},{user_id:2,name:'Regular Employee',category:'ids_emp',employment_category:'Regular',counts:{weekoff:0,present:1,absent:0,leave:0}}];state.profiles=[];`,context);
 nodes.get('employmentCategory').value='Contract';
 assert.equal(vm.runInContext("salaryReportRows('').length",context),3);
 assert.equal(vm.runInContext("salaryReportRows('Contract')[1][1]",context),'Contract Employee');
 assert.equal(vm.runInContext("salaryReportRows('Regular')[1][1]",context),'Regular Employee');
 assert.equal(vm.runInContext("salaryReportRows('Regular').length",context),2);
});


test('totals are read-only and count daily entries despite legacy overrides',()=>{
 const {context,nodes}=setup();
 vm.runInContext(`state.rows=[{user_id:1,name:'Test',joining_date:'2026-09-01',counts:{present:20,absent:4,weekoff:3,leave:0},totals_overridden:true,days:[{day:'2026-09-01',status:'absent',entered:true}]}];renderAttendanceRecord();`,context);
 assert.doesNotMatch(nodes.get('attendanceRecordRows').innerHTML,/data-total-kind/);
 assert.match(nodes.get('attendanceRecordRows').innerHTML,/data-sheet-day="2026-09-01"[^>]*value="A"/);
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).present',context),0);
 vm.runInContext("attendanceTotalDrafts.set(state.month+':1',{present:21,absent:3,weekoff:3,leave:0})",context);
 assert.equal(vm.runInContext('attendanceSheetCounts(state.rows[0]).present',context),0);
 assert.equal(vm.runInContext('state.rows[0].days[0].status',context),'absent');
});

test('IDS shows phase 1 net and phase 2 stays separate on the same gross',()=>{
 const {context,nodes}=setup();
 vm.runInContext("state.rows[0].counts={weekoff:2};state.distribution[0].weekoff_availed=2;state.weekoffIncentives=[{user_id:1,incentive:50000}];renderIDS();renderWeekoffTable();",context);
 const phase1=vm.runInContext('currentDistributionRows()[0]',context),phase2=vm.runInContext('currentWeekoffRows()[0]',context);
 assert.equal(phase1.net_amount,phase1.actual_gross_earning-phase1.total_deductions);
 assert.equal(phase2.gross,phase1.actual_gross_earning);
 assert.equal(phase2.pay,Math.round(phase1.actual_gross_earning*2/30));
 assert.equal(phase2.payable,phase2.pay+50000);
 assert.equal(nodes.get('idsNet').textContent,vm.runInContext('money(currentDistributionRows()[0].net_amount)',context));
 assert.match(nodes.get('idsNote').textContent,/Phase 1/);
 assert.equal((nodes.get('idsRows').innerHTML.match(/<td\b/g)||[]).length,20);
 const html=fs.readFileSync('static/ems.html','utf8');
 assert.match(html,/data-tab="earnings"[^>]*>W\/O &amp; Incentive<\/button><button data-tab="ids">IDS/);
 assert.ok(!vm.runInContext('distributionKeys.includes("weekoff_pay")',context));
});
