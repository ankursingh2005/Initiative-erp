const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/home.html','utf8');
function setup(ok=true){
  const user={id:1,username:'Employee',store_id:1,outlet_name:'Old'};
  const message={textContent:'',classList:{add(){},remove(){}}};
  const context={userManagementUsers:[user],userManagementOutlets:[{id:1,name:'Old',status:'Active',latitude:26,longitude:80},{id:2,name:'New & Central',status:'Active',latitude:27,longitude:81},{id:3,name:'No GPS',status:'Active'}],outletUpdates:new Set(),role:'HR',document:{getElementById:()=>message},renderUserManagementTable(){},umFetch:async(path,options)=>{assert.equal(path,'/api/users/1/attendance-outlet');assert.equal(JSON.parse(options.body).store_id,2);return {ok,json:async()=>ok?{...user,store_id:2,outlet_name:'New & Central'}:{detail:'Unable to assign outlet'}}}};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('    function escapeOutletText'),html.indexOf('    function renderUserManagementTable')),context);
  return {context,user,message};
}
test('dropdown selects current outlet and excludes outlets without GPS',()=>{
  const t=setup(),markup=t.context.userOutletDropdown(t.user);
  assert.match(markup,/value="1" selected/);assert.match(markup,/New &amp; Central/);assert.ok(!markup.includes('No GPS'));
});
test('selecting an outlet saves immediately and updates the user',async()=>{
  const t=setup();await t.context.changeUserOutlet(1,{value:'2'});
  assert.equal(t.user.store_id,2);assert.match(t.message.textContent,/assigned to New & Central/);assert.equal(t.context.outletUpdates.size,0);
});
test('failed save restores previous outlet',async()=>{
  const t=setup(false),select={value:'2'};await t.context.changeUserOutlet(1,select);
  assert.equal(t.user.store_id,1);assert.equal(select.value,'1');assert.equal(t.message.textContent,'Unable to assign outlet');
});
test('home inline scripts parse',()=>{
  for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
});
