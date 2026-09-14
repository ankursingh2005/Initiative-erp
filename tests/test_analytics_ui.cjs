// Decision view behavior without a browser or production connection.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/analytics.html', 'utf8');
const source = html.slice(html.indexOf('    function renderMarginScenario'), html.indexOf('    function renderQuality'));
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, {value: '', innerHTML: '', textContent: ''});
  return elements.get(id);
};
const button = {dataset: {matrixRow: '0'}, addEventListener: (_, callback) => button.click = callback};
const decisions = {sales: 1000, profit: 200, margin: 20, markup: 25, bill_count: 1,
  positive_bill_count: 1, average_bill: 1000, returns: 0, missing_bill_rows: 0,
  matrix: [{store: '<ALM>', category: 'HA', category_name: 'Home Appliances', sales: 1000, profit: 200, margin: 20, bills: 1}],
  loss_lines: [], loss_line_count: 0, selling_loss: 0};
let refreshes = 0;
const context = {document: {getElementById: get, querySelectorAll: () => [button]},
  lastDashboardData: {decisions}, inr: x => 'INR '+x, pct: x => x+'%',
  esc: x => String(x).replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
  refreshDashboard: () => refreshes++};
vm.createContext(context);
vm.runInContext(source, context);
get('marginLift').value = '1';
context.renderDecisions({decisions});
assert.match(get('marginScenario').textContent, /Additional gross profit: INR 10/);
assert.match(get('decisionMatrix').innerHTML, /&lt;ALM&gt;/);
assert.match(get('decisionLosses').innerHTML, /No below-cost/);
button.click();
assert.equal(get('storeFilter').value, '<ALM>');
assert.equal(get('divisionFilter').value, 'HA');
assert.equal(refreshes, 1);
get('marginLift').value = '';
context.renderMarginScenario();
assert.match(get('marginScenario').textContent, /Enter a margin increase/);
get('marginLift').value = '21';
context.renderMarginScenario();
assert.match(get('marginScenario').textContent, /Enter a margin increase/);
get('marginLift').value = '2';
decisions.sales = 0;
context.renderMarginScenario();
assert.match(get('marginScenario').textContent, /needs positive net sales/);
for (const [, script] of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(script);
console.log('Decision rendering, escaping, drilldown, scenario boundaries and inline syntax passed.');
