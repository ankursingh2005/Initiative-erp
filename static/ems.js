'use strict';
const base = location.pathname.startsWith('/erp/') ? '/erp' : '';
const $ = id => document.getElementById(id);
const money = v => new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR'}).format((v || 0)/100);
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groups = {ids_emp:'IDS EMP',ac_retails:'AC Retail',ac_projects:'AC Projects'};
let state = {rows:[],profiles:[],earnings:[],records:[]}, selected = null, loading = false;
let attendanceSheetEmployee=null;
function message(text, error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function api(path, options={}) {
  const response = await fetch(base+'/api/ems'+path,{...options,headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json',...options.headers},cache:'no-store'});
  if(response.status===401){location.href=base+'/login';throw Error('Please sign in again');}
  const raw = await response.text();
  let data;try{data=raw?JSON.parse(raw):{};}catch{throw Error('Unable to save or load records (HTTP '+response.status+'). Restart the server if it was recently updated.');}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail || data));
  return data;
}
const employeeSort=new Intl.Collator('en-IN',{numeric:true,sensitivity:'base'});
function compareEmployees(a,b){return employeeSort.compare(String(a.outlet||'Unassigned').trim(),String(b.outlet||'Unassigned').trim())||employeeSort.compare(String(a.name||'').trim(),String(b.name||'').trim())||employeeSort.compare(a.employee_id||'',b.employee_id||'')||a.user_id-b.user_id;}
function filtered(category=$('employmentCategory').value){const query=$('search').value.toLowerCase();return state.rows.filter(r=>(!$('group').value||r.category===$('group').value)&&(!category||r.employment_category===category)&&[r.name,r.employee_id,r.outlet].some(v=>String(v).toLowerCase().includes(query))).sort(compareEmployees);}
function cells(values){return '<tr>'+values.map(v=>'<td>'+v+'</td>').join('')+'</tr>';}
function empty(columns){return `<tr><td colspan="${columns}">No records for this selection.</td></tr>`;}
function render(){
 const rows=filtered(), ids=new Set(rows.map(r=>r.user_id));
 $('employeeCount').textContent=rows.length;$('missingCount').textContent=rows.filter(r=>!r.profile_id).length;
 $('netTotal').textContent=money(rows.filter(r=>!r.published_id).reduce((s,r)=>s+(r.net||0),0));$('publishedCount').textContent=rows.filter(r=>r.published_id).length;
 $('periodNote').textContent=state.closed_month?'Closed month: review attendance and salary before publication.':'Open or future month: provisional totals only. Publication is available after month end.';
 $('monthlyRows').innerHTML=rows.map(r=>cells([`<b>${esc(r.name)}</b><small>${esc(r.employee_id||'ID not assigned')}</small>`,`${esc(r.outlet)}<small>${groups[r.category]}</small>`,r.counts.present,r.counts.absent,r.counts.casual_leave??0,r.counts.weekoff,r.counts.leave,r.profile_id?money(r.basic+r.allowances):'Setup needed',money(r.weekoff_pay||0),money(r.incentive),money(r.bonus),r.profile_id?money(r.deductions):'—',r.profile_id?money(r.net):'—',`${r.manual_employee?'<button data-manual-attendance="'+r.user_id+'">Attendance</button> ':''}<button data-review="${r.user_id}">${r.published_id?'Attendance':'Review'}</button>${r.status==='draft'?'':'<small>'+esc(r.status)+'</small>'}`])).join('')||empty(14);
 renderDistribution();renderIDS();
 renderAttendanceRecord();
 renderWeekoffTable();

 const name=uid=>state.rows.find(r=>r.user_id===uid)?.name||'Employee '+uid;
 $('profileRows').innerHTML=rows.map(employee=>{
 const p=state.profiles.filter(p=>p.user_id===employee.user_id&&p.effective_month<=state.month).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0];
 const availed=employee.weekoff_availed??employee.counts.weekoff,credit=Math.max(0,4-availed);
 const gross=p?p.basic+p.allowances:0,pay=Math.round(gross*credit/30),incentive=p?.setup_incentive||0;
 return cells([esc(employee.employee_id||'ID not assigned'),esc(employee.name),p?esc(p.effective_month):'Setup needed',p?money(gross):'-',esc(p?.employment_category||'-'),esc(p?.account_no||'-'),esc(p?.ifsc_code||'-'),(employee.manual_employee?'<button type="button" data-manual-attendance="'+employee.user_id+'">Attendance</button> ':'')+'<button type="button" data-setup="'+employee.user_id+'"'+(p?' data-profile="'+p.id+'"':'')+'>'+(p?'Edit':'Set up')+'</button> <button type="button" class="exclude-employee" data-exclude="'+employee.user_id+'">Remove</button> <button type="button" class="exclude-employee" data-delete-ems="'+employee.user_id+'">Delete from EMS only</button>']);
 }).join('')||empty(8);
 $('earningRows').innerHTML=state.earnings.filter(r=>ids.has(r.user_id)&&r.month===$('month').value).map(r=>cells([esc(name(r.user_id)),esc(r.month),esc(r.kind),money(r.amount),`${esc(r.note)}<small>${esc(r.status)}</small>${r.status==='approved'&&!state.records.some(p=>p.user_id===r.user_id&&p.month===r.month)?`<button data-void="${r.id}">Void entry</button>`:''}`])).join('')||empty(5);
 $('recordRows').innerHTML=state.records.filter(r=>ids.has(r.user_id)&&r.month===$('month').value).map(r=>cells([esc(r.name),esc(r.month),money(r.basic),money(r.allowances),money(r.incentives),money(r.bonuses),money(r.deductions),money(r.net),`<span class="badge">${esc(r.status)}</span>`,`<button data-slip="${r.id}">Payslip</button> ${r.status==='published'?`<button data-paid="${r.id}">Mark paid</button>`:''}`])).join('')||empty(10);
}
function employeeOptionLabel(row){return (row.employee_id||'ID not assigned (record '+row.user_id+')')+' - '+row.name;}
function showEmployeeOptions(show){const list=$('setupEmployeeOptions');list.hidden=!show;$('setupEmployeeSearch').setAttribute('aria-expanded',String(show));if(show&&window.matchMedia('(max-width:1350px)').matches){const rect=$('setupEmployeeSearch').getBoundingClientRect();list.style.top=(rect.bottom+5)+'px';list.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-340))+'px';}else{list.style.top='';list.style.left='';}}
window.addEventListener('resize',()=>showEmployeeOptions(false));
document.addEventListener('scroll',event=>{if(!event.target.closest?.('#setupEmployeeOptions'))showEmployeeOptions(false);},true);
function filterSetupEmployees(showAll=false){
 const input=$('setupEmployeeSearch'),query=showAll?'':input.value.trim().toLowerCase();
 const matches=state.rows.filter(r=>employeeOptionLabel(r).toLowerCase().includes(query)).sort(compareEmployees);
 $('setupEmployeeOptions').innerHTML=matches.map(r=>'<button type="button" role="option" aria-selected="'+String(String(r.user_id)===$('setupForm').elements.user_id.value)+'" data-employee-option="'+r.user_id+'">'+esc(employeeOptionLabel(r))+'</button>').join('')||'<p>No matching employees</p>';
 const match=state.rows.find(r=>employeeOptionLabel(r)===input.value);
 $('setupForm').elements.user_id.value=match?String(match.user_id):'';
 input.setCustomValidity(match||!input.value?'':'Choose an employee from the dropdown.');
}
$('setupEmployeeSearch').addEventListener('input',()=>{filterSetupEmployees();syncAttendanceWeekoffs();showEmployeeOptions(true);});
$('setupEmployeeSearch').addEventListener('click',()=>{filterSetupEmployees(true);showEmployeeOptions(true);});
$('setupEmployeeToggle').onclick=()=>{const open=$('setupEmployeeOptions').hidden;filterSetupEmployees(true);showEmployeeOptions(open);};
document.addEventListener('click',event=>{
 const option=event.target.closest('[data-employee-option]');
 if(option){event.preventDefault();editSetup(Number(option.dataset.employeeOption));showEmployeeOptions(false);$('setupEmployeeSearch').focus();}
 else if(!event.target.closest('.employee-picker'))showEmployeeOptions(false);
});
$('setupEmployeeSearch').addEventListener('keydown',event=>{
 if(event.key==='ArrowDown'){event.preventDefault();filterSetupEmployees();showEmployeeOptions(true);$('setupEmployeeOptions').querySelector('button')?.focus();}
 if(event.key==='Escape')showEmployeeOptions(false);
});
$('setupEmployeeOptions').addEventListener('keydown',event=>{
 const buttons=Array.from($('setupEmployeeOptions').querySelectorAll('button')),index=buttons.indexOf(document.activeElement);
 if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();buttons[(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}
 if(event.key==='Escape'){showEmployeeOptions(false);$('setupEmployeeSearch').focus();}
});
function syncAttendanceWeekoffs(){
 const form=$('setupForm'),employee=state.rows.find(r=>String(r.user_id)===form.elements.user_id.value);
 $('setupAbsent').value=employee?.counts.absent??0;
 $('setupWorkingDays').value=employee?.counts.present??0;
 form.elements.weekoff_availed.value=employee?.weekoff_availed??employee?.counts.weekoff??0;
 updateWeekoffCredit();
}
function updateWeekoffPay(){
 const form=$('setupForm'),grossPaise=Math.round(Number($('setupGross').value||0)*100);
 form.elements.weekoff_pay.value=(Math.round(grossPaise*Number(form.elements.weekoff_credit.value||0)/30)/100).toFixed(2);
 setupPayable();
}
$('setupGross').addEventListener('input',updateWeekoffPay);
function updateWeekoffCredit(){
 const form=$('setupForm');
 form.elements.weekoff_credit.value=Math.max(0,4-Number(form.elements.weekoff_availed.value||0));
 updateWeekoffPay();
}
$('setupForm').elements.weekoff_availed.addEventListener('input',updateWeekoffCredit);
updateWeekoffCredit();
function setupPayable(){
 const form=$('setupForm');
 $('setupPayable').value=((Math.round(Number(form.elements.weekoff_pay.value||0)*100)+Math.round(Number(form.elements.setup_incentive.value||0)*100))/100).toFixed(2);
}
for(const key of ['weekoff_pay','setup_incentive'])$('setupForm').elements[key].addEventListener('input',setupPayable);
function setupIdentity(){
 const form=$('setupForm');
 $('setupGross').value=((Number(form.elements.basic.value||0)*100+Number(form.elements.allowances.value||0)*100)/100).toFixed(2);
 updateWeekoffPay();
}
function editSetup(uid,profileId){
 const employee=state.rows.find(r=>r.user_id===uid);
 $('setupEmployeeSearch').value=employee?employeeOptionLabel(employee):'';filterSetupEmployees();
 const form=$('setupForm');form.elements.user_id.value=String(uid);
 const profile=profileId?state.profiles.find(p=>p.id===profileId):state.profiles.filter(p=>p.user_id===uid&&p.effective_month<=$('month').value).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0];
 form.elements.effective_month.value=$('month').value;
 for(const key of ['basic','allowances','deductions'])form.elements[key].value=profile?(profile[key]/100).toFixed(2):(key==='basic'?'':'0');
 for(const key of ['weekoff_pay','setup_incentive'])form.elements[key].value=((profile?.[key]||0)/100).toFixed(2);
 setupPayable();
 syncAttendanceWeekoffs();
 form.elements.employment_category.value=profile?.employment_category||'';
 form.elements.account_no.value=profile?.account_no||'';
 form.elements.ifsc_code.value=profile?.ifsc_code||'';
 form.elements.divisor.value='30';
 form.elements.paid_weekoff.value='true';form.elements.paid_leave.value='false';
 setupIdentity();

}
$('setupForm').elements.user_id.onchange=()=>editSetup(Number($('setupForm').elements.user_id.value));
for(const key of ['basic','allowances'])$('setupForm').elements[key].addEventListener('input',setupIdentity);
document.addEventListener('click',event=>{const button=event.target.closest('[data-setup]');if(!button)return;if($('employeeListDialog').open)$('employeeListDialog').close();document.querySelector('[data-tab="setup"]').click();editSetup(Number(button.dataset.setup),Number(button.dataset.profile)||null);$('setupForm').scrollIntoView({behavior:'smooth',block:'center'});$('setupGross').focus({preventScroll:true});});
async function refresh(){if(loading)return;loading=true;$('refresh').disabled=true;$('month').disabled=true;message('Loading employee and attendance records…');try{
 const month=$('month').value;if(!month)throw Error('Choose a month');
 const [preview,profiles,earnings,records,excluded,distribution,weekoffIncentives]=await Promise.all([api('/salary-preview?month='+encodeURIComponent(month)),api('/salary-profiles'),api('/earnings'),api('/payroll'),api('/excluded-employees'),api('/salary-distribution?month='+encodeURIComponent(month)),api('/weekoff-incentives?month='+encodeURIComponent(month))]);
 state={...preview,profiles,earnings,records,excluded,weekoffIncentives,distribution:distribution.rows};
 $('excludedCount').textContent=excluded.length;
 $('excludedToggleLabel').textContent=$('excludedSalaryEmployees').open?'Hide removed employees':'Show removed employees';
 $('excludedEmployeeRows').innerHTML=excluded.map(r=>'<div>'+esc(r.employee_id)+' - '+esc(r.name)+' <button type="button" data-restore="'+r.user_id+'">Add to salary list</button> <button type="button" class="exclude-employee" data-delete-ems="'+r.user_id+'">Delete from EMS only</button></div>').join('')||'<p>No removed employees. Employees you remove will appear here so you can add them back.</p>';
 if(!state.rows.some(r=>String(r.user_id)===$('setupForm').elements.user_id.value)){$('setupEmployeeSearch').value='';$('setupForm').elements.user_id.value='';}

 for(const form of [$('setupForm'),$('earningForm')]){
 const old=form.elements.user_id.value,isSetup=form===$('setupForm');
 if(isSetup)continue;
 form.elements.user_id.innerHTML='<option value="">'+(isSetup?'Choose employee ID':'Choose employee')+'</option>'+state.rows.map(r=>'<option value="'+r.user_id+'">'+(isSetup?esc(r.employee_id||'ID not assigned (record '+r.user_id+')')+' - '+esc(r.name):esc(r.name)+' - '+esc(r.employee_id||groups[r.category]))+'</option>').join('');
 if(state.rows.some(r=>String(r.user_id)===old))form.elements.user_id.value=old;
 }
 filterSetupEmployees();
 const setupForm=$('setupForm');
 setupForm.elements.effective_month.value=month;
 syncAttendanceWeekoffs();render();if($('employeeListDialog').open)renderEmployeeList();message('Records updated. Automatic incentive allocation is pending.');
 }catch(e){message(e.message,true);}finally{loading=false;$('refresh').disabled=false;$('month').disabled=false;}}
