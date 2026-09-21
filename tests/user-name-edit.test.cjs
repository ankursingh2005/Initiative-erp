const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync('static/home.html', 'utf8');
function setup(role, targetRole = 'Employee', ok = true) {
  const elements = {};
  const element = id => elements[id] ||= {value:'', disabled:false, textContent:'', classList:{add(){}}, showModal(){this.open=true;}, close(){this.open=false;}};
  const user = {id:1, username:'Old name', email:'e@example.test', role:targetRole};
  const context = {role, userManagementUsers:[user], userManagementActorId:1,
    document:{getElementById:element}, localStorage:{setItem(){}}, renderUserManagementTable(){},
    umFetch:async (path, options) => {
      assert.equal(path, '/api/users/1/details');
      assert.equal(options.method, 'PATCH');
      const body = JSON.parse(options.body);
      assert.equal(body.username, 'New name');
      return {ok, json:async()=>ok ? {...user, ...body} : {detail:'Save failed'}};
    }};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('    let editUserTargetId'), html.indexOf('    function renderUserManagementTable')), context);
  return {context, element, user};
}
for (const role of ['Admin','HR']) test(`${role} can open and save username`, async()=>{
  const t = setup(role);
  t.context.openEditUser(1);
  assert.equal(t.element('editUserDialog').open, true);
  assert.equal(t.element('editUserName').value, 'Old name');
  t.element('editUserName').value = ' New name ';
  await t.context.saveUserDetails({preventDefault(){}});
  assert.equal(t.user.username, 'New name');
  assert.equal(t.element('userName').textContent, 'New name');
  assert.equal(t.element('editUserDialog').open, false);
});
test('unauthorized roles and HR editing Admin cannot open editor',()=>{
  for (const [role,target] of [['Owner','Employee'],['Employee','Employee'],['HR','Admin']]) {
    const t=setup(role,target); t.context.openEditUser(1);
    assert.notEqual(t.element('editUserDialog').open,true);
  }
});
test('failed save keeps original username and shows error',async()=>{
  const t=setup('Admin','Employee',false); t.context.openEditUser(1);
  t.element('editUserName').value='New name';
  await t.context.saveUserDetails({preventDefault(){}});
  assert.equal(t.user.username,'Old name');
  assert.equal(t.element('editUserError').textContent,'Save failed');
  assert.equal(t.element('editUserDialog').open,true);
  assert.equal(t.element('editUserSave').disabled,false);
});
