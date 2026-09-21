const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const shell=fs.readFileSync('static/app-shell.js','utf8');
const guard=shell.slice(0,shell.indexOf('})();')+5);
test('shared navigation script parses',()=>{new vm.Script(shell)});
test('project pages allow only the requested roles, including prefixed URLs',()=>{
  for(const role of ['Admin','HR','Owner','MISExecutive','Accounts','Employee','CategoryManager','BrandPartner']) {
    for(const [page,allowed] of [['ems',['Admin','HR']],['purchase-orders',['Admin','HR','MISExecutive','Accounts']]]) {
      for(const base of ['', '/erp']) {
        let redirected=false;
        vm.runInNewContext(guard,{localStorage:{getItem:()=>role},location:{pathname:base+'/'+page+'.html',replace:url=>{redirected=true;assert.equal(url,base+'/home')}}});
        assert.equal(redirected,!allowed.includes(role),role+' '+page);
      }
    }
  }
});
test('all purchase order API handlers have the strict permission dependency',()=>{
  const source=fs.readFileSync('main.py','utf8');
  const routes=source.split('\n').filter(line=>/^@app\./.test(line)&&line.includes('"/api/purchase-orders'));
  assert.ok(routes.length>=7);
  for(const line of routes)assert.match(line,/Depends\(auth.require_purchase_order_access\)/);
});