function attendanceDetails(row){return (row.manual_employee?'<p class="notice">Manual employee: '+(row.missing_attendance||0)+' attendance days not entered.</p>':'')+`<p><b>${esc(row.name)}</b> · ${esc(row.employee_id)} · ${esc(row.outlet)} · ${esc(state.month)}</p><p>Gross salary: ${money(row.gross_salary||0)} &nbsp; Unused weekoff days: ${row.weekoff_credit||0} &nbsp; Weekoff pay: ${money(row.weekoff_pay||0)}</p><p>Present: ${row.counts.present} &nbsp; Absent: ${row.counts.absent} &nbsp; CL: ${row.counts.casual_leave??0} &nbsp; W/O: ${row.counts.weekoff} &nbsp; Leave: ${row.counts.leave}</p><p class="muted">${esc(row.joining_source)}: ${esc(row.joining_date)} · Before joining: ${row.counts.before_joining} · Upcoming: ${row.counts.upcoming}. Leave uses the ERP attendance leave register.</p><div class="days">${row.days.map(d=>`<div class="day ${d.status}"><b>${esc(d.day.slice(8))}</b><br>${esc(d.entered===false?'Not entered':d.status.replace('_',' '))}</div>`).join('')}</div>`;}
function review(uid){selected=state.rows.find(r=>r.user_id===uid);if(!selected)return;$('detailTitle').textContent='Review salary · '+state.month;$('detailBody').innerHTML=attendanceDetails(selected)+(selected.profile_id?`<p>Monthly basic: ${money(selected.monthly_basic)} · Monthly allowances: ${money(selected.monthly_allowances)}</p><p>Divisor: ${esc(selected.divisor)} · W/O: ${selected.paid_weekoff?'paid':'unpaid'} · CL: paid ? L: unpaid</p><p>Payable days: ${selected.payable_days} · Unpaid days: ${selected.unpaid_days}</p><p>Earned basic: ${money(selected.basic)} · Earned allowances: ${money(selected.allowances)}<br>Manual incentive: ${money(selected.incentive)} · Bonus: ${money(selected.bonus)} · Deductions: ${money(selected.deductions)}</p><h2>Draft net: ${money(selected.net)}</h2>`:'<p>Save salary setup to calculate this employee’s salary.</p>');$('ack').checked=false;$('publishControls').hidden=!selected.can_publish;$('printSlip').hidden=true;$('detail').showModal();}
async function slip(id){try{const data=await api('/salary-slips/'+id),p=data.payroll,s=data.snapshot;$('detailTitle').textContent='IDSPL Salary Slip · '+p.month;$('detailBody').innerHTML=`<p>Employee: ${esc(s?.name||state.records.find(r=>r.id===id)?.name)} · ${esc(s?.employee_id||'')}</p><p>Status: ${esc(p.status)}</p><table>${[['Earned basic',p.basic],['Earned allowances',p.allowances],['Approved manual incentive',p.incentives],['Bonus',(p.bonuses||0)-(s?.weekoff_pay||0)],['Unused weekoff pay',s?.weekoff_pay||0],['Deductions',p.deductions],['Net salary',p.net]].map(([label,value])=>cells([label,money(value)])).join('')}</table><p class="muted">Automatic incentive allocation pending. This slip records the salary published in EMS.</p>`+(s?attendanceDetails(s):'');$('publishControls').hidden=true;$('printSlip').hidden=false;$('detail').showModal();}catch(e){message(e.message,true);}}
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b===button);$(b.dataset.tab).hidden=b!==button;});if(button.dataset.tab==='attendanceRecord'){attendanceSheetEmployee=null;renderAttendanceRecord();}if(button.dataset.tab==='distribution')renderDistribution();if(button.dataset.tab==='earnings')renderWeekoffTable();if(button.dataset.tab==='ids')renderIDS();}));
$('refresh').onclick=refresh;$('month').onchange=()=>{if(!$('detail').open)refresh();};$('group').onchange=render;$('employmentCategory').onchange=render;$('search').oninput=render;$('detailClose').onclick=()=>$('detail').close();$('printSlip').onclick=()=>window.print();
document.addEventListener('click',async event=>{const button=event.target.closest('button');if(!button)return;if(button.dataset.review)review(Number(button.dataset.review));if(button.dataset.slip)await slip(Number(button.dataset.slip));if(button.dataset.paid&&confirm('Record that this salary was paid outside EMS?')){button.disabled=true;try{await api('/payroll/'+button.dataset.paid+'/paid',{method:'PUT'});await refresh();}catch(e){message(e.message,true);button.disabled=false;}}});
document.addEventListener('click',async event=>{const button=event.target.closest('[data-void]');if(!button||!confirm('Void this approved earning and recalculate the draft salary?'))return;button.disabled=true;try{await api('/earnings/'+button.dataset.void+'/void',{method:'PUT'});await refresh();}catch(e){message(e.message,true);button.disabled=false;}});
$('publish').onclick=async()=>{if(!$('ack').checked){alert('Review and acknowledge the pending incentive allocation.');return;}const button=$('publish');button.disabled=true;try{await api('/salary-publish',{method:'POST',body:JSON.stringify({user_id:selected.user_id,month:state.month,preview:selected,acknowledge_pending_incentive:true})});$('detail').close();await refresh();}catch(e){alert(e.message);}finally{button.disabled=false;}};
function setupMessage(text,error=false){
 $('setupSaveStatus').textContent=text;$('setupSaveStatus').className=error?'error':'';
}
$('setupForm').addEventListener('invalid',event=>{setupMessage(event.target.validationMessage||'Please complete the required fields.',true);},true);
for(const [formId,path] of [['setupForm','/salary-profiles'],['earningForm','/earnings']]){
 $(formId).onsubmit=async event=>{
 event.preventDefault();const form=event.target,button=form.querySelector('button.primary'),isSetup=formId==='setupForm',label=button.textContent;
 button.disabled=true;button.textContent='Saving...';
 if(isSetup)setupMessage('Saving salary setup...');
 try{
 const data=Object.fromEntries(new FormData(form));
 if(isSetup){
 const employee=state.rows.find(r=>employeeOptionLabel(r)===$('setupEmployeeSearch').value);
 if(!employee)throw Error('Choose an employee from the dropdown before saving.');
 data.user_id=employee.user_id;
 data.effective_month=form.elements.effective_month.value||$('month').value;
 data.allowances=data.allowances||'0';data.deductions=data.deductions||'0';
 data.divisor='30';
 data.basic=((Math.round(Number($('setupGross').value)*100)-Math.round(Number(data.allowances)*100))/100).toFixed(2);
 if(!Number.isFinite(Number(data.basic))||Number(data.basic)<0)throw Error('Enter a valid Expected Basic that covers existing allowances.');
 data.weekoff_availed=employee.counts.weekoff;
 data.weekoff_credit=Math.max(0,4-data.weekoff_availed);
 data.weekoff_pay=(Math.round(Math.round(Number($('setupGross').value)*100)*data.weekoff_credit/30)/100).toFixed(2);
 data.paid_weekoff=true;data.paid_leave=false;
 }else data.user_id=Number(data.user_id);
 const result=await api(path,{method:'POST',body:JSON.stringify(data)});
 if(isSetup)setupMessage(result.message||'Salary setup saved successfully.');
 await refresh();message(result.message||'Saved successfully.');
 }catch(e){message(e.message,true);if(isSetup)setupMessage(e.message,true);}
 finally{button.disabled=false;button.textContent=label;}
 };
}
function salaryReportRows(category=''){
 const headers=['Employee ID','Employee Name','Employee Group','Emp Category','Salary Month','Absent','Working Days','W/O Availed','W/O Credit','Expected Basic INR','W/O Pay INR','Incentive INR','Amount Payable INR','Present','W/O','Leave','Setup Status'];
 const report=filtered(category).map(employee=>{
 const profile=state.profiles.filter(p=>p.user_id===employee.user_id&&p.effective_month<=state.month).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0];
 const availed=employee.weekoff_availed??employee.counts.weekoff,credit=Math.max(0,4-availed);
 const gross=profile?profile.basic+profile.allowances:0,pay=Math.round(gross*credit/30),incentive=profile?.setup_incentive||0;
 return [employee.employee_id,employee.name,groups[employee.category],employee.employment_category||'Not set',state.month,employee.counts.absent||0,employee.counts.present||0,availed,credit,...(profile?[gross,pay,incentive,employee.employment_category==='Regular'?employee.net:pay+incentive].map(v=>(v/100).toFixed(2)):['','','','']),employee.counts.present,employee.counts.weekoff,employee.counts.leave,profile?'Saved':'Setup needed'];
 });
 return [headers,...report];
}
function downloadSalary(category){return downloadSalaryWorkbook(category);}
function showSalaryDownloadMenu(open){
 $('salaryDownloadMenu').hidden=!open;$('export').setAttribute('aria-expanded',String(open));
}
$('export').onclick=()=>{const open=$('salaryDownloadMenu').hidden;showSalaryDownloadMenu(open);if(open)$('salaryDownloadMenu').querySelector('button').focus();};
$('salaryDownloadMenu').addEventListener('click',event=>{const button=event.target.closest('[data-salary-download]');if(!button)return;showSalaryDownloadMenu(false);downloadSalary(button.dataset.salaryDownload);$('export').focus();});
document.addEventListener('click',event=>{if(!event.target.closest('.salary-download'))showSalaryDownloadMenu(false);});
$('salaryDownloadMenu').addEventListener('keydown',event=>{
 if(event.key==='Escape'){showSalaryDownloadMenu(false);$('export').focus();}
 if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();const buttons=Array.from($('salaryDownloadMenu').querySelectorAll('button')),index=buttons.indexOf(document.activeElement);buttons[(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();}
});
$('homeLink').href=base+'/home';
const now=new Date(),month=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit'}).formatToParts(now),initial=month.find(p=>p.type==='year').value+'-'+month.find(p=>p.type==='month').value;
$('month').value=initial;$('setupForm').elements.effective_month.value=initial;$('earningForm').elements.month.value=initial;
if(!localStorage.getItem('token'))location.href=base+'/login';else refresh();


let salaryRemovalTarget=null,salaryRemovalBusy=false,salaryRemovalPermanent=false;
function cancelSalaryRemoval(){
 if(salaryRemovalBusy)return;
 salaryRemovalTarget=null;resetSalaryRemovalVerification();$('removeSalaryDialog').close('cancel');
}
$('removeSalaryCancel').onclick=cancelSalaryRemoval;
$('removeSalaryDialog').addEventListener('cancel',event=>{event.preventDefault();cancelSalaryRemoval();});
$('removeSalaryDialog').querySelector('form').addEventListener('submit',event=>event.preventDefault());
$('removeSalaryConfirm').onclick=async()=>{
 if(salaryRemovalBusy||salaryRemovalTarget===null||!salaryRemovalVerified||$('removeSalaryConfirmation').value!==(salaryRemovalPermanent?'DELETE':'REMOVE'))return;
 salaryRemovalBusy=true;const uid=salaryRemovalTarget,confirmButton=$('removeSalaryConfirm');
 confirmButton.disabled=true;$('removeSalaryCancel').disabled=true;confirmButton.textContent=salaryRemovalPermanent?'Deleting...':'Removing...';$('removeSalaryError').hidden=true;
 try{
 const result=await api('/employees/'+uid+(salaryRemovalPermanent?'':'/exclude'),{method:salaryRemovalPermanent?'DELETE':'PUT',body:JSON.stringify({password:$('removeSalaryPassword').value,confirmation:$('removeSalaryConfirmation').value})});
 salaryRemovalTarget=null;resetSalaryRemovalVerification();$('removeSalaryDialog').close('removed');
 await refresh();setupMessage(result.message);
 }catch(error){$('removeSalaryError').textContent=error.message;$('removeSalaryError').hidden=false;}
 finally{salaryRemovalBusy=false;$('removeSalaryCancel').disabled=false;confirmButton.textContent=salaryRemovalPermanent?'Permanently delete from EMS':'Remove from salary list';syncSalaryRemovalButton();}
};
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-exclude],[data-restore],[data-delete-ems]');if(!button)return;
 if(button.dataset.exclude||button.dataset.deleteEms){
 if($('removeSalaryDialog').open)return;
 salaryRemovalPermanent=Boolean(button.dataset.deleteEms);resetSalaryRemovalVerification();salaryRemovalTarget=Number(button.dataset.deleteEms||button.dataset.exclude);
 const word=salaryRemovalPermanent?'DELETE':'REMOVE';$('salaryRemovalWord').textContent=word;$('salaryRemovalWordLabel').textContent='Type '+word;
 $('removeSalaryTitle').textContent=salaryRemovalPermanent?'Permanently delete from EMS':'Remove only from salary list';
 $('removeSalaryDescription').textContent=salaryRemovalPermanent?'This permanently deletes the employee EMS salary setups, earnings, payroll history, payslips and manual attendance. This cannot be undone. Their registered account, login, Attendance records and access to other modules will remain unchanged. Only EMS records are deleted. A deletion audit is kept.':'This employee will be excluded from the EMS salary list and salary reports. Their login, attendance, other access and saved records remain unchanged.';
 $('removeSalaryConfirm').textContent=salaryRemovalPermanent?'Permanently delete from EMS':'Remove from salary list';
 const employee=state.rows.find(r=>r.user_id===salaryRemovalTarget)||state.excluded?.find(r=>r.user_id===salaryRemovalTarget);
 $('removeSalaryEmployee').textContent=employee?employeeOptionLabel(employee):'Selected employee';
 $('removeSalaryError').hidden=true;$('removeSalaryDialog').showModal();$('removeSalaryPassword').focus();return;
 }
 button.disabled=true;const originalLabel=button.textContent;button.textContent='Adding...';
 try{const result=await api('/employees/'+Number(button.dataset.restore)+'/exclude',{method:'DELETE'});await refresh();setupMessage(result.message);}
 catch(error){setupMessage(error.message,true);button.disabled=false;button.textContent=originalLabel;}
});


