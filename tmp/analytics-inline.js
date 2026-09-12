


    function appUrl(path) {
      const currentPath = window.location.pathname;
      const appBasePath = currentPath === '/erp' || currentPath.startsWith('/erp/') ? '/erp' : '';
      if (!path) return appBasePath || '/';
      if (/^https?:\/\//i.test(path)) return path;
      return path.startsWith('/') ? `${appBasePath}${path}` : `${appBasePath}/${path}`;
    }

    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register(appUrl('/sw.js')).catch(() => {});
      });
    }

    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    if (!token) window.location.href = appUrl('/login');

    function logout() { localStorage.clear(); window.location.href = appUrl('/login'); }
    function openLogoutModal() { document.getElementById('logoutModal').classList.add('show'); }
    function closeLogoutModal() { document.getElementById('logoutModal').classList.remove('show'); }
    function confirmLogout() { logout(); }
    function openClearModal() { document.getElementById('clearModal').classList.add('show'); }
    function closeClearModal() { document.getElementById('clearModal').classList.remove('show'); }

    async function authFetch(url, options = {}) {
      const response = await fetch(appUrl(url), {
        ...options,
        cache: 'no-store',
        headers: { ...(options.headers || {}), Authorization: 'Bearer ' + token }
      });
      if (response.status === 401) { logout(); return null; }
      return response;
    }

    function inr(value) {
      const n = Number(value) || 0;
      return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    }
    function pct(value) { return (Number(value) || 0).toFixed(1) + '%'; }
    function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
    function fmtDate(d) { const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; }

    let charts = {};
    function destroyCharts() { Object.values(charts).forEach(c => c && c.destroy()); charts = {}; }

    const CHART_COLORS = ['#7c3aed', '#155eef', '#d95f00', '#2e7d32', '#c0392b', '#0e7490', '#b8860b', '#9333ea', '#0f766e', '#be185d', '#4338ca', '#65a30d', '#ea580c'];

    async function loadMeta() {
      const res = await authFetch('/api/analytics/meta');
      if (!res) return null;
      return await res.json();
    }

    async function loadDashboard(params = {}) {
      const query = new URLSearchParams();
      if (params.division && params.division !== 'ALL') query.set('division', params.division);
      if (params.store && params.store !== 'ALL') query.set('store', params.store);
      if (params.start_date) query.set('start_date', params.start_date);
      if (params.end_date) query.set('end_date', params.end_date);
      if (params.search) query.set('search', params.search);
      query.set('gst', params.gst || 'false');
      const qs = query.toString();
      const res = await authFetch('/api/analytics/dashboard' + (qs ? '?' + qs : ''));
      if (!res) return null;
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load dashboard');
      return data;
    }

    function renderUploadControls(meta) {
      const container = document.getElementById('uploadControls');
      if (meta.can_upload) {
        container.innerHTML = `
          <label class="dropzone" id="dropzone">
            📎 <span id="dropzoneLabel">Choose or drop an Excel/CSV file</span>
            <input type="file" id="fileInput" accept=".xlsx,.xls,.csv" />
          </label>
          <label><input type="checkbox" id="sourceIncludesGst" /> File amounts already include 18% GST</label><button class="btn btn-primary" id="analyzeBtn" disabled onclick="doUpload()">Analyze</button>
          ${meta.has_data ? '<button class="btn btn-danger" onclick="openClearModal()">Clear Data</button>' : ''}
        `;
        const fileInput = document.getElementById('fileInput');
        const dropzone = document.getElementById('dropzone');
        fileInput.addEventListener('change', () => {
          if (fileInput.files.length) {
            document.getElementById('dropzoneLabel').textContent = fileInput.files[0].name;
            document.getElementById('analyzeBtn').disabled = false;
          }
        });
        ['dragover', 'dragenter'].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add('dragover'); }));
        ['dragleave', 'drop'].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove('dragover'); }));
        dropzone.addEventListener('drop', e => {
          if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            document.getElementById('dropzoneLabel').textContent = e.dataTransfer.files[0].name;
            document.getElementById('analyzeBtn').disabled = false;
          }
        });
      } else {
        container.innerHTML = '';
      }
    }

    function renderStatusText(meta) {
      const el = document.getElementById('statusText');
      if (!meta.has_data) {
        el.innerHTML = meta.can_upload
          ? 'No file uploaded yet. Upload one to build the dashboard.'
          : 'No data yet. Ask your Admin to upload a sales export.';
        return;
      }
      const u = meta.last_upload;
      const uploadedAt = new Date(u.uploaded_at).toLocaleString('en-IN');
      el.innerHTML = `Showing <strong>${esc(u.file_name)}</strong> - ${u.row_count.toLocaleString('en-IN')} rows across ${u.sheet_count} sheet(s), uploaded by <strong>${esc(u.uploaded_by || 'Admin')}</strong> on ${uploadedAt}. Covers ${u.date_from || '?'} to ${u.date_to || '?'}.`;
    }

    // ---------------- Review & Clean (staging) workflow ----------------
    // Upload -> /api/analytics/stage parses + auto-classifies the file but
    // does NOT touch the live dashboard. The Admin reviews/fixes divisions
    // here, can download the cleaned file, and only /commit writes it to
    // the dashboard tables (or /discard + a fresh upload throws it away).
    let reviewState = { token: null, rows: [] };

    const DIVISION_LABELS = { HA: 'HA', HE: 'HE', MH: 'Mobile', IT: 'Computer', ACC: 'Accessories', PAYOUT: 'Payouts', UNCATEGORIZED: 'Needs review', EXCLUDED: 'Excluded / unrelated' };

    async function doUpload() {
      const fileInput = document.getElementById('fileInput');
      const file = fileInput.files[0];
      const msg = document.getElementById('uploadMsg');
      const progress = document.getElementById('progressBar');
      if (!file) return;

      msg.textContent = '';
      msg.className = 'upload-msg';
      progress.style.display = 'block';
      document.getElementById('analyzeBtn').disabled = true;
      document.getElementById('reviewCard').classList.add('hidden');

      const formData = new FormData();
      formData.append('file', file);
      formData.append('amount_basis', document.getElementById('sourceIncludesGst').checked ? 'inclusive' : 'exclusive');

      try {
        const res = await authFetch('/api/analytics/stage', { method: 'POST', body: formData });
        const data = await res.json().catch(() => ({}));
        progress.style.display = 'none';
        document.getElementById('analyzeBtn').disabled = false;
        if (!res.ok) {
          msg.classList.add('error');
          msg.textContent = data.detail || 'Upload failed';
          return;
        }
        msg.classList.add('success');
        msg.textContent = `Parsed ${data.rows.length.toLocaleString('en-IN')} row(s) from "${data.file_name}". Review below, then proceed.`;
        reviewState = { token: data.staging_token, rows: data.rows };
        renderReviewPanel(data.summary);
      } catch (e) {
        progress.style.display = 'none';
        msg.classList.add('error');
        msg.textContent = 'Upload failed - check your connection and try again.';
        document.getElementById('analyzeBtn').disabled = false;
      }
    }

    function renderReviewSummary(summary) {
      const grid = document.getElementById('reviewSummaryGrid');
      const cards = [
        `<div class="review-stat"><div class="label">Total Rows</div><div class="value">${summary.total_rows.toLocaleString('en-IN')}</div></div>`,
        `<div class="review-stat ${summary.uncategorized_count ? 'warn' : 'good'}"><div class="label">Uncategorized</div><div class="value">${summary.uncategorized_count}</div></div>`,
        `<div class="review-stat good"><div class="label">AC ID+OD Merged</div><div class="value">${summary.merged_ac_rows}</div></div>`,
        `<div class="review-stat ${summary.flagged_ac_rows ? 'danger' : 'good'}"><div class="label">AC Rows To Check</div><div class="value">${summary.flagged_ac_rows}</div></div>`,
        `<div class="review-stat"><div class="label">Brands Detected</div><div class="value">${summary.brands_detected}</div></div>`,
      ];
      summary.division_summary.forEach(d => {
        cards.push(`<div class="review-stat"><div class="label">${esc(d.division_name)}</div><div class="value">${d.count}</div></div>`);
      });
      grid.innerHTML = cards.join('');
    }

    function renderReviewTable(rows) {
      const body = document.getElementById('reviewTableBody');
      body.innerHTML = rows.map(source => {
        const r = withGst() ? {...source, ...source.with_gst} : source;
        const rowClass = r.merged ? 'row-merged' : (r.division === 'UNCATEGORIZED' ? 'row-uncategorized' : (r.note ? 'row-flagged' : ''));
        const options = Object.keys(DIVISION_LABELS).map(code =>
          `<option value="${code}" ${r.division === code ? 'selected' : ''}>${DIVISION_LABELS[code]}</option>`
        ).join('');
        return `
          <tr class="${rowClass}" data-row-id="${r.row_id}">
            <td><input type="checkbox" class="review-row-check" data-row-id="${r.row_id}" onchange="updateReviewSelectedCount()" /></td>
            <td>${esc(r.sale_date || '')}</td>
            <td class="item-cell">${esc(r.item)}</td>
            <td><select class="row-division" onchange="reassignSingleRow(${r.row_id}, this.value)">${options}</select></td>
            <td>${esc(r.brand || '')}</td>
            <td class="num">${inr(r.sales_amt)}</td>
            <td class="num">${inr(r.cost_amt)}</td>
            <td class="num">${inr(r.profit_loss)}</td>
            <td>${r.note ? `<span class="note-text">${esc(r.note)}</span>` : ''}</td>
          </tr>`;
      }).join('');
      updateReviewSelectedCount();
    }

    function renderReviewPanel(summary) {
      document.getElementById('reviewCard').classList.remove('hidden');
      renderReviewSummary(summary);
      renderReviewTable(reviewState.rows);
      document.getElementById('reviewCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function updateReviewSelectedCount() {
      const checked = document.querySelectorAll('.review-row-check:checked').length;
      document.getElementById('reviewSelectedCount').textContent = `${checked} selected`;
      const applyBtn = document.getElementById('applyBulkBtn');
      if (applyBtn) applyBtn.disabled = checked === 0;
    }

    function toggleSelectAllReview() {
      const boxes = document.querySelectorAll('.review-row-check');
      const allChecked = Array.from(boxes).every(b => b.checked);
      boxes.forEach(b => b.checked = !allChecked);
      document.getElementById('selectAllBtn').textContent = allChecked ? '☑ Select all' : '☐ Deselect all';
      updateReviewSelectedCount();
    }

    function showReviewToast(message, isError) {
      let toast = document.getElementById('reviewToast');
      if (!toast) {
        toast = document.createElement('div');
        toast.id = 'reviewToast';
        toast.className = 'review-toast';
        document.getElementById('reviewCard').insertBefore(toast, document.getElementById('reviewSummaryGrid'));
      }
      toast.textContent = message;
      toast.className = 'review-toast show' + (isError ? ' error' : ' success');
      clearTimeout(toast._hideTimer);
      toast._hideTimer = setTimeout(() => toast.classList.remove('show'), 3500);
    }

    async function reassignRows(rowIds, division) {
      if (!reviewState.token || !rowIds.length) return;
      try {
        const res = await authFetch(`/api/analytics/stage/${reviewState.token}/reassign`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ row_ids: rowIds, division })
        });
        if (!res) {
          showReviewToast('Your session expired - please log in again.', true);
          return;
        }
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          showReviewToast(errBody.detail || `Could not reassign rows (error ${res.status}). Please try again.`, true);
          return;
        }
        const data = await res.json();
        reviewState.rows = data.rows;
        renderReviewSummary(data.summary);
        renderReviewTable(reviewState.rows);
        document.getElementById('selectAllBtn').textContent = '☑ Select all';
        showReviewToast(data.message || `Reassigned ${rowIds.length} row(s).`, false);
      } catch (e) {
        showReviewToast('Something went wrong reassigning those rows - check your connection and try again.', true);
      }
    }

    function reassignSingleRow(rowId, division) {
      reassignRows([rowId], division);
    }

    function applyBulkReassign() {
      const rowIds = Array.from(document.querySelectorAll('.review-row-check:checked')).map(b => Number(b.dataset.rowId));
      const division = document.getElementById('bulkDivisionSelect').value;
      if (!rowIds.length) {
        showReviewToast('Select at least one row first (tick the checkboxes on the left, or use "Select all").', true);
        return;
      }
      reassignRows(rowIds, division);
    }

    async function downloadCleanedFile(clickEvent) {
      if (!reviewState.token) return;
      const btn = clickEvent && clickEvent.target ? clickEvent.target : null;
      const originalLabel = btn ? btn.textContent : null;
      if (btn) { btn.disabled = true; btn.textContent = 'Preparing download...'; }
      try {
        const res = await authFetch(`/api/analytics/stage/${reviewState.token}/download?gst=${withGst()}`);
        if (!res || !res.ok) {
          const msg = document.getElementById('uploadMsg');
          msg.className = 'upload-msg error';
          msg.textContent = 'Could not download the cleaned file - please try again.';
          return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = withGst() ? 'cleaned_analytics_With_GST.csv' : 'cleaned_analytics_Without_GST.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = originalLabel; }
      }
    }

    async function discardReview() {
      if (reviewState.token) {
        await authFetch(`/api/analytics/stage/${reviewState.token}`, { method: 'DELETE' });
      }
      reviewState = { token: null, rows: [] };
      document.getElementById('reviewCard').classList.add('hidden');
      document.getElementById('uploadMsg').textContent = '';
      document.getElementById('fileInput') && (document.getElementById('fileInput').value = '');
    }

    async function commitReview() {
      if (!reviewState.token) return;
      const msg = document.getElementById('uploadMsg');
      try {
        const res = await authFetch(`/api/analytics/stage/${reviewState.token}/commit`, { method: 'POST' });
        if (!res) {
          msg.className = 'upload-msg error';
          msg.textContent = 'Your session expired - please log in again.';
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          msg.className = 'upload-msg error';
          msg.textContent = data.detail || 'Could not save to the dashboard';
          return;
        }
        reviewState = { token: null, rows: [] };
        document.getElementById('reviewCard').classList.add('hidden');
        msg.className = 'upload-msg success';
        msg.textContent = `Loaded ${data.rows_loaded.toLocaleString('en-IN')} rows from ${data.sheets_read} sheet(s).`;
        await init();
      } catch (e) {
        msg.className = 'upload-msg error';
        msg.textContent = 'Something went wrong saving to the dashboard - check your connection and try again.';
      }
    }

    async function confirmClear() {
      closeClearModal();
      await authFetch('/api/analytics/clear', { method: 'DELETE' });
      await init();
    }

    function renderKpis(data) {
      const k = data.kpis;
      const grid = document.getElementById('kpiGrid');
      grid.innerHTML = `
        <div class="kpi"><div class="label">Total Sales</div><div class="value">${inr(k.total_sales)}</div></div>
        <div class="kpi"><div class="label">Profit (${gstLabel()})</div><div class="value ${k.total_profit >= 0 ? 'good' : 'bad'}">${inr(k.total_profit)}</div></div>
        <div class="kpi"><div class="label">Margin on sales</div><div class="value ${k.margin_percent >= 8 ? 'good' : 'bad'}">${pct(k.margin_percent)}</div></div>
        <div class="kpi"><div class="label">Transactions</div><div class="value">${k.transactions.toLocaleString('en-IN')}</div></div>
        <div class="kpi"><div class="label">Items / Divisions</div><div class="value">${k.unique_items.toLocaleString('en-IN')} / ${k.divisions}</div></div>
        <div class="kpi"><div class="label">Date Range</div><div class="value" style="font-size:14px">${k.date_from || '?'} → ${k.date_to || '?'}</div></div>
      `;
    }

    function renderYearlyChart(data) {
      const ctx = document.getElementById('yearlyChart');
      charts.yearly = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.yearly_trend.map(y => 'FY ' + y.period),
          datasets: [
            { label: 'Sales', data: data.yearly_trend.map(y => y.sales), backgroundColor: '#155eef' },
            { label: 'Profit', data: data.yearly_trend.map(y => y.profit), backgroundColor: '#7c3aed' },
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { ticks: { callback: v => inr(v) } } }
        }
      });
    }

    let lastDashboardData = null;
    let divisionChartType = 'bar';

    function renderDivisionChart(data, type) {
      type = type || divisionChartType;
      divisionChartType = type;
      const ctx = document.getElementById('divisionChart');
      const divs = data.division_breakdown.slice(0, 8);
      const colors = divs.map((d, i) => CHART_COLORS[i % CHART_COLORS.length]);
      const isSlice = (type === 'doughnut' || type === 'pie' || type === 'polarArea');

      const labels = divs.map(d => d.division + (d.profit < 0 ? ' (Loss)' : ''));
      const values = isSlice ? divs.map(d => Math.abs(d.profit)) : divs.map(d => d.profit);

      const tooltipLabel = (item) => {
        const d = divs[item.dataIndex];
        const magnitude = divs.reduce((sum, row) => sum + Math.abs(row.profit), 0);
        const share = isSlice ? `${magnitude ? (Math.abs(d.profit) / magnitude * 100).toFixed(1) : 0}% of absolute profit/loss` : `${d.profit_share_percent}% of net profit`;
        return `${inr(d.profit)}${share ? '  ·  ' + share : ''}`;
      };

      const options = {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: isSlice, position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: tooltipLabel } },
        },
      };
      if (!isSlice) {
        options.scales = { y: { ticks: { callback: v => inr(v) } }, x: { ticks: { autoSkip: false, font: { size: 11 } } } };
      }

      charts.division = new Chart(ctx, {
        type: type,
        data: { labels, datasets: [{ label: 'Profit', data: values, backgroundColor: colors, borderRadius: type === 'bar' ? 6 : 0 }] },
        options,
      });
    }

    function renderDivisionRadarChart(data) {
      const ctx = document.getElementById('divisionRadarChart');
      const divs = data.division_breakdown.slice(0, 8);
      charts.divisionRadar = new Chart(ctx, {
        type: 'radar',
        data: {
          labels: divs.map(d => d.division),
          datasets: [{
            label: 'Margin %',
            data: divs.map(d => d.margin_percent),
            backgroundColor: 'rgba(124,58,237,0.18)',
            borderColor: '#7c3aed',
            pointBackgroundColor: '#7c3aed',
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { r: { ticks: { callback: v => v + '%' }, beginAtZero: true } },
        },
      });
    }

    function renderDivisionSalesCostChart(data) {
      const ctx = document.getElementById('divisionSalesCostChart');
      const divs = data.division_breakdown.slice(0, 8);
      charts.divisionSalesCost = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: divs.map(d => d.division),
          datasets: [
            { label: 'Sales', data: divs.map(d => d.sales), backgroundColor: '#155eef', borderRadius: 5 },
            { label: 'Cost', data: divs.map(d => d.cost), backgroundColor: '#d95f00', borderRadius: 5 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { ticks: { callback: v => inr(v) } } },
        },
      });
    }

    document.getElementById('divisionChartToggle').addEventListener('click', function (e) {
      const btn = e.target.closest('button[data-type]');
      if (!btn || !lastDashboardData) return;
      this.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (charts.division) charts.division.destroy();
      renderDivisionChart(lastDashboardData, btn.dataset.type);
    });

    function renderMonthlyChart(data) {
      const ctx = document.getElementById('monthlyChart');
      charts.monthly = new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.monthly_trend.map(m => m.period),
          datasets: [
            { label: 'Sales', data: data.monthly_trend.map(m => m.sales), borderColor: '#155eef', backgroundColor: 'rgba(21,94,239,0.08)', fill: true, tension: 0.25 },
            { label: 'Profit', data: data.monthly_trend.map(m => m.profit), borderColor: '#7c3aed', backgroundColor: 'rgba(124,58,237,0.10)', fill: true, tension: 0.25 },
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { ticks: { callback: v => inr(v) } }, x: { ticks: { maxRotation: 60, minRotation: 45 } } }
        }
      });
    }

    function renderTopItemsChart(data) {
      const ctx = document.getElementById('topItemsChart');
      const items = data.top_profit_items;
      charts.topItems = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: items.map(i => i.item.length > 28 ? i.item.slice(0, 28) + '…' : i.item),
          datasets: [{ label: 'Profit', data: items.map(i => i.profit), backgroundColor: '#7c3aed' }]
        },
        options: {
          indexAxis: 'y', responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { ticks: { callback: v => inr(v) } } }
        }
      });
    }

    function renderDivisionTable(data) {
      const body = document.getElementById('divisionTableBody');
      body.innerHTML = data.division_breakdown.map(d => `
        <tr>
          <td>${esc(d.division)}</td>
          <td class="num">${inr(d.sales)}</td>
          <td class="num">${inr(d.profit)}</td>
          <td class="num">${pct(d.margin_percent)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No data</td></tr>';
    }

    function renderLossTable(data) {
      const body = document.getElementById('lossTableBody');
      body.innerHTML = data.loss_items.map(i => `
        <tr class="loss">
          <td>${esc(i.item)}</td>
          <td class="num">${inr(i.sales)}</td>
          <td class="num">${inr(i.profit)}</td>
        </tr>
      `).join('') || '<tr><td colspan="3">No loss-making items 🎉</td></tr>';
    }

    function renderMarginTable(data) {
      const body = document.getElementById('marginTableBody');
      const rows = [];
      data.top_margin_items.slice(0, 6).forEach(i => rows.push({ ...i, tag: 'pos' }));
      data.bottom_margin_items.slice(0, 6).forEach(i => rows.push({ ...i, tag: 'neg' }));
      body.innerHTML = rows.map(i => `
        <tr>
          <td>${esc(i.item)}</td>
          <td class="num">${pct(i.margin_percent)}</td>
          <td><span class="pill ${i.tag}">${i.tag === 'pos' ? 'Leader' : 'Laggard'}</span></td>
        </tr>
      `).join('') || '<tr><td colspan="3">Not enough data</td></tr>';
    }

    function renderRevenueTable(data) {
      const body = document.getElementById('revenueTableBody');
      body.innerHTML = data.top_revenue_items.map(i => `
        <tr>
          <td>${esc(i.item)}</td>
          <td class="num">${inr(i.sales)}</td>
          <td class="num">${inr(i.profit)}</td>
          <td class="num">${pct(i.margin_percent)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No data</td></tr>';
    }

    function renderProfitItemsTable(data) {
      const body = document.getElementById('profitItemsTableBody');
      body.innerHTML = data.top_profit_items.map(i => `
        <tr>
          <td>${esc(i.item)}</td>
          <td class="num">${inr(i.sales)}</td>
          <td class="num">${inr(i.profit)}</td>
          <td class="num">${pct(i.margin_percent)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No data</td></tr>';
    }

    function renderQtyTable(data) {
      const body = document.getElementById('qtyTableBody');
      const items = data.top_qty_items || [];
      body.innerHTML = items.map(i => `
        <tr>
          <td>${esc(i.item)}</td>
          <td class="num">${(i.qty ?? 0).toLocaleString('en-IN')}</td>
          <td class="num">${inr(i.sales)}</td>
          <td class="num">${inr(i.profit)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No Qty column found in the upload</td></tr>';
    }

    function renderBrandTable(data) {
      const body = document.getElementById('brandTableBody');
      const brands = data.brand_breakdown || [];
      body.innerHTML = brands.map(b => `
        <tr>
          <td>${esc(b.brand)}</td>
          <td class="num">${inr(b.sales)}</td>
          <td class="num">${inr(b.profit)}</td>
          <td class="num">${pct(b.margin_percent)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No data</td></tr>';
    }

    function renderYearlyTable(data) {
      const body = document.getElementById('yearlyTableBody');
      body.innerHTML = data.yearly_trend.map(y => `
        <tr>
          <td>${esc(y.period)}</td>
          <td class="num">${inr(y.sales)}</td>
          <td class="num">${inr(y.cost)}</td>
          <td class="num">${inr(y.profit)}</td>
          <td class="num">${pct(y.margin_percent)}</td>
        </tr>
      `).join('') || '<tr><td colspan="5">No data</td></tr>';
    }

    function renderMonthlyTable(data) {
      const body = document.getElementById('monthlyTableBody');
      body.innerHTML = data.monthly_trend.map(m => `
        <tr>
          <td>${esc(m.period)}</td>
          <td class="num">${inr(m.sales)}</td>
          <td class="num">${inr(m.cost)}</td>
          <td class="num">${inr(m.profit)}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No data</td></tr>';
    }

    const REC_ICONS = { opportunity: '💡', decline: '📉', growth: '📈', loss: '⚠️', seasonal: '📅' };
    const REC_PRIORITY_LABEL = { high: 'High Priority', medium: 'Medium Priority', low: 'Low Priority' };

    // Bolds the real ₹ amounts and percentages already present in the
    // (already-escaped) recommendation text, so the actual computed figures
    // stand out at a glance instead of being buried in a paragraph.
    function highlightStats(escapedText) {
      return escapedText
        .replace(/₹-?[\d,]+(\.\d+)?/g, (m) => `<strong>${m}</strong>`)
        .replace(/-?\d+(\.\d+)?%/g, (m) => `<strong>${m}</strong>`);
    }

    function renderRecommendations(data) {
      const grid = document.getElementById('recGrid');
      grid.innerHTML = data.recommendations.map(r => `
        <div class="rec-card priority-${r.priority}">
          <div class="rec-icon-badge">${REC_ICONS[r.type] || '•'}</div>
          <div class="rec-body">
            <div class="rec-title-row">
              <div class="rec-title">${esc(r.title)}</div>
              <span class="rec-priority-pill">${REC_PRIORITY_LABEL[r.priority] || r.priority}</span>
            </div>
            <div class="rec-detail">${highlightStats(esc(r.detail))}</div>
          </div>
        </div>
      `).join('') || '<p class="sub">No recommendations yet - upload a sales export to generate them.</p>';
    }

    function renderAll(data) {
      lastDashboardData = data;
      destroyCharts();
      renderKpis(data);
      renderYearlyChart(data);
      renderDivisionChart(data);
      renderDivisionRadarChart(data);
      renderDivisionSalesCostChart(data);
      renderMonthlyChart(data);
      renderTopItemsChart(data);
      renderDivisionTable(data);
      renderLossTable(data);
      renderMarginTable(data);
      renderRevenueTable(data);
      renderProfitItemsTable(data);
      renderQtyTable(data);
      renderBrandTable(data);
      renderYearlyTable(data);
      renderMonthlyTable(data);
      renderRecommendations(data);
      renderAdvanced(data);
    }

    function populateFilterOptions(meta) {
      const catSelect = document.getElementById('divisionFilter');
      const currentCat = catSelect.value;
      catSelect.innerHTML = '<option value="ALL">All Categories</option>' +
        (meta.categories || []).map(c => `<option value="${esc(c)}">${esc(DIVISION_LABELS[c] || c)}</option>`).join('');
      if ((meta.categories || []).includes(currentCat)) catSelect.value = currentCat;

      const storeSelect = document.getElementById('storeFilter');
      const currentStore = storeSelect.value;
      storeSelect.innerHTML = '<option value="ALL">All Stores</option>' +
        (meta.stores || []).map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
      if ((meta.stores || []).includes(currentStore)) storeSelect.value = currentStore;
    }

    function withGst(){ return document.getElementById('amountBasis').value === 'inclusive'; }
    function gstLabel(){ return withGst() ? 'With GST (18%)' : 'Without GST'; }
    function changeGstMode(){
      if(reviewState.rows && reviewState.rows.length) renderReviewTable(reviewState.rows);
      refreshDashboard();
    }
    function currentFilterParams() {
      return {
        gst: withGst() ? 'true' : 'false',
        division: document.getElementById('divisionFilter').value,
        store: document.getElementById('storeFilter').value,
        search: document.getElementById('searchFilter').value.trim(),
        start_date: document.getElementById('startDateFilter').value,
        end_date: document.getElementById('endDateFilter').value,
      };
    }

    function applyPreset() {
      const preset = document.getElementById('presetSelect').value;
      if (preset === 'custom') return;
      const today = new Date();
      let start = new Date(today), end = new Date(today);
      if (preset === 'week') {
        const day = today.getDay();
        start = new Date(today); start.setDate(today.getDate() - day);
      } else if (preset === 'month') {
        start = new Date(today.getFullYear(), today.getMonth(), 1);
      }
      document.getElementById('startDateFilter').value = fmtDate(start);
      document.getElementById('endDateFilter').value = fmtDate(end);
      refreshDashboard();
    }

    let dashboardRequest = 0;
    let searchDelay;
    function queueRefresh(){ clearTimeout(searchDelay); searchDelay=setTimeout(refreshDashboard,350); }
    async function refreshDashboard() {
      const request = ++dashboardRequest;
      itemsPage = 1;
      const params = currentFilterParams();
      try {
        const data = await loadDashboard(params);
        if (request !== dashboardRequest || !data) return;
        renderQuality(data);
        document.getElementById('emptyState').classList.toggle('hidden', !!data.has_data);
        document.getElementById('dashboardContent').classList.toggle('hidden', !data.has_data);
        if(data.has_data) renderAll(data);
        else { destroyCharts(); document.getElementById('emptyStateText').textContent='No included sales match these filters. Reset filters or inspect Needs category review / All uploaded rows below.'; }
        if(itemsViewOpen) await loadItemsView();
      } catch(error){
        if(request !== dashboardRequest) return;
        document.getElementById('dashboardContent').classList.add('hidden');
        document.getElementById('emptyState').classList.remove('hidden');
        document.getElementById('emptyStateText').textContent=error.message;
      }
    }

    function resetFilters() {
      document.getElementById('presetSelect').value = 'custom';
      document.getElementById('divisionFilter').value = 'ALL';
      document.getElementById('storeFilter').value = 'ALL';
      document.getElementById('searchFilter').value = '';
      document.getElementById('dataView').value = 'included';
      document.getElementById('startDateFilter').value = '';
      document.getElementById('endDateFilter').value = '';
      refreshDashboard();
    }

    let itemsViewOpen = false;
    let itemsPage = 1;
    let itemRequest = 0;

    function itemsTableHtml(items) {
      if (!items.length) {
        return `<div class="empty-state"><div class="icon">&#128203;</div>No items match the selected filters.</div>`;
      }
      const rows = items.map(it => `
        <tr>
          <td>${esc(it.sale_date || '')}</td>
          <td>${esc(it.item || '')}</td>
          <td>${esc(DIVISION_LABELS[it.division] || it.division || '')}</td>
          <td>${esc(it.store || '')}</td>
          <td>${esc(it.brand || '')}</td>
          <td class="num">${esc(it.qty ?? '')}</td>
          <td class="num">${inr(it.sales_amt)}</td>
          <td class="num">${inr(it.cost_amt)}</td>
          <td class="num">${inr(it.profit_loss)}</td><td>${esc(it.status)}</td><td>${esc(it.exclusion_reason)}</td>
        </tr>`).join('');
      return `
        <h2>Line items</h2>
        <p class="sub">${gstLabel()}. Use Previous / Next to inspect every matching row.</p>
        <div class="table-scroll">
          <table>
            <thead>
              <tr><th>Date</th><th class="item-cell">Item</th><th>Category</th><th>Store</th><th>Brand</th>
                  <th class="num">Qty</th><th class="num">Sales</th><th class="num">Cost</th><th class="num">Profit</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }

    function itemQuery(){
      const params = currentFilterParams(), query = new URLSearchParams();
      for(const [key,value] of Object.entries(params)) if(value && value !== 'ALL') query.set(key,value);
      query.set('view',document.getElementById('dataView').value);
      return query;
    }
    async function loadItemsView() {
      const card = document.getElementById('itemsViewCard'), request=++itemRequest;
      card.textContent='Loading items...';
      const query=itemQuery(); query.set('page',itemsPage); query.set('page_size',100);
      try {
        const res=await authFetch('/api/analytics/items?'+query);
        if(!res || request!==itemRequest)return;
        const data=await res.json();
        if(!res.ok)throw new Error(data.detail || 'Could not load items');
        card.innerHTML=itemsTableHtml(data.items || []) + '<div class="item-pagination"><button class="btn btn-ghost" onclick="itemsPage--;loadItemsView()" '+(itemsPage<=1?'disabled':'')+'>Previous</button> <span>Page '+itemsPage+' / '+Math.max(1,Math.ceil(data.total/100))+' &middot; '+data.total+' rows</span> <button class="btn btn-ghost" onclick="itemsPage++;loadItemsView()" '+(itemsPage*100>=data.total?'disabled':'')+'>Next</button></div>';
      }catch(error){if(request===itemRequest)card.textContent=error.message;}
    }
    async function downloadAnalytics(){
      try{
        const res=await authFetch('/api/analytics/export?'+itemQuery());
        if(!res)return;
        if(!res.ok){const data=await res.json();throw new Error(data.detail || 'Download failed');}
        const url=URL.createObjectURL(await res.blob()), a=document.createElement('a');
        a.href=url;a.download=withGst()?'AI_Analysis_With_GST.csv':'AI_Analysis_Without_GST.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      }catch(error){alert(error.message);}
    }
    function renderQuality(data){
      const q=data.quality||{}, g=data.gst||{};
      document.getElementById('qualitySummary').innerHTML='<div class="quality-badges"><span>Included: '+(q.included||0)+'</span><span>Needs review: '+(q.review||0)+'</span><span>Excluded: '+(q.excluded||0)+'</span></div><p>Sales before GST: <b>'+inr(g.sales_before_gst)+'</b> + GST '+(g.rate||0)+'%: <b>'+inr(g.sales_gst)+'</b>. Cost before GST: <b>'+inr(g.cost_before_gst)+'</b> + GST '+(g.rate||0)+'%: <b>'+inr(g.cost_gst)+'</b>.</p><p class="sub">'+(g.enabled ? 'With GST: 18% is applied to sales and cost, including Payouts.' : 'Without GST: no GST is added to sales or cost.')+' Profit = displayed sales minus displayed cost. These are product margins, before operating expenses. Unknown historical stores appear as Unknown.</p>';
    }
    function renderAdvanced(data){
      renderQuality(data);
      const a=data.advanced||{},d=a.distribution||{},daily=a.daily_trend||[],stores=a.store_breakdown||[];
      document.getElementById('statsGrid').innerHTML=[['Total cost ('+gstLabel()+')',inr(data.kpis.total_cost)],['Median line sale',inr(d.median_sale)],['Sales standard deviation',inr(d.sale_stddev)],['Loss-making rows',d.loss_rows||0],['Unusual sale amounts',d.outliers_evaluable?d.outlier_rows:'Not enough variation']].map(([label,value])=>'<div class="kpi"><div class="label">'+label+'</div><div class="value">'+value+'</div></div>').join('');
      document.getElementById('scatterNote').textContent='First '+Math.min(a.scatter_total||0,1000)+' of '+(a.scatter_total||0)+' included rows in date order. Export includes all rows. Unusual amounts use median absolute deviation; they are not removed.';
      charts.dailyAdvanced=new Chart(document.getElementById('dailyAdvancedChart'),{type:'line',data:{labels:daily.map(x=>x.date),datasets:[{label:'Sales ('+gstLabel()+')',data:daily.map(x=>x.sales),borderColor:'#155eef',pointRadius:1},{label:'7-day average',data:daily.map(x=>x.rolling_7_sales),borderColor:'#0f9d84',pointRadius:0}]},options:{responsive:true,maintainAspectRatio:false}});
      charts.scatterAdvanced=new Chart(document.getElementById('scatterAdvancedChart'),{type:'scatter',data:{datasets:[{label:'Sales / profit',data:a.scatter||[],backgroundColor:'#7258d9aa'}]},options:{responsive:true,maintainAspectRatio:false,scales:{x:{title:{display:true,text:'Sales ('+gstLabel()+')'}},y:{title:{display:true,text:'Profit ('+gstLabel()+')'}}},plugins:{tooltip:{callbacks:{label:ctx=>(ctx.raw.item||'Item')+': '+inr(ctx.raw.x)+' sale / '+inr(ctx.raw.y)+' profit'}}}}});
      charts.storeAdvanced=new Chart(document.getElementById('storeAdvancedChart'),{type:'bar',data:{labels:stores.map(x=>x.store),datasets:[{label:'Sales',data:stores.map(x=>x.sales),backgroundColor:'#155eef'},{label:'Profit',data:stores.map(x=>x.profit),backgroundColor:'#0f9d84'}]},options:{responsive:true,maintainAspectRatio:false}});
    }

    async function toggleItemsView() {
      itemsViewOpen = !itemsViewOpen;
      const card = document.getElementById('itemsViewCard');
      const btn = document.getElementById('viewItemsBtn');
      if (itemsViewOpen) {
        card.classList.remove('hidden');
        btn.textContent = '\u{1F441} Hide Items';
        await loadItemsView();
      } else {
        card.classList.add('hidden');
        btn.textContent = '\u{1F441} View Items';
      }
    }

    async function init() {
      document.getElementById('loadingState').classList.remove('hidden');
      document.getElementById('emptyState').classList.add('hidden');
      document.getElementById('dashboardContent').classList.add('hidden');

      const meta = await loadMeta();
      if (!meta) return;
      renderUploadControls(meta);
      renderStatusText(meta);

      document.getElementById('loadingState').classList.add('hidden');

      if (!meta.has_data) {
        document.getElementById('emptyStateText').textContent = meta.can_upload
          ? 'Upload a sales export above (Excel or CSV - every sheet in a workbook is read) to generate the profitability dashboard and recommendations.'
          : 'No data has been uploaded yet. Ask your Admin to upload a sales export from the AI Analysis page.';
        document.getElementById('emptyState').classList.remove('hidden');
        return;
      }

      populateFilterOptions(meta);
      await refreshDashboard();
    }

    init().catch(error=>{document.getElementById("loadingState").classList.add("hidden"); document.getElementById("emptyState").classList.remove("hidden"); document.getElementById("emptyStateText").textContent=error.message;});
  