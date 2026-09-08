const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app-shell.js', 'utf8');
const guard = source.slice(source.lastIndexOf('(function(){const role='));
function redirectFor(role, pathname) {
  let redirect;
  vm.runInNewContext(guard, {
    localStorage: { getItem: key => key === 'role' ? role : 'test-token' },
    location: { pathname, replace: value => { redirect = value; } },
    document: { readyState: 'loading', addEventListener() {} }
  });
  return redirect;
}
test('Category Managers can open all PO route variants', () => {
  for (const path of ['/purchase-orders','/purchase-orders.html','/erp/purchase-orders','/erp/purchase-orders.html']) {
    assert.equal(redirectFor('CategoryManager', path), undefined);
  }
});
test('other restricted roles and unrelated pages remain restricted', () => {
  assert.equal(redirectFor('BrandManager','/purchase-orders'),'/home');
  assert.equal(redirectFor('CategoryManager','/analytics'),'/home');
  assert.equal(redirectFor('SupportingStaff','/erp/purchase-orders'),'/erp/home');
  assert.equal(redirectFor('Admin','/purchase-orders'),undefined);
  assert.equal(redirectFor('CategoryManager','/dashboard'),undefined);
});