$('excludedSalaryEmployees').addEventListener('toggle',()=>{$('excludedToggleLabel').textContent=$('excludedSalaryEmployees').open?'Hide removed employees':'Show removed employees';});

let employeeListMissingOnly=false,manualAttendanceEmployee=null,manualAttendanceMonth=null;
function renderEmployeeList(){
 const rows=filtered().filter(r=>!employeeListMissingOnly||!r.profile_id);
 $('employeeListTitle').textContent=employeeListMissingOnly?'Salary setups missing':'Employees';
 $('employeeListNote').textContent=rows.length+' employees matching the current month and filters.';
 $('employeeListRows').innerHTML=rows.map(r=>cells([esc(r.employee_id||'ID not assigned'),esc(r.name)+(r.manual_employee?'<small>Manual employee</small>':''),esc(r.outlet),r.profile_id?'Saved':'Missing',r.manual_employee?'<button type="button" data-manual-attendance="'+r.user_id+'">Enter attendance</button>':'ERP attendance','<button type="button" data-setup="'+r.user_id+'">'+(r.profile_id?'Edit salary':'Set up salary')+'</button>'])).join('')||empty(6);
}
function showEmployeeList(missingOnly){employeeListMissingOnly=missingOnly;renderEmployeeList();$('employeeListDialog').showModal();}
$('showEmployees').onclick=()=>showEmployeeList(false);
$('showMissingEmployees').onclick=()=>showEmployeeList(true);
document.addEventListener('click',event=>{const button=event.target.closest('[data-close-dialog]');if(button)$(button.dataset.closeDialog).close();const attendanceButton=event.target.closest('[data-manual-attendance]');if(attendanceButton)openManualAttendance(Number(attendanceButton.dataset.manualAttendance));});
$('addManualEmployee').onclick=async()=>{
 const button=$('addManualEmployee');button.disabled=true;
 try{const options=await api('/manual-employee-options');$('manualEmployeeStore').innerHTML='<option value="">Unassigned</option>'+options.stores.map(s=>'<option value="'+s.id+'">'+esc(s.name)+'</option>').join('');$('manualEmployeeError').textContent='';$('manualEmployeeDialog').showModal();await updateManualEmployeeId();}
 catch(error){message(error.message,true);}finally{button.disabled=false;}
};
$('manualEmployeeForm').onsubmit=async event=>{
 event.preventDefault();const form=event.target,button=form.querySelector('button.primary');button.disabled=true;$('manualEmployeeError').textContent='';
 try{const data=Object.fromEntries(new FormData(form));data.store_id=data.store_id?Number(data.store_id):null;data.weekoff_day=data.weekoff_day||null;const result=await api('/manual-employees',{method:'POST',body:JSON.stringify(data)});$('manualEmployeeDialog').close();form.reset();await refresh();document.querySelector('[data-tab="setup"]').click();editSetup(result.user_id);message(result.message);}
 catch(error){$('manualEmployeeError').textContent=error.message;}finally{button.disabled=false;}
};
function openManualAttendance(uid){
 const employee=state.rows.find(r=>r.user_id===uid);if(!employee)return;
 if(employee.manual_employee){
   if($('employeeListDialog').open)$('employeeListDialog').close();
   document.querySelector('[data-tab="attendanceRecord"]').click();
   attendanceSheetEmployee=uid;renderAttendanceRecord();
   $('attendanceRecord').scrollIntoView({behavior:'smooth',block:'start'});
   return;
 }
 if($('employeeListDialog').open)$('employeeListDialog').close();
 manualAttendanceEmployee=uid;manualAttendanceMonth=state.month;
 $('manualAttendanceTitle').textContent='Attendance Record - '+employee.name+' - '+state.month;
 $('manualAttendanceNote').textContent=employee.published_id?'Published salary: attendance is locked.':'Select a status to correct attendance, or Automatic to restore fetched attendance.';
 const todayParts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
 const part=k=>todayParts.find(p=>p.type===k).value,today=part('year')+'-'+part('month')+'-'+part('day');
 $('manualAttendanceRows').innerHTML=employee.days.map(d=>{
 const disabled=Boolean(employee.published_id||d.day<employee.joining_date||d.day>today);
 return cells([esc(d.day)+'<small>'+esc(d.entered===false?'Not entered':d.status.replace('_',' '))+'</small>','<select aria-label="Attendance '+esc(d.day)+'" data-manual-day="'+esc(d.day)+'" data-original="'+esc(d.overridden||employee.manual_employee&&d.entered?d.status:"auto")+'"'+(disabled?' disabled':'')+'><option value="auto">Automatic</option><option value="">'+(d.day<employee.joining_date?'Before joining':d.day>today?'Upcoming':'Not entered')+'</option>'+['present','absent','casual_leave','weekoff','leave'].map(status=>'<option value="'+status+'"'+((employee.manual_employee?d.entered:d.overridden)&&d.status===status?' selected':'')+'>'+({present:'Present',absent:'Absent',casual_leave:'Casual Leave',weekoff:'W/O',leave:'Leave'}[status])+'</option>').join('')+'</select>','<input aria-label="Note '+esc(d.day)+'" data-manual-note="'+esc(d.day)+'" value="'+esc(d.note||'')+'" data-original-note="'+esc(d.note||'')+'" maxlength="300"'+(disabled?' disabled':'')+'>']);
 }).join('');
 $('manualAttendanceError').textContent='';$('manualAttendanceForm').querySelector('button.primary').disabled=Boolean(employee.published_id);$('manualAttendanceDialog').showModal();
}
$('manualAttendanceForm').onsubmit=async event=>{
 event.preventDefault();const button=event.target.querySelector('button.primary');button.disabled=true;$('manualAttendanceError').textContent='';
 try{const days=Array.from($('manualAttendanceRows').querySelectorAll('[data-manual-day]')).filter(input=>!input.disabled&&input.value&&(input.value!==input.dataset.original||$('manualAttendanceRows').querySelector('[data-manual-note="'+input.dataset.manualDay+'"]').value!==$('manualAttendanceRows').querySelector('[data-manual-note="'+input.dataset.manualDay+'"]').dataset.originalNote)).map(input=>({day:input.dataset.manualDay,status:input.value,note:$('manualAttendanceRows').querySelector('[data-manual-note="'+input.dataset.manualDay+'"]').value}));if(!days.length)throw Error('Enter attendance for at least one day.');const result=await api('/attendance-records/'+manualAttendanceEmployee,{method:'PUT',body:JSON.stringify({month:manualAttendanceMonth,days})});$('manualAttendanceDialog').close();await refresh();message(result.message);}
 catch(error){$('manualAttendanceError').textContent=error.message;}finally{button.disabled=false;}
};

