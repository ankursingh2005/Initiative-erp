(() => {
  'use strict';
  const ERP=document.documentElement.dataset.erp==='true';
  const base=location.pathname.startsWith('/erp/')?'/erp':'';
  const erpUrl=path=>base+path;
  const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format((n||0)/100);
  const date=v=>v?new Date(v.length===10?v+'T00:00:00+05:30':v).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric',timeZone:'Asia/Kolkata'}):'—';
  const time=v=>v?new Date(v).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'}):'—';
  const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const initials=name=>name.split(/\s+/).slice(0,2).map(s=>s[0]||'').join('').toUpperCase();
  const badge=s=>`<span class="badge ${esc(s)}">${esc(s)}</span>`;
  const button=(label,action,id='',style='row-action')=>`<button type="button" class="${style}" data-action="${action}" data-id="${esc(id)}">${label}</button>`;
  const table=(headers,rows,empty='No records yet.')=>`<div class="table-scroll"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.join(''):`<tr><td colspan="${headers.length}" class="empty">${empty}</td></tr>`}</tbody></table></div>`;
  const stat=(label,value,note)=>`<div class="stat"><span class="stat-label">${label}</span><strong>${esc(value)}</strong><small>${note}</small></div>`;
  let user=null, csrf='', view='overview', registerMode=false, employees=[], attendance=[], leaves=[], earnings=[], payroll=[], audit=[], photoDraft=null, requestVersion=0;
  const manager=()=>user&&['hr','admin'].includes(user.role);
  const nav=[['overview','◈','Overview'],['employees','♙','Employees'],['attendance','◷','Attendance'],['leave','▤','Leave requests'],['identity','▣','Identity card'],['payroll','₹','Salary & payslips'],['rewards','☆','Incentives & bonus'],['profile','○','My profile'],['audit','≡','Activity log']];

  async function api(path,method='GET',body){
    const response=await fetch((ERP?erpUrl('/api/ems'):'/api')+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...(ERP?{Authorization:'Bearer '+localStorage.getItem('token')}:{})},body:body===undefined?undefined:JSON.stringify(body)});
    const data=await response.json().catch(()=>({}));
    if(!response.ok){
      if(response.status===401&&user){user=null;showAuth();}
      throw Error(Array.isArray(data.detail)?data.detail.map(x=>`${x.loc.at(-1)}: ${x.msg}`).join('; '):data.detail||'Unable to complete your request.');
    }
    return data;
  }
  function message(text,error=false,id='message'){$(id).textContent=text;$(id).classList.toggle('error',error);}
  function showAuth(){requestVersion++;if(ERP){location.replace(erpUrl('/login'));return;}$('auth').hidden=false;$('workspace').hidden=true;$('dialog').close();}
  function switchAuth(mode){registerMode=mode;$('registerName').hidden=!mode;$('authForm').elements.name.required=mode;$('authTitle').textContent=mode?'Your first day starts here.':'Good to see you.';$('authSubtitle').textContent=mode?'Register your details for HR approval.':'Sign in to your employee workspace.';$('authSubmit').textContent=mode?'Create account →':'Sign in →';$('loginTab').classList.toggle('active',!mode);$('registerTab').classList.toggle('active',mode);$('authForm').elements.password.autocomplete=mode?'new-password':'current-password';message('',false,'authMessage');}
  $('loginTab').onclick=()=>switchAuth(false);$('registerTab').onclick=()=>switchAuth(true);
  $('authForm').onsubmit=async e=>{e.preventDefault();$('authSubmit').disabled=true;message('',false,'authMessage');try{const values=Object.fromEntries(new FormData(e.target));if(registerMode){const result=await api('/register','POST',values);switchAuth(false);message(result.message,false,'authMessage');}else{delete values.name;const result=await api('/login','POST',values);user=result.user;csrf=result.csrf;await enter();}}catch(error){message(error.message,true,'authMessage');}finally{$('authSubmit').disabled=false;}};
  $('logout').onclick=async()=>{try{if(ERP){['token','role','username'].forEach(key=>localStorage.removeItem(key));location.replace(erpUrl('/login'));return;}await api('/logout','POST');user=null;csrf='';$('content').innerHTML='';$('authForm').reset();showAuth();}catch(error){message(error.message,true);}};
  async function enter(){
    $('auth').hidden=true;$('workspace').hidden=false;$('accountName').textContent=user.name+' · '+user.role;
    $('navigation').innerHTML=nav.filter(([key])=>manager()||!['employees','audit'].includes(key)).map(([key,icon,label])=>`<button class="nav-button" data-view="${key}"><span class="nav-icon">${icon}</span>${label}</button>`).join('');
    if(ERP){
      document.querySelectorAll('.brand').forEach(el=>el.href=erpUrl('/home'));
      $('navigation').insertAdjacentHTML('beforeend',`<a class="nav-button" href="${erpUrl('/home')}">← Back to ERP</a>`);
      $('accountName').textContent=user.name+' · '+user.erp_role;
    }
    $('today').textContent=date(today());
    await load('overview');
  }
  async function load(next=view){
    if(ERP&&next==='identity'){location.assign(erpUrl('/identity-card'));return;}
    const version=++requestVersion;view=next;message('');
    document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
    const label=nav.find(x=>x[0]===view)?.[2]||'Overview';$('pageTitle').textContent=label;$('breadcrumb').textContent='Workspace / '+label;$('pageEyebrow').textContent=manager()?'PEOPLE OPERATIONS':'EMPLOYEE SELF-SERVICE';
    $('content').innerHTML='<p class="empty">Loading your workspace…</p>';
    try{
      const result=await Promise.all([api('/me'),api('/attendance'),api('/leave'),api('/earnings'),api('/payroll'),manager()?api('/employees'):Promise.resolve([]),view==='audit'?api('/audit'):Promise.resolve([])]);
      if(version!==requestVersion)return;
      [user,attendance,leaves,earnings,payroll,employees,audit]=result;csrf=user.csrf||'';render();
    }catch(error){if(version!==requestVersion)return;$('content').innerHTML='<p class="empty">Unable to load this page. Please try again.</p>';message(error.message,true);}
  }
  function render(){
    const renderers={overview:overviewPage,employees:employeesPage,attendance:attendancePage,leave:leavePage,identity:identityPage,payroll:payrollPage,rewards:rewardsPage,profile:profilePage,audit:auditPage};
    $('content').innerHTML=(renderers[view]||overviewPage)();
    if(view==='employees'){$('employeeSearch').oninput=filterEmployees;$('employeeStatus').onchange=filterEmployees;}
    if(view==='identity')fitIdentity($('content'));
    if(view==='profile')bindProfile();
  }
  let overviewSelection='';
  const overviewStat=(label,value,note,key)=>`<button type="button" class="stat stat-button" data-action="overview-list" data-id="${key}" aria-expanded="${overviewSelection===key}" aria-controls="overviewDetails"><span class="stat-label">${label}<span aria-hidden="true">?</span></span><strong>${esc(value)}</strong><small>${note}</small></button>`;
  function overviewDetails(){
    if(!manager()||!overviewSelection)return '';
    const titles={active:'Active employees',pending:'Pending approval',present:'Present today',leave:'Pending leave requests'};
    const activeIds=new Set(employees.filter(e=>e.status==='active').map(e=>e.id));
    let rows;
    if(overviewSelection==='leave'){
      rows=leaves.filter(l=>l.status==='pending').map(l=>({name:l.name,detail:l.kind+' ? '+date(l.start_date)+' ? '+date(l.end_date),status:l.status,action:button('View requests','navigate','leave')}));
    }else{
      const checkedIn=new Map(attendance.filter(a=>a.day===today()&&activeIds.has(a.user_id)).map(a=>[a.user_id,a]));
      rows=employees.filter(e=>overviewSelection==='present'?checkedIn.has(e.id):e.status===overviewSelection).map(e=>({name:e.name,detail:[e.employee_id,e.department,e.outlet,overviewSelection==='present'?'Check-in: '+time(checkedIn.get(e.id).check_in):e.email].filter(Boolean).join(' ? '),status:e.status,action:button('Manage','employee',e.id)}));
    }
    return `<section class="panel overview-details" id="overviewDetails" tabindex="-1" aria-labelledby="overviewDetailsTitle"><div class="panel-head"><div><h2 id="overviewDetailsTitle">${titles[overviewSelection]}</h2><p>${rows.length} ${overviewSelection==='leave'?'requests':'users'}</p></div>${button('Close','overview-close','','secondary')}</div><div class="overview-people">${rows.map(r=>`<article class="overview-person"><span class="avatar" aria-hidden="true">${esc(initials(r.name))}</span><div class="overview-person-info"><b>${esc(r.name)}</b><p>${esc(r.detail)}</p></div>${badge(r.status)}${r.action}</article>`).join('')||'<p class="empty">No matching users or requests.</p>'}</div></section>`;
  }
  function overviewPage(){
    const ownToday=attendance.find(a=>a.user_id===user.id&&a.day===today()),month=today().slice(0,7);
    const pending=leaves.filter(l=>l.status==='pending');
    const monthPayroll=payroll.filter(p=>p.month===month);
    const activeEmployeeIds=new Set(employees.filter(e=>e.status==='active').map(e=>e.id));
    const presentToday=new Set(attendance.filter(a=>a.day===today()&&activeEmployeeIds.has(a.user_id)).map(a=>a.user_id)).size;
    const metrics=manager()?[overviewStat('ACTIVE EMPLOYEES',activeEmployeeIds.size,'Across your organisation','active'),overviewStat('PENDING APPROVAL',employees.filter(e=>e.status==='pending').length,'New employee registrations','pending'),overviewStat('PRESENT TODAY',presentToday,'Active employee check-ins','present'),overviewStat('LEAVE REQUESTS',pending.length,'Awaiting a decision','leave')]:[stat('DAYS PRESENT',attendance.filter(a=>a.day.startsWith(month)).length,'This calendar month'),stat('LEAVE REQUESTS',pending.length,'Awaiting HR approval'),stat('LATEST NET PAY',payroll.length?money(payroll[0].net):'—','Latest published payslip'),stat('REWARDS',money(earnings.filter(e=>e.month===month).reduce((s,e)=>s+e.amount,0)),'Approved this month')];
    return `<div class="welcome"><div><h2>Hello, ${esc(user.name.split(' ')[0])}.</h2><p>${manager()?'Your people, attendance and approvals, all in view.':'Your workday, without the paperwork.'}</p></div><span class="welcome-mark" aria-hidden="true">✳</span></div><div class="stats">${metrics.join('')}</div>${overviewDetails()}<div class="two-columns"><div><section class="panel"><div class="panel-head"><div><h2>My attendance today</h2><p>${date(today())}</p></div>${badge(ownToday?(ownToday.check_out?'completed':'active'):'pending')}</div><div class="attendance-clock">${ownToday?time(ownToday.check_in):'Ready for the day?'}</div><p class="subtext">${ownToday?(ownToday.check_out?'Checked out at '+time(ownToday.check_out):'Your check-in is recorded. Check out when you finish.'):'Record your check-in to start your workday.'}</p><div class="actions">${!ownToday?button('Check in →','check-in','','primary'):!ownToday.check_out?button('Check out','check-out','','primary'):''}${button('View attendance','navigate','attendance','secondary')}</div></section><section class="panel"><div class="panel-head"><h2>${manager()?'Latest leave requests':'My latest requests'}</h2>${button('View all','navigate','leave')}</div>${leaves.slice(0,4).map(l=>`<div class="activity-item"><span class="avatar">${esc(initials(l.name))}</span><div>${esc(l.name)}<small class="subtext"> · ${esc(l.kind)}<br>${date(l.start_date)} – ${date(l.end_date)}</small></div>${badge(l.status)}</div>`).join('')||'<p class="empty">No leave requests yet.</p>'}</section></div><div><section class="panel"><div class="panel-head"><h2>Quick access</h2></div><div class="quick-links">${button('My identity card<span>Print your employee ID</span>','navigate','identity','quick-link')}${button('Request leave<span>Plan your time away</span>','new-leave','','quick-link')}${button('Salary & payslips<span>View published salary</span>','navigate','payroll','quick-link')}${button('Incentives & bonus<span>Your extra earnings</span>','navigate','rewards','quick-link')}</div></section><section class="panel"><div class="panel-head"><h2>${manager()?'Payroll this month':'My employment'}</h2></div>${manager()?`<div class="attendance-clock">${money(monthPayroll.reduce((s,p)=>s+p.net,0))}</div><p class="subtext">${monthPayroll.length} payslips published for ${esc(month)}.</p>${button('Manage payroll','navigate','payroll','secondary')}`:`<p class="subtext">Employee ID<br><b>${esc(user.employee_id)}</b></p><p class="subtext">Department / Outlet<br><b>${esc(user.department||'Not assigned')} / ${esc(user.outlet||'Not assigned')}</b></p><p class="subtext">Joining date<br><b>${date(user.joining_date)}</b></p>`}</section></div></div>`;
  }
  function employeeRows(list){return list.map(e=>`<tr><td><div class="person-cell"><span class="avatar">${esc(initials(e.name))}</span><div>${esc(e.name)}<small>${esc(e.email)}</small></div></div></td><td>${esc(e.employee_id)}</td><td>${esc(e.department||'—')}<small>${esc(e.outlet)}</small></td><td>${esc(e.role)}</td><td>${badge(e.status)}</td><td>${button('Manage','employee',e.id)}</td></tr>`);}
  function employeesPage(){return `<section class="panel"><div class="panel-head"><div><h2>Employee directory</h2><p>Approve registrations and assign roles, departments and outlets.</p></div><span class="badge">${employees.length} users</span></div><div class="toolbar"><input id="employeeSearch" type="search" placeholder="Search name, email or employee ID" aria-label="Search employees"><select id="employeeStatus" aria-label="Filter employee status"><option value="">All statuses</option><option>pending</option><option>active</option><option>inactive</option></select></div><div id="employeeTable">${table(['Employee','ID','Department','Role','Status',''],employeeRows(employees))}</div></section>`;}
  function filterEmployees(){const q=$('employeeSearch').value.toLowerCase(),s=$('employeeStatus').value;$('employeeTable').innerHTML=table(['Employee','ID','Department','Role','Status',''],employeeRows(employees.filter(e=>(!s||e.status===s)&&[e.name,e.email,e.employee_id,e.department,e.outlet].join(' ').toLowerCase().includes(q))),'No employees match your search.');}
  function attendancePage(){return `<section class="panel"><div class="panel-head"><div><h2>${manager()?'Team attendance':'My attendance'}</h2><p>Times are recorded in India Standard Time. Latest 500 records.</p></div><div class="actions">${button('Check in','check-in','','primary')}${button('Check out','check-out','','secondary')}</div></div>${table(['Employee','Date','Check in','Check out','Hours'],attendance.map(a=>`<tr><td>${esc(a.name)}</td><td>${date(a.day)}</td><td>${time(a.check_in)}</td><td>${time(a.check_out)}</td><td>${a.check_out?((new Date(a.check_out)-new Date(a.check_in))/3600000).toFixed(2):'In progress'}</td></tr>`))}</section>`;}
  function leavePage(){return `<section class="panel"><div class="panel-head"><div><h2>${manager()?'Leave approvals':'My leave requests'}</h2><p>Submit dates and a reason. HR reviews each request.</p></div>${button('＋ Request leave','new-leave','','primary')}</div>${table(['Employee','Dates','Type','Reason','Status',''],leaves.map(l=>`<tr><td>${esc(l.name)}</td><td>${date(l.start_date)}<small>to ${date(l.end_date)}</small></td><td>${esc(l.kind)}</td><td title="${esc(l.reason)}">${esc(l.reason.slice(0,55))}</td><td>${badge(l.status)}</td><td>${manager()&&l.status==='pending'&&l.user_id!==user.id?button('Approve','approve-leave',l.id)+' '+button('Reject','reject-leave',l.id):''}</td></tr>`))}</section>`;}
  function identityMarkup(){return `<div class="identity-layout"><article class="id-card"><div class="id-head">EMS<small>EMPLOYEE IDENTITY CARD</small></div>${user.photo?`<img class="id-photo" src="${esc(user.photo)}" alt="Employee portrait">`:`<div class="id-photo">${esc(initials(user.name))}</div>`}<div class="id-body"><b class="id-name">${esc(user.name)}</b><span class="id-title">${esc(user.designation||'Employee')}</span><div class="id-line">EMPLOYEE ID<b>${esc(user.employee_id)}</b></div><div class="id-line">DEPARTMENT<b>${esc(user.department||'Not assigned')}</b></div><div class="id-line">OUTLET<b>${esc(user.outlet||'Not assigned')}</b></div></div><div class="id-footer">EMPLOYEE MANAGEMENT SYSTEM</div></article><article class="id-card id-back"><h2>EMS</h2><p class="subtext">EMPLOYEE MANAGEMENT SYSTEM</p><div class="id-line">EMPLOYEE ID<b>${esc(user.employee_id)}</b></div><div class="id-line">JOINING DATE<b>${date(user.joining_date)}</b></div><div class="id-line">CONTACT NUMBER<b>${esc(user.phone||'Not added')}</b></div><div class="id-line">ACCOUNT STATUS<b>${esc(user.status)}</b></div><div class="id-footer">PROPERTY OF THE ISSUING ORGANISATION</div></article></div>`;}
  function fitIdentity(root){root.querySelectorAll('.id-name,.id-title').forEach(el=>{let size=parseFloat(getComputedStyle(el).fontSize);while(el.scrollWidth>el.clientWidth&&size>2){size-=.25;el.style.fontSize=size+'px';}});}
  function identityPage(){return `<section class="panel"><div class="panel-head"><div><h2>My employee identity</h2><p>Front and back print together. Update your photo in My Profile.</p></div>${button('Print / Save PDF','print-id','','primary')}</div>${identityMarkup()}</section>`;}
  function payrollPage(){return `<section class="panel"><div class="panel-head"><div><h2>${manager()?'Salary register':'My payslips'}</h2><p>Published monthly salary, including approved incentives and bonuses.</p></div>${manager()?button('＋ Publish payslip','new-payroll','','primary'):''}</div>${table(['Employee','Month','Gross','Deductions','Net pay','Status',''],payroll.map(p=>`<tr><td>${esc(p.name)}</td><td>${esc(p.month)}</td><td>${money(p.basic+p.allowances+p.incentives+p.bonuses)}</td><td>${money(p.deductions)}</td><td><b>${money(p.net)}</b></td><td>${badge(p.status)}</td><td>${button('Payslip','payslip',p.id)} ${manager()&&p.status==='published'?button('Mark paid','paid',p.id):''}</td></tr>`))}</section>`;}
  function rewardsPage(){return `<div class="stats">${stat('INCENTIVES',money(earnings.filter(e=>e.kind==='incentive').reduce((s,e)=>s+e.amount,0)),'All recorded incentives')}${stat('BONUSES',money(earnings.filter(e=>e.kind==='bonus').reduce((s,e)=>s+e.amount,0)),'All recorded bonuses')}</div><section class="panel"><div class="panel-head"><div><h2>Incentives & bonus</h2><p>HR-approved earnings are included when the month’s payslip is published.</p></div>${manager()?button('＋ Add earning','new-earning','','primary'):''}</div>${table(['Employee','Month','Type','Amount','Note'],earnings.map(e=>`<tr><td>${esc(e.name)}</td><td>${esc(e.month)}</td><td>${badge(e.kind)}</td><td>${money(e.amount)}</td><td>${esc(e.note)}</td></tr>`))}</section>`;}
  function profilePage(){photoDraft=user.photo;return `<div class="two-columns"><section class="panel"><div class="panel-head"><h2>Personal details</h2></div><form id="profileForm">${user.photo?`<img class="profile-photo" src="${esc(user.photo)}" alt="Current profile photo">`:`<div class="profile-photo">${esc(initials(user.name))}</div>`}<label>Full name<input name="name" value="${esc(user.name)}" required minlength="2" maxlength="120"></label><label>Mobile number<input name="phone" type="tel" value="${esc(user.phone)}" maxlength="25"></label><label>Profile photo<input id="profilePhoto" type="file" accept="image/jpeg,image/png,image/webp"><small>JPG, PNG or WebP, up to 2 MB.</small></label><div class="actions">${button('Remove photo','remove-photo','','secondary')}<button class="primary">Save profile</button></div></form></section><section class="panel"><h2>Employment details</h2><p class="subtext">Contact HR to correct these details.</p>${[['Employee ID',user.employee_id],['Email',user.email],['Role',user.role],['Department',user.department],['Designation',user.designation],['Outlet',user.outlet],['Joining date',date(user.joining_date)]].map(([label,value])=>`<div class="activity-item"><span>${label}</span><b>${esc(value||'Not assigned')}</b></div>`).join('')}</section></div>`;}
  function bindProfile(){
    if(ERP){
      $('profileForm').querySelectorAll('input,button').forEach(el=>el.disabled=true);
      $('profileForm').insertAdjacentHTML('afterend','<p class="subtext">Your details come from ERP User Management and Identity Cards. Contact Admin or HR for corrections.</p>'+button('Open identity card','navigate','identity','secondary'));
      return;
    }
    $('profilePhoto').onchange=async e=>{const f=e.target.files[0];if(!f)return;if(f.size>2_000_000||!['image/jpeg','image/png','image/webp'].includes(f.type)){e.target.value='';message('Choose a JPG, PNG or WebP photo under 2 MB.',true);return;}try{photoDraft=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(f);});message('Photo selected. Save your profile to apply it.');}catch{message('Unable to read the photo.',true);}};
    $('profileForm').onsubmit=async e=>{e.preventDefault();const submit=e.submitter;submit.disabled=true;try{const result=await api('/me','PUT',{...Object.fromEntries(new FormData(e.target)),photo:photoDraft});await load();$('accountName').textContent=user.name+' · '+user.role;message(result.message);}catch(error){message(error.message,true);}finally{submit.disabled=false;}};
  }
  function auditPage(){return `<section class="panel"><div class="panel-head"><div><h2>Activity log</h2><p>Latest 300 recorded actions.</p></div></div>${table(['When','By','Action','Record'],audit.map(a=>`<tr><td>${date(a.created_at)} ${time(a.created_at)}</td><td>${esc(a.name||'System')}</td><td>${esc(a.action.replaceAll('_',' '))}</td><td>${esc(a.target)}</td></tr>`))}</section>`;}
  const input=(label,name,type='text',value='',extra='')=>`<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
  const select=(label,name,values,value='')=>`<label>${label}<select name="${name}">${values.map(v=>{const [key,text]=Array.isArray(v)?v:[v,v];return `<option value="${esc(key)}" ${String(key)===String(value)?'selected':''}>${esc(text)}</option>`;}).join('')}</select></label>`;
  const employeeSelect=()=>select('Employee','user_id',employees.filter(e=>e.status==='active').map(e=>[e.id,e.name+' · '+e.employee_id]));
  function modal(title,fields,submit){
    $('dialogTitle').textContent=title;$('dialogForm').innerHTML=fields+'<button class="primary wide">Save</button>';message('',false,'dialogMessage');$('dialog').showModal();
    $('dialogForm').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;try{const result=await submit(Object.fromEntries(new FormData(e.target)));$('dialog').close();await load();message(result.message);}catch(error){message(error.message,true,'dialogMessage');}finally{e.submitter.disabled=false;}};
  }
  $('closeDialog').onclick=()=>$('dialog').close();
  function payslipMarkup(p){return `<article class="payslip"><div class="payslip-header"><div><h2>EMS</h2><p>Employee Management System</p></div><div><h2>Payslip</h2><p>${esc(p.month)}</p></div></div><h3>${esc(p.name)}</h3><p class="subtext">Employee ID: ${esc(p.employee_id||('EMS-'+String(p.user_id).padStart(5,'0')))} · Status: ${esc(p.status)}</p>${table(['Component','Amount'],[['Basic salary',p.basic],['Allowances',p.allowances],['Incentives',p.incentives],['Bonus',p.bonuses],['Deductions',-p.deductions]].map(([label,value])=>`<tr><td>${label}</td><td>${money(value)}</td></tr>`))}<div class="payslip-total"><b>Net pay</b><b>${money(p.net)}</b></div><p class="payslip-note">Published ${date(p.created_at)}. Salary amounts and deductions are entered and approved by HR.</p></article>`;}
  async function printMarkup(markup){const area=$('printArea');area.innerHTML=markup;area.style.cssText='display:block;position:fixed;left:-10000px';await Promise.all([...area.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));fitIdentity(area);area.removeAttribute('style');window.print();}
  addEventListener('afterprint',()=>{$('printArea').innerHTML='';});
  document.addEventListener('click',async e=>{
    const navButton=e.target.closest('[data-view]');if(navButton){load(navButton.dataset.view);return;}
    const b=e.target.closest('[data-action]');if(!b)return;
    const {action,id}=b.dataset;
    try{
      if(action==='overview-list'&&manager()){overviewSelection=id;render();$('overviewDetails').focus();$('overviewDetails').scrollIntoView({behavior:'smooth',block:'start'});return;}
      if(action==='overview-close'){const previous=overviewSelection;overviewSelection='';render();document.querySelector('[data-action="overview-list"][data-id="'+previous+'"]').focus();return;}
      if(action==='navigate'){await load(id);return;}
      if(action==='employee'){
        if(ERP){if(user.can_manage_users){location.assign(erpUrl('/home#user-management'));}else{message('User accounts are managed by Admin and HR. Use Identity Cards for card corrections.');}return;}
        const employee=employees.find(x=>x.id===Number(id));
        modal('Manage '+employee.name,`<div class="form-grid">${select('Account status','status',['pending','active','inactive'],employee.status)}${select('Role','role',user.role==='admin'?['employee','hr','admin']:[employee.role],employee.role)}${input('Department','department','text',employee.department,'maxlength="80"')}${input('Designation','designation','text',employee.designation,'maxlength="100"')}${input('Outlet / Office','outlet','text',employee.outlet,'maxlength="80"')}${input('Joining date','joining_date','date',employee.joining_date||'')}</div>`,d=>api('/employees/'+id,'PUT',{...d,joining_date:d.joining_date||null}));return;
      }
      if(action==='new-leave'){modal('Request leave',`<div class="form-grid">${input('From','start_date','date',today(),'required')}${input('To','end_date','date',today(),'required')}</div>${select('Leave type','kind',['Casual','Sick','Earned','Unpaid'])}<label>Reason<textarea name="reason" required minlength="3" maxlength="500"></textarea></label>`,d=>api('/leave','POST',d));return;}
      if(action==='new-earning'){modal('Add an approved earning',employeeSelect()+`<div class="form-grid">${input('Month','month','month',today().slice(0,7),'required')}${select('Type','kind',['incentive','bonus'])}</div>`+input('Amount (₹)','amount','number','','required min="0.01" max="10000000" step="0.01"')+input('Reason / reference','note','text','','required minlength="3" maxlength="300"'),d=>api('/earnings','POST',d));return;}
      if(action==='new-payroll'){modal('Publish monthly payslip','<p class="subtext">Approved incentives and bonuses for this month are added automatically. Published payslips are locked.</p>'+employeeSelect()+input('Month','month','month',today().slice(0,7),'required')+`<div class="form-grid">${input('Basic salary (₹)','basic','number','','required min="0" max="10000000" step="0.01"')}${input('Allowances (₹)','allowances','number','0','required min="0" max="10000000" step="0.01"')}${input('Deductions (₹)','deductions','number','0','required min="0" max="10000000" step="0.01"')}</div>`,d=>api('/payroll','POST',d));return;}
      if(action==='payslip'){await printMarkup(payslipMarkup(payroll.find(p=>p.id===Number(id))));return;}
      if(action==='print-id'){await printMarkup(identityMarkup());return;}
      if(action==='remove-photo'){photoDraft=null;$('profilePhoto').value='';message('Photo removed from your draft. Save your profile to apply it.');return;}
      b.disabled=true;let result;
      if(action==='check-in'||action==='check-out'){
        if(ERP){location.assign(erpUrl('/attendance'));return;}
        result=await api('/attendance/'+action,'POST');
      }
      if(action==='approve-leave'||action==='reject-leave')result=await api('/leave/'+id,'PUT',{status:action==='approve-leave'?'approved':'rejected'});
      if(action==='paid'){if(!confirm('Confirm that this salary has already been paid outside EMS?'))return;result=await api('/payroll/'+id+'/paid','PUT');}
      if(result){await load();message(result.message);}
    }catch(error){message(error.message,true);}finally{b.disabled=false;}
  });
  if(ERP&&!localStorage.getItem('token')){showAuth();return;}
  if(ERP&&localStorage.getItem('role')==='BrandPartner'){location.replace(erpUrl('/home'));return;}
  api('/me').then(async result=>{user=result;csrf=result.csrf||'';await enter();}).catch(()=>showAuth());
})();
