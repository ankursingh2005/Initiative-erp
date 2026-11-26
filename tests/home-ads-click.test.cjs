const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('welcome decoration cannot intercept Ads button clicks', () => {
  const home = fs.readFileSync('static/home.html', 'utf8');
  const decoration = home.match(/\.content-head::before\s*\{([^}]+)\}/)[1];
  assert.match(decoration, /pointer-events:\s*none/);
  assert.match(home, /\.content-head > \.ads-button\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*1/);
});

for (const role of ['Admin', 'HR', 'SalesExecutive', 'Owner', 'BrandPartner']) {
test(`${role}: Ads editor is available only to Admin and HR`, async () => {
  const nodes = [];
  function element(tag) {
    const fields = new Map();
    const node = { tagName: tag?.toUpperCase(), files: [], value: '', children: [],
      setAttribute() {}, append(...items) { this.children.push(...items); }, before() {},
      replaceChildren() { this.children = []; }, addEventListener() {},
      showModal() { this.open = true; }, close() { this.open = false; },
      querySelector(selector) { if (!fields.has(selector)) fields.set(selector, element('input')); return fields.get(selector); },
      querySelectorAll() { return []; } };
    nodes.push(node); return node;
  }
  const head = element('div'), stage = element('div');
  vm.runInNewContext(fs.readFileSync('static/home-ads.js', 'utf8'), {
    location: { pathname: '/erp/home' },
    localStorage: { getItem: key => key === 'role' ? role : 'token' },
    document: { body: element('body'), createElement: element,
      querySelector: selector => selector === '.content-head' ? head : stage },
    fetch: async () => { throw new Error('Server unavailable'); },
    console: { error() {} }, setInterval() {}, requestAnimationFrame() {}, URL,
  });
  const button = head.children[0];
  const editor = nodes.find(node => node.tagName === 'DIALOG');
  if (!['Admin', 'HR'].includes(role)) {
    assert.equal(editor, undefined);
    assert.equal(button, undefined);
    return;
  }
  assert.match(editor.innerHTML, /id="adsTitle">ADS<\/h2>/);
  assert.match(editor.innerHTML, /Close advertisement editor">&times;/);
  assert.ok(!editor.innerHTML.includes('Create your banner once'));
  const pending = button.onclick();
  assert.equal(editor.open, true);
  await pending;
  assert.equal(editor.querySelector('.ads-status').textContent, 'Server unavailable');
  editor.getBoundingClientRect = () => ({left: 100, right: 600, top: 100, bottom: 700});
  editor.onclick({target: editor, clientX: 200, clientY: 200});
  assert.equal(editor.open, true, 'clicking popup padding keeps it open');
  editor.onclick({target: editor.querySelector('form'), clientX: 200, clientY: 200});
  assert.equal(editor.open, true, 'clicking form keeps it open');
  editor.onclick({target: editor, clientX: 50, clientY: 200});
  assert.equal(editor.open, false, 'clicking outside closes the popup');
  editor.showModal();
  editor.querySelector('[data-close]').onclick();
  assert.equal(editor.open, false);
});
}