let manualIdPreviewRequest=0;
async function updateManualEmployeeId(){
 const request=++manualIdPreviewRequest,store=$('manualEmployeeStore').value;
 $('manualEmployeeId').value='';$('manualEmployeeId').placeholder='Generating employee ID...';
 try{const data=await api('/manual-employee-id'+(store?'?store_id='+encodeURIComponent(store):''));if(request!==manualIdPreviewRequest)return;$('manualEmployeeId').value=data.employee_id;$('manualEmployeeId').placeholder='Assigned automatically on creation';}
 catch(error){if(request===manualIdPreviewRequest){$('manualEmployeeId').placeholder='Assigned automatically on creation';$('manualEmployeeError').textContent=error.message;}}
}
$('manualEmployeeStore').onchange=updateManualEmployeeId;
let salaryRemovalVerified=false;
function syncSalaryRemovalButton(){$('removeSalaryConfirm').disabled=salaryRemovalBusy||!salaryRemovalVerified||$('removeSalaryConfirmation').value!==(salaryRemovalPermanent?'DELETE':'REMOVE');}
function resetSalaryRemovalVerification(){salaryRemovalVerified=false;$('removeSalaryPassword').value='';$('removeSalaryConfirmation').value='';$('removeSalaryConfirmationStep').hidden=true;$('removeSalaryError').hidden=true;syncSalaryRemovalButton();}
$('removeSalaryPassword').addEventListener('input',()=>{salaryRemovalVerified=false;$('removeSalaryConfirmation').value='';$('removeSalaryConfirmationStep').hidden=true;syncSalaryRemovalButton();});
$('removeSalaryConfirmation').addEventListener('input',syncSalaryRemovalButton);
$('verifySalaryRemovalPassword').onclick=async()=>{
 if(salaryRemovalBusy||salaryRemovalTarget===null)return;
 const password=$('removeSalaryPassword').value;if(!password){$('removeSalaryError').textContent='Enter your login password.';$('removeSalaryError').hidden=false;return;}
 salaryRemovalBusy=true;$('verifySalaryRemovalPassword').disabled=true;$('removeSalaryPassword').disabled=true;$('removeSalaryCancel').disabled=true;$('removeSalaryError').hidden=true;
 try{await api('/employees/'+salaryRemovalTarget+'/removal-password',{method:'POST',body:JSON.stringify({password})});salaryRemovalVerified=true;$('removeSalaryConfirmationStep').hidden=false;$('removeSalaryConfirmation').focus();}
 catch(error){salaryRemovalVerified=false;$('removeSalaryError').textContent=error.message;$('removeSalaryError').hidden=false;}
 finally{salaryRemovalBusy=false;$('verifySalaryRemovalPassword').disabled=false;$('removeSalaryPassword').disabled=false;$('removeSalaryCancel').disabled=false;syncSalaryRemovalButton();}
};

