const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const html = fs.readFileSync('static/purchase_orders.html', 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
test('all page scripts parse', () => { scripts.forEach(s => new vm.Script(s)); });
function helper(name, next) { return html.slice(html.indexOf('    function ' + name), html.indexOf('    ' + next, html.indexOf('    function ' + name))); }
test('sent report includes confirmed sends only and escapes supplier data', () => {
  const output = {};
  const context = { isProcessor: false, document: { getElementById: () => output }, escapeHtml: s => String(s).replaceAll('<', '&lt;').replaceAll('>', '&gt;') };
  vm.createContext(context);
  vm.runInContext(helper('renderSentPoReport', 'function purchaseOrderPdfFromCanvas'), context);
  context.renderSentPoReport([{id:1,request_no:'UNSENT'}, {id:2,request_no:'SENT',supplier_name:'<supplier>',email_sent_at:'2026-09-08T10:00:00',email_sent_to:'vendor@example.com'}]);
  assert.match(output.innerHTML, /SENT/); assert.doesNotMatch(output.innerHTML,/UNSENT/);
  assert.match(output.innerHTML,/&lt;supplier&gt;/); assert.match(output.innerHTML,/Success/);
  context.renderSentPoReport([]); assert.match(output.innerHTML,/No successfully sent/);
});
test('PDF uses multiple A4 pages for long orders without shrinking content', () => {
  let pages = 1; const images = [];
  const pdf = { internal: { pageSize: { getWidth: () => 210, getHeight: () => 297 } }, addPage: () => pages++, addImage: (...args) => images.push(args) };
  const context = { window: { jspdf: { jsPDF: function() { return pdf; } } }, document: { createElement: () => ({ getContext: () => ({drawImage() {}}), toDataURL: () => 'image' }) } };
  vm.createContext(context); vm.runInContext(helper('purchaseOrderPdfFromCanvas', 'async function emailPurchaseOrderPdf'), context);
  assert.equal(context.purchaseOrderPdfFromCanvas({width:1700,height:6000}),pdf);
  assert.equal(pages,3); assert.equal(images.length,3);
  for (const image of images) { assert.equal(image[4],190); assert.ok(image[5]<=277); }
});
test('search and ready/sent filters preserve user scope', () => {
  const controls = Object.fromEntries(['statusFilter','poDateField','poDateFrom','poDateTo','poSearch'].map(id => [id,{value:''}]));
  const context = {document:{getElementById:id=>controls[id]},isProcessor:false,username:'manager',orders:[
    {id:1,submitted_by_username:'manager',status:'Approved',brand_name:'Realme',request_no:'REQ-1',items:[{product_name:'Phone'}]},
    {id:2,submitted_by_username:'manager',status:'Ordered',email_sent_at:'2026-09-08',request_no:'REQ-2',supplier_name:'Acme',items:[]},
    {id:3,submitted_by_username:'other',status:'Approved',request_no:'REQ-3',items:[]}
  ]};
  vm.createContext(context); vm.runInContext(helper('getScopedFilteredOrders','function clearPoDateFilter'),context);
  controls.statusFilter.value='ready'; assert.deepEqual(Array.from(context.getScopedFilteredOrders(),o=>o.id),[1]);
  controls.statusFilter.value='sent'; assert.deepEqual(Array.from(context.getScopedFilteredOrders(),o=>o.id),[2]);
  controls.statusFilter.value=''; controls.poSearch.value=' PHONE '; assert.deepEqual(Array.from(context.getScopedFilteredOrders(),o=>o.id),[1]);
  controls.poSearch.value='acme'; assert.deepEqual(Array.from(context.getScopedFilteredOrders(),o=>o.id),[2]);
  controls.poSearch.value='REQ-3'; assert.equal(context.getScopedFilteredOrders().length,0);
});
test('section toggle updates visibility and accessible state', () => {
  const body={style:{display:'block'}}; const attrs={}; let opened;
  const header={classList:{toggle:(_,value)=>opened=value},setAttribute:(key,value)=>attrs[key]=value};
  const context={document:{getElementById:()=>body}}; vm.createContext(context);
  vm.runInContext(helper('toggleSectionBody','const token'),context);
  context.toggleSectionBody('queue',header); assert.equal(body.style.display,'none'); assert.equal(attrs['aria-expanded'],'false'); assert.equal(opened,false);
  context.toggleSectionBody('queue',header); assert.equal(body.style.display,'block'); assert.equal(attrs['aria-expanded'],'true');
});
test('Busy number validation rejects duplicates but permits same-order edits and blanks', () => {
  const context={orders:[{id:1,busy_po_number:'181',request_no:'REQ-1'},{id:2,busy_po_number:null}]};
  vm.createContext(context); vm.runInContext(helper('busyNumberConflict','async function savePurchaseOrder'),context);
  assert.equal(context.busyNumberConflict('2',' 181 ').request_no,'REQ-1');
  assert.equal(context.busyNumberConflict('1','181'),undefined);
  assert.equal(context.busyNumberConflict('2','182'),undefined);
  assert.equal(context.busyNumberConflict('2','  '),null);
});
test('sent orders offer edit and resend only for processors', () => {
  const context={isProcessor:true}; vm.createContext(context);
  vm.runInContext(helper('orderProcessingActions','function renderOrders'),context);
  const sent={id:7,email_sent_at:'2026-09-08'};
  assert.match(context.orderProcessingActions(sent),/Success/);
  assert.match(context.orderProcessingActions(sent),/Edit &amp; resend/);
  assert.match(context.orderProcessingActions(sent),/openProcess\(7\)/);
  assert.match(context.orderProcessingActions({id:8}),/Prepare order/);
  context.isProcessor=false; assert.equal(context.orderProcessingActions(sent),'');
});
