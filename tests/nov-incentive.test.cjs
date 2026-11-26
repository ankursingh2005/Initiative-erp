const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/nov-incentive.js', 'utf8');

function setup(now, token = 'signed-in') {
  let ready, tick, timer;
  const nodes = [];
  function element() {
    const node = { children: [], open: false, setAttribute() {},
      appendChild(child) { this.children.push(child); },
      prepend(child) { this.children.unshift(child); },
      querySelector() { return { addEventListener() {} }; },
      cloneNode() { return Object.assign(element(), { src: this.src, alt: this.alt }); },
      showModal() { this.open = true; }, close() { this.open = false; },
      remove() { this.removed = true; } };
    nodes.push(node);
    return node;
  }
  const content = element();
  const context = { window: {}, location: { pathname: '/erp/home' },
    Date: class extends Date { static now() { return now.value; } },
    localStorage: { getItem: () => token }, sessionStorage: { getItem: () => '1' },
    document: { head: element(), body: element(), createElement: element,
      querySelector: () => content,
      addEventListener(name, fn) { if (name === 'DOMContentLoaded') ready = fn; } },
    setTimeout(fn, delay) { timer = { fn, delay }; }, clearTimeout() { timer = null; },
    setInterval(fn) { tick = fn; } };
  vm.runInNewContext(source, context);
  ready();
  return { context, content, nodes, tick: () => tick(), timer: () => timer };
}

test('offer uses inclusive India dates and an exclusive December cutoff', () => {
  const { context } = setup({ value: 0 });
  for (const [date, expected] of [
    ['2026-11-24T23:59:59+05:30', false],
    ['2026-11-25T00:00:00+05:30', true],
    ['2026-11-30T23:59:59.999+05:30', true],
    ['2026-12-01T00:00:00+05:30', false],
  ]) assert.equal(context.window.novIncentiveActive(Date.parse(date)), expected, date);
});
test('authenticated home displays poster and popup, and removes both at expiry', () => {
  const now = { value: Date.parse('2026-11-25T00:00:00+05:30') };
  const app = setup(now);
  assert.equal(app.content.children.length, 1);
  assert.equal(app.content.children[0].children[0].src, '/erp/static/nov-incentive-2026.png');
  assert.equal(app.timer().delay, 2000);
  app.timer().fn();
  const dialog = app.nodes.find(node => node.className === 'nov-offer-dialog');
  assert.equal(dialog.open, true);
  now.value = Date.parse('2026-12-01T00:00:00+05:30');
  app.tick();
  assert.equal(dialog.open, false);
  assert.equal(dialog.removed, true);
  assert.equal(app.content.children[0].removed, true);
});
test('no offer is rendered outside dates or without a login', () => {
  assert.equal(setup({ value: 0 }).content.children.length, 0);
  assert.equal(setup({ value: Date.parse('2026-11-26') }, null).content.children.length, 0);
});