const distributionDrafts=new Map();
const distributionKeys=['absent','no_of_days','working_days','expected_basic','actual_basic','other_allowances','actual_vda','actual_pay_epf','actual_oa','total_earning','bonus_payable','actual_gross_earning','epf_employee','esic_employee','staff_advance','total_deductions','net_amount','account_no','ifsc_code'];
function distributionKey(uid){return state.month+':'+uid;}
function salaryAttendance(employee,profile,fallback){
 const totalDraft=employee?.manual_employee?attendanceTotalDrafts.get(state.month+':'+employee.user_id):null;
 if(employee?.manual_employee&&(totalDraft?.valid||employee.monthly_attendance)){
  const counts=totalDraft?.valid?totalDraft.counts:employee.counts;
  const elapsed=employee.elapsed_days??employee.days.filter(d=>d.status!=='upcoming').length;
  const entered=['present','absent','casual_leave','weekoff','leave'].reduce((n,k)=>n+(counts[k]||0),0);
  return {unpaid:counts.absent+counts.leave+Math.max(0,elapsed-entered),weekoff:counts.weekoff,pending:Boolean(totalDraft)};
 }

 if(!Array.isArray(employee?.days))return {unpaid:fallback.absent,weekoff:employee?.counts?.weekoff??fallback.weekoff_availed??4,pending:false};
 let unpaid=0,weekoff=0,pending=false;
 for(const day of employee.days){
  const draft=attendanceDrafts.get(attendanceKey(employee.user_id,day.day));
  pending ||= Boolean(draft);
  const status=effectiveAttendanceStatus(employee,day);
  if(status==='weekoff')weekoff++;
  if(day.day<employee.joining_date||status==='before_joining'||status==='absent'||status==='unrecorded'||status==='leave')unpaid++;
 }
 return {unpaid,weekoff,pending};
}
function currentDistributionRows(category){
 const order=new Map(filtered(category).map((row,index)=>[row.user_id,index]));
 return (state.distribution||[]).filter(row=>order.has(row.user_id)).sort((a,b)=>order.get(a.user_id)-order.get(b.user_id)).map(row=>{
  const draft=distributionDrafts.get(distributionKey(row.user_id));
  // Use the same effective salary setup displayed in the Salary setup table.
  const profile=Array.isArray(state.profiles)?state.profiles.filter(p=>p.user_id===row.user_id&&p.effective_month<=state.month).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0]:null;
  const expectedBasic=Array.isArray(state.profiles)?(profile?profile.basic+profile.allowances:0):row.expected_basic;
  const profileId=Array.isArray(state.profiles)?(profile?.id??null):row.profile_id;
  const employee=state.rows.find(r=>r.user_id===row.user_id),attendance=salaryAttendance(employee,profile,row);
  const employmentCategory=profile?.employment_category??employee?.employment_category??row.employment_category??null;
  return {...row,profile_id:profileId,attendance_pending:attendance.pending,...salaryDistributionMath.calculateDistribution(expectedBasic,attendance.unpaid,draft?.other_allowances??row.other_allowances,draft?.staff_advance??row.staff_advance,attendance.weekoff,employmentCategory)};
 });
}
function distributionInput(row,key){return '<input type="number" min="0" max="10000000" step="0.01" aria-label="'+esc(key==='other_allowances'?'Other allowances for '+row.name:'Staff advance and deduction for '+row.name)+'" data-dist-input="'+key+'" value="'+(row[key]/100).toFixed(2)+'"'+(!row.profile_id?' disabled':'')+'>'+(key==='staff_advance'?'<button type="button" class="distribution-save" data-dist-save="'+row.user_id+'"'+(!row.profile_id?' disabled':'')+'>Save inputs</button>':'');}
function renderDistribution(){
 const rows=currentDistributionRows();
 $('distributionRows').innerHTML=rows.map(row=>'<tr data-dist-user="'+row.user_id+'"><td class="distribution-employee"><b>'+esc(row.name)+'</b><small>'+esc(row.employee_id)+'</small><small data-dist-status role="status">'+(!row.profile_id?'Salary setup needed':row.missing_attendance?'Attendance incomplete: '+row.missing_attendance+' days':row.attendance_pending?'Attendance saving; provisional totals':distributionDrafts.has(distributionKey(row.user_id))?'Unsaved inputs':'')+'</small></td>'+distributionKeys.map(key=>{
  const total=['total_earning','actual_gross_earning','total_deductions'].includes(key);
  let content;
  if(['account_no','ifsc_code'].includes(key))content=esc(row[key]||'-');
  else if(['other_allowances','staff_advance'].includes(key))content=distributionInput(row,key);
  else if(['absent','no_of_days','working_days'].includes(key))content=row[key];
  else content=row.profile_id?money(row[key]):'-';
  const displayed=['other_allowances','staff_advance'].includes(key)?content:'<span class="distribution-value" title="'+esc(String(content))+'">'+content+'</span>';
  return '<td data-dist-value="'+key+'" class="'+(key==='net_amount'?'distribution-net':total?'dist-total':'')+'">'+displayed+'</td>';
 }).join('')+'</tr>').join('')||empty(20);
 $('distributionNote').textContent=(state.month||'')+' | '+(state.closed_month?'Closed month':'Provisional: month not closed')+' | Fixed 30-day basis';
 renderDistributionTotals(rows);
}
function renderDistributionTotals(rows=currentDistributionRows()){
 const saved=rows.filter(row=>row.profile_id),sum=key=>saved.reduce((total,row)=>total+row[key],0);
 $('distributionCount').textContent=rows.length;$('distributionGross').textContent=money(sum('actual_gross_earning'));$('distributionDeductions').textContent=money(sum('total_deductions'));$('distributionNet').textContent=money(sum('net_amount'));
 const totalKeys=new Set(['expected_basic','actual_basic','other_allowances','actual_vda','actual_pay_epf','actual_oa','total_earning','bonus_payable','actual_gross_earning','weekoff_pay','epf_employee','esic_employee','staff_advance','total_deductions','net_amount']);
 $('distributionTotals').innerHTML=cells(['Total',...distributionKeys.map(key=>totalKeys.has(key)?money(sum(key)):'')]);
}

