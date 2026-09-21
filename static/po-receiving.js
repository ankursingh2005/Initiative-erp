// Loaded after the PO page: uses its authenticated API helper and order list.
let receivingOptions = {can_receive: false, can_verify: false, locations: []};
let receivingOrderId = null;

function receivingActions(order) {
  if (!order.email_sent_at) return '';
  const summary = order.receiving || {};
  const progress = summary.verified_at ? 100 : 50;
  return `<div class="po-loop-ring" style="--po-progress:${progress}%" role="img" aria-label="PO loop ${progress}% complete"><span>${progress}%</span></div><div class="po-meta"><strong>${escapeHtml(summary.stage || 'Sent — awaiting receipt')}</strong>
    </div>
    <button type="button" class="btn-outline" onclick="openReceiving(${order.id})">Receive</button>`;
}

async function openReceiving(id) {
  receivingOrderId = id;
  const dialog = document.getElementById('receivingDialog');
  try {
    const order = await api(`/api/purchase-orders/${id}`);
    const s = order.receiving;
    document.getElementById('receivingTitle').textContent = `${order.request_no} — ${s.stage}`;
    document.getElementById('receivingMatch').innerHTML = `<table style="width:100%"><thead><tr><th>PO item / model</th><th>Sent</th><th>Received</th><th>Difference</th></tr></thead><tbody>${s.matching.map(l => `<tr><td>${escapeHtml(l.product_name)} ${escapeHtml(l.model_no || '')} ${escapeHtml(l.variant || '')}</td><td>${l.ordered} ${escapeHtml(l.unit)}</td><td>${l.received}</td><td>${l.difference === 0 ? 'Matched' : l.difference < 0 ? `${-l.difference} short` : `${l.difference} excess`}</td></tr>`).join('')}</tbody></table>`;
    const editable = !s.verified_at && !['Rejected', 'Cancelled'].includes(order.status);
    const verificationStore = receivingOptions.verification_store_id;
    const mayVerifyOrder = receivingOptions.can_verify && (verificationStore == null || s.receipts.filter(r => !r.voided_at).every(r => r.store_id === verificationStore));
    document.getElementById('receiptEntry').hidden = !(editable && receivingOptions.can_receive);
    document.getElementById('receiptLocation').innerHTML = receivingOptions.locations.map(l => `<option value="${l.id === null ? 'warehouse' : l.id}">${escapeHtml(l.name)}</option>`).join('');
    document.getElementById('receiptDocument').value = '';
    document.getElementById('receiptNotes').value = '';
    const today = new Date();
    document.getElementById('receiptDate').value = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    document.getElementById('receiptQuantities').innerHTML = s.matching.map(l => `<label style="display:block;margin:10px 0">${escapeHtml(l.product_name)} ${escapeHtml(l.model_no || '')} (${escapeHtml(l.unit)})<input type="number" min="0" step="1" value="0" data-receipt-item="${l.item_id}" required /></label>`).join('');
    document.getElementById('receiptHistory').innerHTML = s.receipts.length ? s.receipts.map(r => `<div class="po-row"><strong>${escapeHtml(r.document_number)} · ${escapeHtml(r.location_name)}</strong><div>${escapeHtml(r.received_date)} · Entered by ${escapeHtml(r.received_by)}${r.voided_at ? ' · Voided (excluded from totals)' : ''}</div><div>${r.lines.map(l => `${escapeHtml(order.items.find(i => i.id === l.item_id)?.product_name || '')}: ${l.quantity}`).join('; ')}</div><div>${escapeHtml(r.notes || '')}</div>${editable && !r.voided_at && (receivingOptions.can_verify || r.received_by_user_id === receivingOptions.user_id) ? `<button type="button" class="btn-outline" onclick="voidReceipt(${r.id})">Void incorrect receipt</button>` : ''}</div>`).join('') : '<p>No receipts entered yet.</p>';
    document.getElementById('verifyReceipt').hidden = !(editable && mayVerifyOrder);
    document.getElementById('verifyReceipt').disabled = !s.matched;
    document.getElementById('receivingMessage').textContent = s.verified_at ? `Verified by ${s.verified_by} on ${new Date(s.verified_at + 'Z').toLocaleString()}. PO loop complete.` : s.matched ? 'All quantities match. Review the delivery documents, then verify to complete the loop.' : 'Record actual quantities received. Short or excess quantities keep the loop open. Void incorrect entries and enter a corrected receipt.';
    if (!dialog.open) dialog.showModal();
  } catch (e) { alert(e.message); }
}

async function saveReceipt(event) {
  event.preventDefault();
  const button = document.getElementById('saveReceipt');
  button.disabled = true;
  try {
    const location = document.getElementById('receiptLocation').value;
    await api(`/api/purchase-orders/${receivingOrderId}/receipts`, {method:'POST', body:JSON.stringify({
      store_id: location === 'warehouse' ? null : Number(location),
      document_number: document.getElementById('receiptDocument').value.trim(),
      received_date: document.getElementById('receiptDate').value,
      notes: document.getElementById('receiptNotes').value,
      lines: [...document.querySelectorAll('[data-receipt-item]')].map(input => ({item_id:Number(input.dataset.receiptItem), quantity:Number(input.value)}))
    })});
    await loadOrders(); await openReceiving(receivingOrderId);
  } catch (e) { document.getElementById('receivingMessage').textContent = e.message; }
  finally { button.disabled = false; }
}

async function voidReceipt(id) {
  if (!confirm('Void this receipt? It will remain in the history but its quantities will be excluded.')) return;
  try {
    await api(`/api/purchase-orders/${receivingOrderId}/receipts/${id}/void`, {method:'POST'});
    await loadOrders(); await openReceiving(receivingOrderId);
  } catch (e) { document.getElementById('receivingMessage').textContent = e.message; }
}

async function verifyReceipt() {
  if (!confirm('Confirm that received goods and delivery documents match the sent PO. Verification will complete and lock this PO.')) return;
  const button = document.getElementById('verifyReceipt'); button.disabled = true;
  try {
    await api(`/api/purchase-orders/${receivingOrderId}/verify`, {method:'POST'});
    await loadOrders(); await openReceiving(receivingOrderId);
  } catch (e) { document.getElementById('receivingMessage').textContent = e.message; button.disabled = false; }
}

function loadReceivingOptions() {
  return api('/api/po-receiving-options').then(options => { receivingOptions = options; renderOrders(); }).catch(e => console.warn(e));
}
