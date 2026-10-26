'use strict';
const base = location.pathname.startsWith('/erp/') ? '/erp' : '';
const $ = id => document.getElementById(id);
const money = v => new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR'}).format((v || 0)/100);
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groups = {ids_emp:'IDS EMP',ac_retails:'AC Retail',ac_projects:'AC Projects'};
let state = {rows:[],profiles:[],earnings:[],records:[]}, selected = null, loading = false;
function message(text, error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function api(path, options={}) {
  const response = await fetch(base+'/api/ems'+path,{...options,headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json',...options.headers},cache:'no-store'});
  if(response.status===401){location.href=base+'/login';throw Error('Please sign in again');}
  const raw = await response.text();
  let data;try{data=raw?JSON.parse(raw):{};}catch{throw Error('Unable to save or load records (HTTP '+response.status+'). Restart the server if it was recently updated.');}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail || data));
  return data;
}
function filtered(){const query=$('search').value.toLowerCase();return state.rows.filter(r=>(!$('group').value||r.category===$('group').value)&&(!$('employmentCategory').value||r.employment_category===$('employmentCategory').value)&&[r.name,r.employee_id,r.outlet].some(v=>String(v).toLowerCase().includes(query)));}
function cells(values){return '<tr>'+values.map(v=>'<td>'+v+'</td>').join('')+'</tr>';}
function empty(columns){return `<tr><td colspan="${columns}">No records for this selection.</td></tr>`;}
function render(){
 const rows=filtered(), ids=new Set(rows.map(r=>r.user_id));
 $('employeeCount').textContent=rows.length;$('missingCount').textContent=rows.filter(r=>!r.profile_id).length;
 $('netTotal').textContent=money(rows.filter(r=>!r.published_id).reduce((s,r)=>s+(r.net||0),0));$('publishedCount').textContent=rows.filter(r=>r.published_id).length;
 $('periodNote').textContent=state.closed_month?'Closed month: review attendance and salary before publication.':'Open or future month: provisional totals only. Publication is available after month end.';
 $('monthlyRows').innerHTML=rows.map(r=>cells([`<b>${esc(r.name)}</b><small>${esc(r.employee_id||'ID not assigned')}</small>`,`${esc(r.outlet)}<small>${groups[r.category]}</small>`,r.counts.present,r.counts.absent,r.counts.weekoff,r.counts.leave,r.profile_id?money(r.basic+r.allowances):'Setup needed',money(r.incentive),money(r.bonus),r.profile_id?money(r.deductions):'—',r.profile_id?money(r.net):'—',`${r.manual_employee?'<button data-manual-attendance="'+r.user_id+'">Attendance</button> ':''}<button data-review="${r.user_id}">${r.published_id?'Attendance':'Review'}</button>${r.status==='draft'?'':'<small>'+esc(r.status)+'</small>'}`])).join('')||empty(12);
 $('idsRows').innerHTML=rows.filter(r=>r.employment_category==='Regular').map(r=>cells([esc(r.name),...['basic','actual_vda','actual_pay_epf','actual_oa','total_earning','bonus_payable','actual_gross_earning','epf_employee','esic_employee','staff_advance','deductions','net'].map(k=>r.profile_id?money(r[k]):'Setup needed')])).join('')||empty(13);
 const name=uid=>state.rows.find(r=>r.user_id===uid)?.name||'Employee '+uid;
 $('profileRows').innerHTML=rows.map(employee=>{
 const p=state.profiles.filter(p=>p.user_id===employee.user_id&&p.effective_month<=state.month).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0];
 const availed=employee.weekoff_availed??employee.counts.weekoff,credit=Math.max(0,4-availed);
 const gross=p?p.basic+p.allowances:0,pay=Math.round(gross*credit/30),incentive=p?.setup_incentive||0;
 return cells([esc(employee.employee_id||'ID not assigned'),esc(employee.name),p?esc(p.effective_month):'Setup needed',availed,credit,p?money(gross):'-',p?money(pay):'-',p?money(incentive):'-',p?money(employee.employment_category==='Regular'?employee.net:pay+incentive):'-',(employee.manual_employee?'<button type="button" data-manual-attendance="'+employee.user_id+'">Attendance</button> ':'')+'<button type="button" data-setup="'+employee.user_id+'"'+(p?' data-profile="'+p.id+'"':'')+'>'+(p?'Edit':'Set up')+'</button> <button type="button" class="exclude-employee" data-exclude="'+employee.user_id+'">Remove</button>']);
 }).join('')||empty(10);
 $('earningRows').innerHTML=state.earnings.filter(r=>ids.has(r.user_id)&&r.month===$('month').value).map(r=>cells([esc(name(r.user_id)),esc(r.month),esc(r.kind),money(r.amount),`${esc(r.note)}<small>${esc(r.status)}</small>${r.status==='approved'&&!state.records.some(p=>p.user_id===r.user_id&&p.month===r.month)?`<button data-void="${r.id}">Void entry</button>`:''}`])).join('')||empty(5);
 $('recordRows').innerHTML=state.records.filter(r=>ids.has(r.user_id)&&r.month===$('month').value).map(r=>cells([esc(r.name),esc(r.month),money(r.basic),money(r.allowances),money(r.incentives),money(r.bonuses),money(r.deductions),money(r.net),`<span class="badge">${esc(r.status)}</span>`,`<button data-slip="${r.id}">Payslip</button> ${r.status==='published'?`<button data-paid="${r.id}">Mark paid</button>`:''}`])).join('')||empty(10);
}
function employeeOptionLabel(row){return (row.employee_id||'ID not assigned (record '+row.user_id+')')+' - '+row.name;}
function showEmployeeOptions(show){const list=$('setupEmployeeOptions');list.hidden=!show;$('setupEmployeeSearch').setAttribute('aria-expanded',String(show));if(show&&window.matchMedia('(max-width:1350px)').matches){const rect=$('setupEmployeeSearch').getBoundingClientRect();list.style.top=(rect.bottom+5)+'px';list.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-340))+'px';}else{list.style.top='';list.style.left='';}}
window.addEventListener('resize',()=>showEmployeeOptions(false));
document.addEventListener('scroll',event=>{if(!event.target.closest?.('#setupEmployeeOptions'))showEmployeeOptions(false);},true);
function filterSetupEmployees(showAll=false){
 const input=$('setupEmployeeSearch'),query=showAll?'':input.value.trim().toLowerCase();
 const matches=state.rows.filter(r=>employeeOptionLabel(r).toLowerCase().includes(query));
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
 form.elements.divisor.value='30';
 for(const key of ['paid_weekoff','paid_leave'])form.elements[key].value=profile?String(Boolean(profile[key])):String(key==='paid_weekoff');
 setupIdentity();
 loadIDS(profile,employee);
}
$('setupForm').elements.user_id.onchange=()=>editSetup(Number($('setupForm').elements.user_id.value));
for(const key of ['basic','allowances'])$('setupForm').elements[key].addEventListener('input',setupIdentity);
document.addEventListener('click',event=>{const button=event.target.closest('[data-setup]');if(!button)return;if($('employeeListDialog').open)$('employeeListDialog').close();document.querySelector('[data-tab="setup"]').click();editSetup(Number(button.dataset.setup),Number(button.dataset.profile)||null);$('setupForm').scrollIntoView({behavior:'smooth',block:'center'});$('setupGross').focus({preventScroll:true});});
async function refresh(){if(loading)return;loading=true;$('refresh').disabled=true;$('month').disabled=true;message('Loading employee and attendance records…');try{
 const month=$('month').value;if(!month)throw Error('Choose a month');
 const [preview,profiles,earnings,records,excluded]=await Promise.all([api('/salary-preview?month='+encodeURIComponent(month)),api('/salary-profiles'),api('/earnings'),api('/payroll'),api('/excluded-employees')]);
 state={...preview,profiles,earnings,records};
 $('excludedCount').textContent=excluded.length;
 $('excludedToggleLabel').textContent=$('excludedSalaryEmployees').open?'Hide removed employees':'Show removed employees';
 $('excludedEmployeeRows').innerHTML=excluded.map(r=>'<div>'+esc(r.employee_id)+' - '+esc(r.name)+' <button type="button" data-restore="'+r.user_id+'">Add to salary list</button></div>').join('')||'<p>No removed employees. Employees you remove will appear here so you can add them back.</p>';
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
function attendanceDetails(row){return (row.manual_employee?'<p class="notice">Manual employee: '+(row.missing_attendance||0)+' attendance days not entered.</p>':'')+`<p><b>${esc(row.name)}</b> · ${esc(row.employee_id)} · ${esc(row.outlet)} · ${esc(state.month)}</p><p>Present: ${row.counts.present} &nbsp; Absent: ${row.counts.absent} &nbsp; Weekoff: ${row.counts.weekoff} &nbsp; Leave: ${row.counts.leave}</p><p class="muted">${esc(row.joining_source)}: ${esc(row.joining_date)} · Before joining: ${row.counts.before_joining} · Upcoming: ${row.counts.upcoming}. Leave uses the ERP attendance leave register.</p><div class="days">${row.days.map(d=>`<div class="day ${d.status}"><b>${esc(d.day.slice(8))}</b><br>${esc(d.entered===false?'Not entered':d.status.replace('_',' '))}</div>`).join('')}</div>`;}
function idsBreakdown(r){return r?.employment_category==='Regular'?'<h3>IDS regular pay calculation</h3><table>'+[['VDA',r.actual_vda],['Actual pay (EPF)',r.actual_pay_epf],['Actual OA',r.actual_oa],['Bonus payable',r.bonus_payable],['Gross earning',r.actual_gross_earning],['EPF employee',r.epf_employee],['ESIC employee',r.esic_employee],['Staff advance & deduction',r.staff_advance]].map(([k,v])=>cells([k,money(v)])).join('')+'</table>':'';}
function review(uid){selected=state.rows.find(r=>r.user_id===uid);if(!selected)return;$('detailTitle').textContent='Review salary · '+state.month;$('detailBody').innerHTML=attendanceDetails(selected)+idsBreakdown(selected)+(selected.profile_id?`<p>Monthly basic: ${money(selected.monthly_basic)} · Monthly allowances: ${money(selected.monthly_allowances)}</p><p>Divisor: ${esc(selected.divisor)} · Weekoff: ${selected.paid_weekoff?'paid':'unpaid'} · Leave: ${selected.paid_leave?'paid':'unpaid'}</p><p>Payable days: ${selected.payable_days} · Unpaid days: ${selected.unpaid_days}</p><p>Earned basic: ${money(selected.basic)} · Earned allowances: ${money(selected.allowances)}<br>Manual incentive: ${money(selected.incentive)} · Bonus: ${money(selected.bonus)} · Deductions: ${money(selected.deductions)}</p><h2>Draft net: ${money(selected.net)}</h2>`:'<p>Save salary setup to calculate this employee’s salary.</p>');$('ack').checked=false;$('publishControls').hidden=!selected.can_publish;$('printSlip').hidden=true;$('detail').showModal();}
async function slip(id){try{const data=await api('/salary-slips/'+id),p=data.payroll,s=data.snapshot;$('detailTitle').textContent='IDSPL Salary Slip · '+p.month;$('detailBody').innerHTML=`<p>Employee: ${esc(s?.name||state.records.find(r=>r.id===id)?.name)} · ${esc(s?.employee_id||'')}</p><p>Status: ${esc(p.status)}</p><table>${[['Earned basic',p.basic],['Earned allowances',p.allowances],['Approved manual incentive',p.incentives],['Bonus',p.bonuses],['Deductions',p.deductions],['Net salary',p.net]].map(([label,value])=>cells([label,money(value)])).join('')}</table><p class="muted">Automatic incentive allocation pending. This slip records the salary published in EMS.</p>`+idsBreakdown(s)+(s?attendanceDetails(s):'');$('publishControls').hidden=true;$('printSlip').hidden=false;$('detail').showModal();}catch(e){message(e.message,true);}}
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b===button);$(b.dataset.tab).hidden=b!==button;});}));
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
 if(data.employment_category==='Regular'){
   for(const key of ['basic','allowances','deductions']){
     const input=$('ids_'+key);if(!input.checkValidity()||!Number.isFinite(Number(input.value)))throw Error('Enter valid IDS salary amounts.');
     data[key]=input.value||'0';
   }
   $('setupGross').value=(Number(data.basic)+Number(data.allowances)).toFixed(2);
   data.ids_attributes=readIDS();
 }
 data.effective_month=form.elements.effective_month.value||$('month').value;
 data.allowances=data.allowances||'0';data.deductions=data.deductions||'0';
 data.divisor='30';
 if(data.employment_category!=='Regular')data.basic=((Math.round(Number($('setupGross').value)*100)-Math.round(Number(data.allowances)*100))/100).toFixed(2);
 if(!Number.isFinite(Number(data.basic))||Number(data.basic)<0)throw Error('Enter a valid gross salary that covers existing allowances.');
 data.weekoff_availed=employee.counts.weekoff;
 data.weekoff_credit=Math.max(0,4-data.weekoff_availed);
 data.weekoff_pay=(Math.round(Math.round(Number($('setupGross').value)*100)*data.weekoff_credit/30)/100).toFixed(2);
 data.paid_weekoff=data.paid_weekoff==='true';data.paid_leave=data.paid_leave==='true';
 }else data.user_id=Number(data.user_id);
 const result=await api(path,{method:'POST',body:JSON.stringify(data)});
 if(isSetup)setupMessage(result.message||'Salary setup saved successfully.');
 await refresh();message(result.message||'Saved successfully.');
 }catch(e){message(e.message,true);if(isSetup)setupMessage(e.message,true);}
 finally{button.disabled=false;button.textContent=label;}
 };
}
function salaryReportRows(){
 const headers=['Employee ID','Employee Name','Employee Group','Emp Category','Salary Month','Week Off Availed','Week Off Credit','Gross Salary INR','Week Off Pay INR','Incentive INR','Amount Payable INR','Present','Absent','Week Off','Leave','Setup Status'];
 const report=filtered().map(employee=>{
 const profile=state.profiles.filter(p=>p.user_id===employee.user_id&&p.effective_month<=state.month).sort((a,b)=>b.effective_month.localeCompare(a.effective_month))[0];
 const availed=employee.weekoff_availed??employee.counts.weekoff,credit=Math.max(0,4-availed);
 const gross=profile?profile.basic+profile.allowances:0,pay=Math.round(gross*credit/30),incentive=profile?.setup_incentive||0;
 return [employee.employee_id,employee.name,groups[employee.category],employee.employment_category||'Not set',state.month,availed,credit,...(profile?[gross,pay,incentive,employee.employment_category==='Regular'?employee.net:pay+incentive].map(v=>(v/100).toFixed(2)):['','','','']),employee.counts.present,employee.counts.absent,employee.counts.weekoff,employee.counts.leave,profile?'Saved':'Setup needed'];
 });
 const idsKeys=['basic','actual_vda','actual_pay_epf','actual_oa','total_earning','bonus_payable','actual_gross_earning','epf_employee','esic_employee','staff_advance','deductions','net'];
 headers.push('Actual Basic INR','VDA INR','Actual Pay EPF INR','Actual OA INR','Total Earning INR','Bonus Payable INR','Actual Gross INR','EPF INR','ESIC INR','Staff Advance INR','Total Deductions INR','Net INR','Branch','Skill Category','Payment Mode','Hold / Release','Account No.','IFSC Code','Working Days');
 filtered().forEach((r,i)=>report[i].push(...idsKeys.map(k=>r.profile_id?(Number(r[k]||0)/100).toFixed(2):''),...['branch','skill_category','payment_mode','release_status','account_no','ifsc_code'].map(k=>r.ids_attributes?.[k]||''),r.working_days??''));
 return [headers,...report];
}
$('export').onclick=()=>{
 const rows=salaryReportRows();
 if(rows.length===1){message('No employees match the selected report filters.',true);return;}
 const csv=rows.map(r=>r.map(v=>'"'+String(v??'').replace(/^[=+@\-]/,"'$&").replace(/"/g,'""')+'"').join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;
 link.download='IDSPL_Salary_Report_'+state.month+'_'+($('employmentCategory').value||'All_Categories')+'.csv';
 link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 message('Salary report downloaded: '+($('employmentCategory').value||'All categories')+' ('+(rows.length-1)+' employees).');
};
$('homeLink').href=base+'/home';
const now=new Date(),month=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit'}).formatToParts(now),initial=month.find(p=>p.type==='year').value+'-'+month.find(p=>p.type==='month').value;
$('month').value=initial;$('setupForm').elements.effective_month.value=initial;$('earningForm').elements.month.value=initial;
if(!localStorage.getItem('token'))location.href=base+'/login';else refresh();


let salaryRemovalTarget=null,salaryRemovalBusy=false;
function cancelSalaryRemoval(){
 if(salaryRemovalBusy)return;
 salaryRemovalTarget=null;$('removeSalaryDialog').close('cancel');
}
$('removeSalaryCancel').onclick=cancelSalaryRemoval;
$('removeSalaryDialog').addEventListener('cancel',event=>{event.preventDefault();cancelSalaryRemoval();});
$('removeSalaryDialog').querySelector('form').addEventListener('submit',event=>event.preventDefault());
$('removeSalaryConfirm').onclick=async()=>{
 if(salaryRemovalBusy||salaryRemovalTarget===null)return;
 salaryRemovalBusy=true;const uid=salaryRemovalTarget,confirmButton=$('removeSalaryConfirm');
 confirmButton.disabled=true;$('removeSalaryCancel').disabled=true;confirmButton.textContent='Removing...';$('removeSalaryError').hidden=true;
 try{
 const result=await api('/employees/'+uid+'/exclude',{method:'PUT'});
 salaryRemovalTarget=null;$('removeSalaryDialog').close('removed');
 await refresh();setupMessage(result.message);
 }catch(error){$('removeSalaryError').textContent=error.message;$('removeSalaryError').hidden=false;}
 finally{salaryRemovalBusy=false;confirmButton.disabled=false;$('removeSalaryCancel').disabled=false;confirmButton.textContent='Remove from salary list';}
};
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-exclude],[data-restore]');if(!button)return;
 if(button.dataset.exclude){
 if($('removeSalaryDialog').open)return;
 salaryRemovalTarget=Number(button.dataset.exclude);
 const employee=state.rows.find(r=>r.user_id===salaryRemovalTarget);
 $('removeSalaryEmployee').textContent=employee?employeeOptionLabel(employee):'Selected employee';
 $('removeSalaryError').hidden=true;$('removeSalaryDialog').showModal();return;
 }
 button.disabled=true;const originalLabel=button.textContent;button.textContent='Adding...';
 try{const result=await api('/employees/'+Number(button.dataset.restore)+'/exclude',{method:'DELETE'});await refresh();setupMessage(result.message);}
 catch(error){setupMessage(error.message,true);button.disabled=false;button.textContent=originalLabel;}
});