function renderIDS(){
 const rows=currentDistributionRows(),saved=rows.filter(r=>r.profile_id),sum=k=>saved.reduce((n,r)=>n+(r[k]||0),0);
 const plain=new Set(['absent','no_of_days','working_days','account_no','ifsc_code']);
 $('idsRows').innerHTML=rows.map(r=>cells(['<b>'+esc(r.name)+'</b><small>'+esc(r.employee_id)+'</small>'+(r.missing_attendance?'<small>Attendance incomplete</small>':'')+(r.attendance_pending?'<small>Attendance saving; provisional totals</small>':distributionDrafts.has(distributionKey(r.user_id))?'<small>Unsaved inputs</small>':''),...distributionKeys.map(k=>plain.has(k)?esc(r[k]??''):r.profile_id?money(r[k]):'Setup needed')])).join('')||empty(distributionKeys.length+1);
 const totals=new Set(distributionKeys.filter(k=>!plain.has(k)));
 $('idsTotals').innerHTML=cells(['Total',...distributionKeys.map(k=>totals.has(k)?money(sum(k)):'')]);
 $('idsCount').textContent=rows.length;$('idsGross').textContent=money(sum('actual_gross_earning'));$('idsDeductions').textContent=money(sum('total_deductions'));$('idsNet').textContent=money(sum('net_amount'));
 $('idsNote').textContent=state.month+' | '+(state.closed_month?'Closed month':'Provisional: month not closed')+' | Phase 1: gross less deductions; W/O and incentive excluded';
}

