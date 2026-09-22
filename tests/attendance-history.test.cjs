const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
test('BrandPartner heading shows assigned companies and a clear unassigned fallback',()=>{
  const context={};vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('function attendanceEmployeeTitle('),html.indexOf('async function openAdminRecord(')),context);
  assert.equal(context.attendanceEmployeeTitle({username:'ravi pal',role:'BrandPartner',brand_names:['Samsung']}),'ravi pal (BrandPartner – Samsung)');
  assert.equal(context.attendanceEmployeeTitle({username:'ravi pal',role:'BrandPartner',brand_names:['Samsung','LG']}),'ravi pal (BrandPartner – Samsung, LG)');
  assert.equal(context.attendanceEmployeeTitle({username:'ravi pal',role:'BrandPartner'}),'ravi pal (BrandPartner)');
  assert.equal(context.attendanceEmployeeTitle({username:'Priyanshu',role:'ACTechnicianA'}),'Priyanshu (AC Technician A)');
});
test('employee history loads by permanent ID after a rename, with older dates available',async()=>{
  const select={value:'',disabled:true},detail={},heading={},close={};
  const modal={dataset:{},isConnected:true,querySelector:q=>({'h2':heading,'.record-detail':detail,'.record-date':select,'.record-close':close}[q])};
  const calls=[];
  const context={document:{createElement:()=>modal,body:{appendChild(){}}},today:'2026-09-21',
    safeText:String,localStorage:{getItem:()=> 'token'},requestAnimationFrame:fn=>fn(),
    fetch:async url=>{calls.push(url);return{ok:true,json:async()=>({user_id:7,username:'Renamed employee',history:[{id:100,attendance_date:'2026-09-21'},{id:99,attendance_date:'2026-08-01'}]})}},
    fetchSelfieRecord:async id=>({attendance_date:id==='99'?'2026-08-01':'2026-09-21',checkin_at:'09:00',checkout_at:'18:00',checkin_selfie:'photo-'+id}),
    formatTime:String,workingHours:()=> '9 hours',selfieTile:(label,photo)=>photo||'',bindSelfieZoom(){}};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('function attendanceEmployeeTitle('),html.indexOf('</script>',html.indexOf('async function openAdminRecord('))),context);
  await context.openAdminRecord({dataset:{userId:'7',username:'Old name'},children:[{textContent:'Old name'}],cells:[],closest:()=>null});
  assert.deepEqual(calls,['/api/attendance/users/7/history']);
  assert.equal(heading.textContent,'Renamed employee');
  assert.equal(select.disabled,false);
  assert.match(select.innerHTML,/2026-08-01/);
  assert.match(select.innerHTML,/2026-09-21/);
  assert.equal(select.value,'100');
  select.value='99';
  await select.onchange();
  assert.match(detail.innerHTML,/2026-08-01/);
  assert.match(detail.innerHTML,/9 hours/);
  assert.match(detail.innerHTML,/photo-99/);
  // A slower response for a previously selected date must not replace the latest date.
  let resolveOld;
  context.fetchSelfieRecord=id=>id==='99'?new Promise(resolve=>{resolveOld=resolve}):Promise.resolve({attendance_date:'2026-09-21'});
  const oldRequest=select.onchange();
  select.value='100';await select.onchange();
  resolveOld({attendance_date:'2026-08-01'});await oldRequest;
  assert.match(detail.innerHTML,/2026-09-21/);
  assert.doesNotMatch(detail.innerHTML,/2026-08-01/);
});
test('all dashboard row renderers include permanent user IDs',()=>{
  const rows=html.match(/<tr class="admin-row"[^>]*>/g);
  assert.equal(rows.length,3);
  for(const row of rows)assert.match(row,/data-user-id=/);
});