function readIDS(){const result={};for(const key of ['branch','skill_category','account_no','ifsc_code','payment_mode','release_status','epf_enabled','esic_enabled','bonus_enabled']){const value=$('ids_'+key).value;result[key]=key.endsWith('_enabled')?value==='true':value;}return result;}
function loadIDS(profile,employee){
 $('idsEmployee').textContent=employee?employeeOptionLabel(employee)+' � '+$('month').value:'Choose an employee in Salary setup first.';
 let attrs={};try{attrs=JSON.parse(profile?.ids_attributes||'{}');}catch{}
 for(const key of ['basic','allowances','deductions'])$('ids_'+key).value=((profile?.[key]||0)/100).toFixed(2);
 const defaults={skill_category:'Skilled',epf_enabled:true,esic_enabled:false,bonus_enabled:false,payment_mode:'BANK',release_status:'RELEASE'};
 for(const key of ['branch','skill_category','account_no','ifsc_code','payment_mode','release_status','epf_enabled','esic_enabled','bonus_enabled'])$('ids_'+key).value=String(attrs[key]??defaults[key]??'');
}
$('saveIDS').onclick=()=>{const form=$('setupForm');if(!form.elements.user_id.value){message('Choose an employee in Salary setup first.',true);return;}form.elements.employment_category.value='Regular';$('setupGross').value=(Number($('ids_basic').value)+Number($('ids_allowances').value)).toFixed(2);form.requestSubmit();};
loadIDS(null,null);

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
 try{const options=await api('/manual-employee-options');$('manualEmployeeStore').innerHTML='<option value="">Unassigned</option>'+options.stores.map(s=>'<option value="'+s.id+'">'+esc(s.name)+'</option>').join('');$('manualEmployeeError').textContent='';$('manualEmployeeDialog').showModal();}
 catch(error){message(error.message,true);}finally{button.disabled=false;}
};
$('manualEmployeeForm').onsubmit=async event=>{
 event.preventDefault();const form=event.target,button=form.querySelector('button.primary');button.disabled=true;$('manualEmployeeError').textContent='';
 try{const data=Object.fromEntries(new FormData(form));data.store_id=data.store_id?Number(data.store_id):null;data.weekoff_day=data.weekoff_day||null;const result=await api('/manual-employees',{method:'POST',body:JSON.stringify(data)});$('manualEmployeeDialog').close();form.reset();await refresh();document.querySelector('[data-tab="setup"]').click();editSetup(result.user_id);message(result.message);}
 catch(error){$('manualEmployeeError').textContent=error.message;}finally{button.disabled=false;}
};
function openManualAttendance(uid){
 const employee=state.rows.find(r=>r.user_id===uid);if(!employee?.manual_employee)return;
 if($('employeeListDialog').open)$('employeeListDialog').close();
 manualAttendanceEmployee=uid;manualAttendanceMonth=state.month;
 $('manualAttendanceTitle').textContent='Manual attendance - '+employee.name+' - '+state.month;
 $('manualAttendanceNote').textContent=employee.published_id?'Published salary: attendance is locked.':employee.missing_attendance+' days not entered. Select a status for each day on or after joining; future dates are unavailable.';
 const todayParts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
 const part=k=>todayParts.find(p=>p.type===k).value,today=part('year')+'-'+part('month')+'-'+part('day');
 $('manualAttendanceRows').innerHTML=employee.days.map(d=>{
 const disabled=Boolean(employee.published_id||d.day<employee.joining_date||d.day>today);
 return cells([esc(d.day),'<select aria-label="Attendance '+esc(d.day)+'" data-manual-day="'+esc(d.day)+'"'+(disabled?' disabled':'')+'><option value="">'+(d.day<employee.joining_date?'Before joining':d.day>today?'Upcoming':'Not entered')+'</option>'+['present','absent','weekoff','leave'].map(status=>'<option value="'+status+'"'+(d.entered&&d.status===status?' selected':'')+'>'+({present:'Present',absent:'Absent',weekoff:'Week Off',leave:'Leave'}[status])+'</option>').join('')+'</select>','<input aria-label="Note '+esc(d.day)+'" data-manual-note="'+esc(d.day)+'" value="'+esc(d.note||'')+'" maxlength="300"'+(disabled?' disabled':'')+'>']);
 }).join('');
 $('manualAttendanceError').textContent='';$('manualAttendanceForm').querySelector('button.primary').disabled=Boolean(employee.published_id);$('manualAttendanceDialog').showModal();
}
$('manualAttendanceForm').onsubmit=async event=>{
 event.preventDefault();const button=event.target.querySelector('button.primary');button.disabled=true;$('manualAttendanceError').textContent='';
 try{const days=Array.from($('manualAttendanceRows').querySelectorAll('[data-manual-day]')).filter(input=>!input.disabled&&input.value).map(input=>({day:input.dataset.manualDay,status:input.value,note:$('manualAttendanceRows').querySelector('[data-manual-note="'+input.dataset.manualDay+'"]').value}));if(!days.length)throw Error('Enter attendance for at least one day.');const result=await api('/manual-employees/'+manualAttendanceEmployee+'/attendance',{method:'PUT',body:JSON.stringify({month:manualAttendanceMonth,days})});$('manualAttendanceDialog').close();await refresh();message(result.message);}
 catch(error){$('manualAttendanceError').textContent=error.message;}finally{button.disabled=false;}
};