function parseDistributionAmount(input){
 if(!input.checkValidity()||!/^\d+(?:\.\d{1,2})?$/.test(input.value))throw Error('Enter a non-negative amount with up to two decimal places.');
 const [whole,fraction='']=input.value.split('.');const value=Number(whole)*100+Number(fraction.padEnd(2,'0'));
 if(value>1000000000)throw Error('Amount cannot exceed INR 1,00,00,000.');return value;
}
document.addEventListener('input',event=>{
 const input=event.target.closest('[data-dist-input]');if(!input)return;
 const tr=input.closest('[data-dist-user]'),uid=Number(tr.dataset.distUser),original=(state.distribution||[]).find(row=>row.user_id===uid);if(!original)return;
 try{
  input.setCustomValidity('');const value=parseDistributionAmount(input);
  const previous=distributionDrafts.get(distributionKey(uid))||{other_allowances:original.other_allowances,staff_advance:original.staff_advance};
  distributionDrafts.set(distributionKey(uid),{...previous,[input.dataset.distInput]:value});
  const row=currentDistributionRows().find(row=>row.user_id===uid);
  for(const key of distributionKeys){if(['absent','no_of_days','working_days','account_no','ifsc_code','other_allowances','staff_advance'].includes(key))continue;tr.querySelector('[data-dist-value="'+key+'"]').textContent=money(row[key]);}
  tr.querySelector('[data-dist-status]').textContent='Unsaved inputs';renderDistributionTotals();renderIDS();renderWeekoffTable();
 }catch(error){input.setCustomValidity(error.message);tr.querySelector('[data-dist-status]').textContent=error.message;}
});
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-dist-save]');if(!button)return;
 const tr=button.closest('[data-dist-user]'),inputs=Array.from(tr.querySelectorAll('[data-dist-input]')),uid=Number(button.dataset.distSave),month=state.month,key=distributionKey(uid);
 try{
  const values=Object.fromEntries(inputs.map(input=>{input.setCustomValidity('');return [input.dataset.distInput,(parseDistributionAmount(input)/100).toFixed(2)];}));
  button.disabled=true;inputs.forEach(input=>input.disabled=true);tr.querySelector('[data-dist-status]').textContent='Saving...';
  await api('/salary-distribution/'+uid,{method:'PUT',body:JSON.stringify({month,...values})});
  distributionDrafts.delete(key);await refresh();message('Salary distribution inputs saved.');
 }catch(error){tr.querySelector('[data-dist-status]').textContent=error.message;message(error.message,true);}
 finally{button.disabled=false;inputs.forEach(input=>input.disabled=false);}
});
function salaryWorkbookPayload(category){
 const ids=currentDistributionRows(category),employees=new Map(filtered(category).map(r=>[r.user_id,r])),weekoff=new Map(currentWeekoffRows(category).map(r=>[r.user_id,r]));
 const identity=r=>{const e=employees.get(r.user_id);return [e.employee_id||'',r.name,e.outlet||'',e.employment_category||groups[e.category]||''];};
 const textKeys=new Set(['account_no','ifsc_code']),dayKeys=new Set(['absent','no_of_days','working_days']);
 return {month:state.month,provisional:!state.closed_month||ids.some(r=>!r.profile_id||r.missing_attendance||r.attendance_pending||attendanceTotalDrafts.has(state.month+':'+r.user_id)||distributionDrafts.has(distributionKey(r.user_id))||weekoffDrafts.has(state.month+':'+r.user_id)),
 ids_rows:ids.map(r=>[...identity(r),...distributionKeys.map(k=>textKeys.has(k)?String(r[k]??''):dayKeys.has(k)?r[k]:r.profile_id?r[k]/100:null)]),
 weekoff_rows:ids.map(r=>{const w=weekoff.get(r.user_id);return [...identity(r),4,w.weekoff_availed,w.credit,...[w.gross,w.pay,w.incentive,w.payable].map(v=>r.profile_id?v/100:null)];})};
}
let workbookDownloading=false;
async function downloadSalaryWorkbook(category){
 if(workbookDownloading)return;
 const payload=salaryWorkbookPayload(category);
 if(!payload.ids_rows.length){message('No employees match the selected report filters.',true);return;}
 workbookDownloading=true;
 try{
  const response=await fetch(base+'/api/ems/salary-workbook',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store'});
  if(response.status===401){location.href=base+'/login';throw Error('Please sign in again');}
  if(!response.ok){const error=await response.text();throw Error('Excel download failed (HTTP '+response.status+'): '+error);}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download='IDSPL_Salary_'+state.month+'.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  message('Excel downloaded: IDS and W/O & Incentive.'+(payload.provisional?' Provisional totals include open month or unsaved inputs.':''));
 }catch(error){message(error.message,true);}finally{workbookDownloading=false;}
}
function exportDistribution(){return downloadSalaryWorkbook();}
$('distributionExport').onclick=()=>downloadSalaryWorkbook();
$('idsExport').onclick=()=>downloadSalaryWorkbook();
$('weekoffExport').onclick=()=>downloadSalaryWorkbook();

const attendanceDrafts=new Map();
const attendanceTotalDrafts=new Map();
let attendanceSaveTimer=null,attendanceSaving=false,attendanceSaveAgain=false;
const attendanceCodes={present:'P',absent:'A',casual_leave:'CL',weekoff:'WO',leave:'L',upcoming:'',before_joining:''};
function attendanceStatus(value){return {P:'present',A:'absent',CL:'casual_leave',WO:'weekoff',L:'leave'}[value.trim().toUpperCase()];}
function attendanceKey(uid,day){return state.month+':'+uid+':'+day;}
function effectiveAttendanceStatus(employee,day){
 const draft=attendanceDrafts.get(attendanceKey(employee.user_id,day.day));
 return draft?.status&&draft.status!=='auto'?draft.status:day.status;
}
function attendanceSheetCounts(employee){
 const draft=employee.manual_employee?attendanceTotalDrafts.get(state.month+':'+employee.user_id):null;
 if(draft?.valid)return {...draft.counts};
 if(employee.manual_employee&&employee.monthly_attendance)return Object.fromEntries(['present','absent','casual_leave','weekoff','leave'].map(k=>[k,employee.counts[k]||0]));

 const counts={present:0,absent:0,casual_leave:0,weekoff:0,leave:0};
 for(const day of employee.days){const status=effectiveAttendanceStatus(employee,day);if(status in counts)counts[status]++;}
 return counts;
}
function renderAttendanceRecord(){
 const active=document.activeElement,focus=active?.dataset?.manualTotalUser?{manualUser:active.dataset.manualTotalUser,kind:active.dataset.manualTotalKind}:active?.dataset?.sheetDay?{user:active.dataset.sheetUser,day:active.dataset.sheetDay}:null;
 const rows=attendanceSheetEmployee===null?filtered():state.rows.filter(r=>r.user_id===attendanceSheetEmployee),days=state.rows[0]?.days||[];
 $('showAllAttendanceEmployees').hidden=attendanceSheetEmployee===null;
 $('attendanceSheetHead').innerHTML='<tr><th class="attendance-employee">Employee / ID</th><th>Outlet</th>'+days.map(d=>'<th scope="col">'+esc(d.day.slice(8))+'<small>'+esc(new Intl.DateTimeFormat('en',{weekday:'short',timeZone:'UTC'}).format(new Date(d.day+'T00:00:00Z')))+'</small></th>').join('')+'<th>P</th><th>A</th><th>CL</th><th>WO</th><th>L</th></tr>';
 $('attendanceRecordRows').innerHTML=rows.map((r,ri)=>'<tr><th class="attendance-employee" scope="row"><b>'+esc(r.name)+'</b><small>'+esc(r.employee_id)+(r.published_id?' ? Locked':'')+'</small></th><td>'+esc(r.outlet)+'</td>'+r.days.map((d,ci)=>{
 const key=attendanceKey(r.user_id,d.day),draft=attendanceDrafts.get(key),disabled=Boolean(r.published_id||r.monthly_attendance||attendanceTotalDrafts.has(state.month+':'+r.user_id)||d.day<r.joining_date||d.status==='upcoming');
 const value=r.manual_employee&&(r.monthly_attendance||attendanceTotalDrafts.has(state.month+':'+r.user_id))?'':draft?draft.value:d.day<r.joining_date?'':d.entered===false?'':attendanceCodes[d.status]||'';
 return '<td class="attendance-cell"><input aria-label="'+esc(r.name+' '+d.day)+'" title="'+esc(d.day+' ? '+d.status+(d.note?' ? '+d.note:''))+'" data-sheet-user="'+r.user_id+'" data-sheet-day="'+d.day+'" data-sheet-row="'+ri+'" data-sheet-col="'+ci+'" class="sheet-code '+esc(effectiveAttendanceStatus(r,d))+(draft?' sheet-dirty':'')+'" value="'+esc(value)+'" autocomplete="off" spellcheck="false"'+(disabled?' disabled':'')+'></td>';
 }).join('')+['present','absent','casual_leave','weekoff','leave'].map(k=>'<td class="attendance-count" data-sheet-count="'+r.user_id+':'+k+'">'+(r.manual_employee?'<input type="number" min="0" max="31" step="1" style="width:64px" aria-label="'+esc(r.name+' total '+attendanceCodes[k])+'" data-manual-total-user="'+r.user_id+'" data-manual-total-kind="'+k+'" value="'+(attendanceTotalDrafts.get(state.month+':'+r.user_id)?.counts[k]??attendanceSheetCounts(r)[k])+'"'+(r.published_id?' disabled':'')+'>':attendanceSheetCounts(r)[k])+'</td>').join('')+'</tr>').join('')||empty(days.length+7);
 attendanceSheetMessage();
 if(focus){const input=$('attendanceRecordRows').querySelector(focus.manualUser?'[data-manual-total-user="'+focus.manualUser+'"][data-manual-total-kind="'+focus.kind+'"]':'[data-sheet-user="'+focus.user+'"][data-sheet-day="'+focus.day+'"]');input?.focus();}
}
function attendanceSheetMessage(text){$('attendanceSheetStatus').textContent=text||((attendanceDrafts.size+attendanceTotalDrafts.size)?(attendanceDrafts.size+attendanceTotalDrafts.size)+' unsaved attendance changes':'Attendance fetched automatically');}
function stageAttendanceCell(input){
 if(attendanceSaving)attendanceSaveAgain=true;
 const value=input.value.trim().toUpperCase(),status=attendanceStatus(value),employee=state.rows.find(r=>r.user_id===Number(input.dataset.sheetUser)),day=employee.days.find(d=>d.day===input.dataset.sheetDay);
 input.value=value;input.setCustomValidity(status?'':'Use P, A, CL, WO or L');input.classList.toggle('sheet-invalid',!status);
 attendanceDrafts.set(attendanceKey(employee.user_id,day.day),{month:state.month,user_id:employee.user_id,day:day.day,value,status,note:day.note||''});input.classList.add('sheet-dirty');
 for(const name of ['present','absent','casual_leave','weekoff','leave'])input.classList.toggle(name,status===name);
 const counts=attendanceSheetCounts(employee);
 for(const name of Object.keys(counts)){const cell=$('attendanceRecordRows').querySelector('[data-sheet-count="'+employee.user_id+':'+name+'"]');if(cell){const total=cell.querySelector?.('input');if(total)total.value=counts[name];else cell.textContent=counts[name];}}
 attendanceSheetMessage(status?'Updating attendance and salary calculations?':'Use P, A, CL, WO or L.');
 renderDistribution();renderIDS();renderWeekoffTable();
 clearTimeout(attendanceSaveTimer);
 if(status)attendanceSaveTimer=setTimeout(()=>saveAttendanceSheet(true),700);
}
function stageManualAttendanceTotal(input){
 const employee=state.rows.find(r=>r.user_id===Number(input.dataset.manualTotalUser));
 if(!employee?.manual_employee||employee.published_id)return;
 const key=state.month+':'+employee.user_id,previous=attendanceTotalDrafts.get(key);
 // A cleared monthly total means zero, rather than blocking all linked reports.
 const counts={...(previous?.counts||attendanceSheetCounts(employee)),[input.dataset.manualTotalKind]:Number(input.value.trim()||0)};
 const elapsed=employee.elapsed_days??employee.days.filter(d=>d.status!=='upcoming').length;
 const valid=Object.values(counts).every(v=>Number.isInteger(v)&&v>=0&&v<=31)&&Object.values(counts).reduce((a,b)=>a+b,0)<=elapsed;
 input.setCustomValidity(valid?'':'Enter whole days; P + A + CL + WO + L cannot exceed '+elapsed+'.');
 attendanceTotalDrafts.set(key,{month:state.month,user_id:employee.user_id,counts,valid});
 for(const [dayKey,day] of attendanceDrafts)if(day.month===state.month&&day.user_id===employee.user_id)attendanceDrafts.delete(dayKey);
 if(attendanceSaving)attendanceSaveAgain=true;
 attendanceSheetMessage(valid?'Manual totals updated; saving salary calculations...':'Check manual totals: the sum cannot exceed '+elapsed+' elapsed days.');
 renderDistribution();renderIDS();renderWeekoffTable();
 clearTimeout(attendanceSaveTimer);if(valid)attendanceSaveTimer=setTimeout(()=>saveAttendanceSheet(true),700);
}
$('attendanceRecordRows').addEventListener('input',event=>{if(event.target.matches('[data-manual-total-user]'))stageManualAttendanceTotal(event.target);});
function selectAttendanceCell(event){
 const input=event.target;if(input.matches('[data-sheet-day]')&&!input.disabled)input.select();
}
$('attendanceRecordRows').addEventListener('focusin',selectAttendanceCell);
$('attendanceRecordRows').addEventListener('click',selectAttendanceCell);
function replaceAttendanceCode(input,key){
 // Keep W followed by O as one code; a new status replaces a completed code.
 if(/^[pawlc]$/i.test(key)&&attendanceStatus(input.value)&&!(input.value.toUpperCase()==='W'&&key.toUpperCase()==='O'))input.select();
}
$('attendanceRecordRows').addEventListener('input',event=>{if(event.target.matches('[data-sheet-day]'))stageAttendanceCell(event.target);});
$('attendanceRecordRows').addEventListener('keydown',event=>{
 const input=event.target;if(!input.matches('[data-sheet-day]'))return;
 if(!event.ctrlKey&&!event.metaKey&&!event.altKey)replaceAttendanceCode(input,event.key);
 let row=Number(input.dataset.sheetRow),col=Number(input.dataset.sheetCol);
 if(event.key==='Enter'||event.key==='ArrowDown')row+=event.shiftKey?-1:1;
 else if(event.key==='ArrowUp')row--;else return;
 const next=$('attendanceRecordRows').querySelector('[data-sheet-row="'+row+'"][data-sheet-col="'+col+'"]');if(next&&!next.disabled){event.preventDefault();next.focus();next.select();}
});
$('attendanceRecordRows').addEventListener('paste',event=>{
 const input=event.target;if(!input.matches('[data-sheet-day]'))return;
 const text=event.clipboardData.getData('text/plain');if(!/[\t\r\n]/.test(text)){event.preventDefault();input.value=text.trim();stageAttendanceCell(input);return;}event.preventDefault();
 text.replace(/\r/g,'').replace(/\n$/,'').split('\n').forEach((line,ri)=>line.split('\t').forEach((value,ci)=>{
 const cell=$('attendanceRecordRows').querySelector('[data-sheet-row="'+(Number(input.dataset.sheetRow)+ri)+'"][data-sheet-col="'+(Number(input.dataset.sheetCol)+ci)+'"]');
 if(cell&&!cell.disabled){cell.value=value;stageAttendanceCell(cell);}
 }));
});
async function saveAttendanceSheet(automatic=false){
 if(attendanceSaving)return;
 clearTimeout(attendanceSaveTimer);
 if(!attendanceDrafts.size&&!attendanceTotalDrafts.size){attendanceSheetMessage('No changes to save.');return;}
 if([...attendanceTotalDrafts.values()].some(d=>!d.valid)){attendanceSheetMessage('Fix manual totals before saving.');return;}
 if([...attendanceDrafts.values()].some(d=>!d.status)){attendanceSheetMessage('Fix highlighted cells: use P, A, CL, WO, L or AUTO.');return;}
 const button=$('saveAttendanceSheet');button.disabled=true;attendanceSaving=true;
 const batches=new Map();for(const [key,d] of attendanceDrafts){const batchKey=d.month+':'+d.user_id;if(!batches.has(batchKey))batches.set(batchKey,[]);batches.get(batchKey).push([key,d]);}
 try{for(const entries of batches.values()){
 const first=entries[0][1];await api('/attendance-records/'+first.user_id,{method:'PUT',body:JSON.stringify({month:first.month,days:entries.map(([,d])=>({day:d.day,status:d.status,note:d.note}))})});
 for(const [key,d] of entries){
  const day=state.rows.find(r=>r.user_id===d.user_id)?.days?.find(day=>day.day===d.day);
  if(day&&d.status!=='auto')Object.assign(day,{status:d.status,entered:true,overridden:true,note:d.note});
  if(attendanceDrafts.get(key)===d)attendanceDrafts.delete(key);
 }
 }
 for(const [key,d] of [...attendanceTotalDrafts]){
  await api('/attendance-totals/'+d.user_id,{method:'PUT',body:JSON.stringify({month:d.month,...d.counts})});
  const employee=state.rows.find(r=>r.user_id===d.user_id);
  if(employee)Object.assign(employee,{monthly_attendance:true,counts:{...employee.counts,...d.counts}});
  if(attendanceTotalDrafts.get(key)===d)attendanceTotalDrafts.delete(key);
 }
 await refresh();attendanceSheetMessage(attendanceDrafts.size||attendanceTotalDrafts.size?'Saving latest changes?':'Attendance saved automatically. Salary totals updated.');}
 catch(error){attendanceSheetMessage(error.message+' Remaining changes are kept for retry.');}
 finally{button.disabled=false;attendanceSaving=false;}
 if((attendanceDrafts.size||attendanceTotalDrafts.size)&&[...attendanceDrafts.values()].every(d=>d.status)&&[...attendanceTotalDrafts.values()].every(d=>d.valid)&&attendanceSaveAgain){attendanceSaveAgain=false;attendanceSaveTimer=setTimeout(()=>saveAttendanceSheet(true),700);}
}
$('saveAttendanceSheet').onclick=()=>saveAttendanceSheet();
window.addEventListener('beforeunload',event=>{if(attendanceDrafts.size||attendanceTotalDrafts.size||weekoffDrafts.size){event.preventDefault();event.returnValue='';}});
setInterval(()=>{if(!document.hidden&&!document.querySelector('dialog[open]')&&!document.querySelector('input:focus,select:focus')&&!distributionDrafts.size&&!attendanceDrafts.size&&!attendanceTotalDrafts.size&&!weekoffDrafts.size)refresh();},60000);


const weekoffDrafts=new Map();
function weekoffValues(gross,availed,incentive){
 const credit=Math.max(0,4-availed),pay=Math.sign(gross*credit)*Math.round(Math.abs(gross*credit)/30);
 return {credit,pay,payable:pay+incentive};
}
function currentWeekoffRows(category){
 const distribution=new Map(currentDistributionRows(category).map(r=>[r.user_id,r]));
 return filtered(category).map(r=>{
 const d=distribution.get(r.user_id),saved=(state.weekoffIncentives||[]).find(i=>i.user_id===r.user_id),draft=weekoffDrafts.get(state.month+':'+r.user_id);
 const incentive=draft??saved?.incentive??0,gross=d?.actual_gross_earning??0,availed=d?.weekoff_availed??r.counts?.weekoff??0;
 return {...r,gross,incentive,attendance_pending:d?.attendance_pending,weekoff_availed:availed,...weekoffValues(gross,availed,incentive)};
 });
}
function renderWeekoffTotals(){
 const rows=currentWeekoffRows(),sum=key=>rows.reduce((s,r)=>s+r[key],0);
 $('weekoffTotals').innerHTML=cells(['Total','','','',money(sum('gross')),money(sum('pay')),money(sum('incentive')),money(sum('payable')),'']);
}
function renderWeekoffTable(){
 $('weekoffRows').innerHTML=currentWeekoffRows().map(r=>'<tr data-weekoff-user="'+r.user_id+'"><td><b>'+esc(r.name)+'</b><small>'+esc(r.employee_id)+'</small></td><td>4</td><td>'+r.weekoff_availed+'</td><td>'+r.credit+'</td><td>'+money(r.gross)+'</td><td>'+money(r.pay)+'</td><td><input type="number" min="0" max="10000000" step="0.01" aria-label="Incentive for '+esc(r.name)+'" data-weekoff-incentive="'+r.user_id+'" value="'+(r.incentive/100).toFixed(2)+'"></td><td data-weekoff-payable>'+money(r.payable)+'</td><td><button type="button" data-weekoff-save="'+r.user_id+'">Save</button><small data-weekoff-status>'+(r.attendance_pending?'Attendance saving; provisional totals':weekoffDrafts.has(state.month+':'+r.user_id)?'Unsaved incentive':'')+'</small></td></tr>').join('')||empty(9);
 renderWeekoffTotals();
}
$('weekoffRows').addEventListener('input',event=>{
 const input=event.target;if(!input.matches('[data-weekoff-incentive]'))return;
 const tr=input.closest('tr');try{
 input.setCustomValidity('');const value=parseDistributionAmount(input),uid=Number(input.dataset.weekoffIncentive);weekoffDrafts.set(state.month+':'+uid,value);
 tr.querySelector('[data-weekoff-payable]').textContent=money(currentWeekoffRows().find(r=>r.user_id===uid).payable);tr.querySelector('[data-weekoff-status]').textContent='Unsaved incentive';renderWeekoffTotals();
 }catch(error){input.setCustomValidity(error.message);tr.querySelector('[data-weekoff-status]').textContent=error.message;}
});
$('weekoffRows').addEventListener('click',async event=>{
 const button=event.target.closest('[data-weekoff-save]');if(!button)return;
 const tr=button.closest('tr'),input=tr.querySelector('[data-weekoff-incentive]'),uid=Number(button.dataset.weekoffSave),month=state.month;
 try{input.setCustomValidity('');const incentive=parseDistributionAmount(input);button.disabled=true;input.disabled=true;
 await api('/weekoff-incentives/'+uid,{method:'PUT',body:JSON.stringify({month,incentive:(incentive/100).toFixed(2)})});weekoffDrafts.delete(month+':'+uid);await refresh();message('W/O incentive saved.');
 }catch(error){tr.querySelector('[data-weekoff-status]').textContent=error.message;}finally{button.disabled=false;input.disabled=false;}
});

$('showAllAttendanceEmployees').onclick=()=>{attendanceSheetEmployee=null;renderAttendanceRecord();};
