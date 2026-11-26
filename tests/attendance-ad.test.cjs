const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function setup(ad) {
  const nodes = [], calls = []; let tick, inserted;
  const anchor = {after(node) {inserted = node;}};
  vm.runInNewContext(fs.readFileSync('static/attendance-ad.js', 'utf8'), {
    localStorage: {getItem: () => 'signed-in'}, location: {pathname: '/erp/attendance'},
    document: {hidden: false, querySelector: () => anchor, addEventListener() {},
      createElement(tag) {const node = {tag, clientWidth: 650, children: [], style: {setProperty() {}},
        append(child) {this.children.push(child);}, replaceChildren() {this.children = [];}, setAttribute() {}}; nodes.push(node); return node;}},
    window: {addEventListener() {}}, setInterval(fn) {tick = fn;},
    URL: {createObjectURL: () => 'blob:test-offer', revokeObjectURL() {}},
    fetch: async (url, options) => {calls.push({url, options}); return {ok: true, json: async () => ad, blob: async () => ({})};}
  });
  await new Promise(resolve => setImmediate(resolve));
  return {nodes, calls, strip: inserted, tick};
}

test('attendance shows offer heading, message and a corner media thumbnail', async () => {
  const app = await setup({visible: true, title: 'November offers', message: 'Earn rewards', media_type: 'video/mp4'});
  assert.equal(app.strip.hidden, false);
  assert.equal(app.strip.children[0].children[0].textContent, '\u2726 SPECIAL OFFER');
  assert.equal(app.strip.children[0].children[1].textContent, 'November offers');
  assert.equal(app.strip.children[1].children[0].textContent, 'Earn rewards');
  const thumbnail = app.strip.children[0].children[2];
  assert.equal(thumbnail.hidden, false);
  assert.equal(thumbnail.children[0].tag, 'video');
  assert.equal(thumbnail.children[0].src, 'blob:test-offer');
  assert.equal(app.calls[1].url, '/erp/api/home-ad/media');
  assert.equal(app.calls[0].url, '/erp/api/home-ad');
  assert.equal(app.calls[0].options.headers.Authorization, 'Bearer signed-in');
});

test('hiding, clearing or removing the message removes the attendance strip', async () => {
  const ad = {visible: true, message: 'Offer'};
  const app = await setup(ad);
  for (const next of [{visible: false, message: 'Offer'}, {visible: true, message: ''}, {visible: false, message: ''}]) {
    Object.assign(ad, next); await app.tick();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.strip.hidden, true);
    assert.equal(app.strip.children[1].children[0].textContent, '');
  }
});
