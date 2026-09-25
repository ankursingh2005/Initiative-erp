const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/home.html','utf8');
function setup(ok=true){
  const user={id:1,username:'Employee',role:'Employee'},message={classList:{add(){},remove(){}}},toast={className:'',classList:{add(){},remove(){}},setAttribute(){},textContent:''};
  const context={userManagementUsers:[user],userManagementRoles:['Employee','ACTechnicianA','ACTechnicianB'],userManagementActorId:2,roleUpdates:new Set(),role:'HR',escapeOutletText:String,document:{body:{appendChild(node){context.toast=node}},createElement(){return toast},getElementById:id=>id==='userManagementToast'?context.toast:message},renderUserManagementTable(){},renderUserCountSummary(data){context.counts=data;},setTimeout(fn){context.timeout=fn;return 1},clearTimeout(){},umFetch:async(path,options)=>{assert.equal(path,'/api/users/1/role');assert.equal(JSON.parse(options.body).role,'ACTechnicianB');return {ok,json:async()=>ok?{role:'ACTechnicianB'}:{detail:'Invalid role'}}}};
  vm.createContext(context);vm.runInContext(html.slice(html.indexOf('    function userRoleDropdown'),html.indexOf('    function renderUserManagementTable')),context);
  return {context,user,message};
}
test('role dropdown shows current and available roles',()=>{
  const t=setup(),markup=t.context.userRoleDropdown(t.user);
  assert.match(markup,/value="Employee" selected/);assert.match(markup,/AC Technician B/);
});
test('role save updates user and role totals',async()=>{
  const t=setup();await t.context.changeUserRole(1,{value:'ACTechnicianB'});
  assert.equal(t.user.role,'ACTechnicianB');assert.equal(t.context.counts.by_role.ACTechnicianB,1);
  assert.equal(t.context.toast.textContent,'Employee is now assigned the ACTechnicianB role.');
});
test('role save failure restores the original role',async()=>{
  const t=setup(false),select={value:'ACTechnicianB'};await t.context.changeUserRole(1,select);
  assert.equal(t.user.role,'Employee');assert.equal(select.value,'Employee');assert.equal(t.message.textContent,'Invalid role');
});
test('changing own role updates stored role and reloads navigation',async()=>{
  const t=setup();t.context.userManagementActorId=1;let stored,reloaded=false;
  t.context.localStorage={setItem:(key,value)=>{stored=value;}};t.context.location={reload:()=>{reloaded=true;}};
  await t.context.changeUserRole(1,{value:'ACTechnicianB'});
  assert.equal(stored,'ACTechnicianB');assert.equal(reloaded,true);
});

test('brand roles save selected brands and role in one request',async()=>{
  for(const next of ['BrandPartner','BrandManager']){
    const t=setup();let requests=0;
    t.context.chooseRoleBrands=async()=>[2,5];
    t.context.umFetch=async(path,options)=>{requests++;assert.deepEqual(JSON.parse(options.body),{role:next,brand_ids:[2,5]});return{ok:true,json:async()=>({role:next,brand_ids:[2,5]})}};
    await t.context.changeUserRole(1,{value:next});
    assert.equal(requests,1);assert.equal(t.user.role,next);assert.deepEqual(t.user.brand_ids,[2,5]);
  }
});
test('cancelling brand selection never saves the role',async()=>{
  const t=setup(),select={value:'BrandPartner'};let called=false;
  t.context.chooseRoleBrands=async()=>null;t.context.umFetch=async()=>{called=true};
  await t.context.changeUserRole(1,select);
  assert.equal(called,false);assert.equal(t.user.role,'Employee');assert.equal(select.value,'Employee');assert.equal(t.context.roleUpdates.size,0);
});
