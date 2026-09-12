const fs=require('fs'); let s=fs.readFileSync('static/analytics.html','utf8').replace(/\r\n/g,'\n');
const replace=(a,b)=>{if(!s.includes(a))throw Error('Missing '+a.slice(0,65));s=s.replace(a,b);};
replace('<h1>Profitability dashboard &amp; recommendations</h1>','<h1>Sales intelligence &amp; profitability</h1>');
replace('Upload a sales/profitability export - any Excel workbook (every sheet is read) or CSV - and get an instant breakdown of your most profitable items and divisions, plus data-driven suggestions to boost sales.', 'Explore HA, HE, Mobile, Computer, Accessories and Payouts. All dashboard amounts include a fixed 18% GST uplift; margin is profit divided by sales. Review unrelated and unclassified rows separately.');
replace("const DIVISION_LABELS = { HA: 'Home Appliance', HE: 'Home Entertainment', Computer: 'Computer / IT', Mobile: 'Mobile', Other: 'Other' };", "const DIVISION_LABELS = { HA: 'HA', HE: 'HE', MH: 'Mobile', IT: 'Computer', ACC: 'Accessories', PAYOUT: 'Payouts', UNCATEGORIZED: 'Needs review', EXCLUDED: 'Excluded / unrelated' };");
replace('<option value="Computer">Computer / IT</option>\n            <option value="Mobile">Mobile</option>\n            <option value="Other">Other</option>', '<option value="IT">Computer</option><option value="MH">Mobile</option><option value="ACC">Accessories</option><option value="PAYOUT">Payouts</option><option value="UNCATEGORIZED">Needs review</option><option value="EXCLUDED">Exclude / unrelated</option>');
replace('<div id="dashboardContent" class="hidden">\n      <div class="card">','<div id="filterControls" class="card">');
replace('      <div id="itemsViewCard" class="card hidden"></div>', `<div id="qualityCard" class="card"><h2>Data quality &amp; GST</h2><div id="qualitySummary">Upload data to begin.</div></div>
      <div id="itemTools" class="card">
        <label for="dataView">Rows to inspect or export</label>
        <select id="dataView" onchange="itemsPage=1; if(itemsViewOpen) loadItemsView();"><option value="included">Included in dashboard</option><option value="review">Needs category review</option><option value="excluded">Excluded / unrelated</option><option value="all">All uploaded rows</option></select>
        <button class="btn btn-primary" onclick="downloadAnalytics()">Download filtered CSV</button>
        <p class="sub">Dashboard totals use included rows only. Review and excluded rows remain available here. CSV includes every matching row, not just the current page.</p>
      </div>
      <div id="itemsViewCard" class="card hidden"></div>
      <div id="dashboardContent" class="hidden">`);
replace('<label for="storeFilter">Store</label>', '<label for="storeFilter">Store</label>');
replace('          <div class="filter-field">\n            <label>&nbsp;</label>\n            <button class="btn btn-ghost" id="viewItemsBtn"', '          <div class="filter-field"><label for="searchFilter">Item, brand or voucher</label><input id="searchFilter" placeholder="Search all rows..." oninput="queueRefresh()" /></div>\n          <div class="filter-field">\n            <label>&nbsp;</label>\n            <button class="btn btn-ghost" id="viewItemsBtn"');
replace('<div class="kpi-grid" id="kpiGrid"></div>', `<div class="kpi-grid" id="kpiGrid"></div>
      <div id="statsGrid" class="kpi-grid"></div>
      <div class="charts-grid"><div class="card"><h2>Daily sales &amp; 7-day average</h2><p class="sub">Trailing calendar-day average; dates with no sales count as zero.</p><div class="chart-box"><canvas id="dailyAdvancedChart"></canvas></div></div><div class="card"><h2>Sales versus profit</h2><p class="sub" id="scatterNote"></p><div class="chart-box"><canvas id="scatterAdvancedChart"></canvas></div></div></div>
      <div class="card"><h2>Store performance</h2><div class="chart-box"><canvas id="storeAdvancedChart"></canvas></div></div>`);
replace('<button class="btn btn-primary" id="analyzeBtn"', '<label for="amountBasis">Source amounts</label><select id="amountBasis"><option value="exclusive">Before GST - add 18%</option><option value="inclusive">Already includes 18% GST</option></select><button class="btn btn-primary" id="analyzeBtn"');
replace("formData.append('file', file);", "formData.append('file', file);\n      formData.append('amount_basis', document.getElementById('amountBasis').value);");
replace('Divisions and brands were auto-detected, and matching AC indoor/outdoor rows were combined. Check it over, fix anything that\'s wrong, then proceed.', 'Review amounts below are BEFORE GST. Dashboard amounts add 18% once. Check category assignments; Needs review and Excluded rows stay out of dashboard totals. Matching AC indoor/outdoor rows are combined.');
replace("if (params.end_date) query.set('end_date', params.end_date);\n      const qs", "if (params.end_date) query.set('end_date', params.end_date);\n      if (params.search) query.set('search', params.search);\n      const qs");
replace("const res = await authFetch('/api/analytics/dashboard' + (qs ? '?' + qs : ''));\n      if (!res) return null;\n      return await res.json();", "const res = await authFetch('/api/analytics/dashboard' + (qs ? '?' + qs : ''));\n      if (!res) return null;\n      const data = await res.json();\n      if (!res.ok) throw new Error(data.detail || 'Could not load dashboard');\n      return data;");
replace("store: document.getElementById('storeFilter').value,", "store: document.getElementById('storeFilter').value,\n        search: document.getElementById('searchFilter').value.trim(),");
replace("document.getElementById('storeFilter').value = 'ALL';", "document.getElementById('storeFilter').value = 'ALL';\n      document.getElementById('searchFilter').value = '';\n      document.getElementById('dataView').value = 'included';");
replace('      renderRecommendations(data);','      renderRecommendations(data);\n      renderAdvanced(data);');
replace('<div class="label">Total Profit</div>', '<div class="label">Profit incl. GST</div>');
replace('<div class="label">Margin</div>', '<div class="label">Margin on sales</div>');
replace("    async function refreshDashboard() {", "    let dashboardRequest = 0;\n    let searchDelay;\n    function queueRefresh(){ clearTimeout(searchDelay); searchDelay=setTimeout(refreshDashboard,350); }\n    async function refreshDashboard() {");
let a=s.indexOf('    async function refreshDashboard() {'),b=s.indexOf('    function resetFilters()',a);
s=s.slice(0,a)+`    async function refreshDashboard() {
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

`+s.slice(b);
replace('    let itemsViewOpen = false;', '    let itemsViewOpen = false;\n    let itemsPage = 1;\n    let itemRequest = 0;');
replace('<td class="num">${it.qty ?? \'\'}</td>', '<td class="num">${esc(it.qty ?? \'\')}</td>');
replace('<td class="num">${inr(it.profit_loss)}</td>','<td class="num">${inr(it.profit_loss)}</td><td>${esc(it.status)}</td><td>${esc(it.exclusion_reason)}</td>');
replace('<th class="num">Profit</th></tr>', '<th class="num">Profit</th><th>Status</th><th>Review reason</th></tr>');
replace('<h2>Items (${items.length})</h2>', '<h2>Line items</h2>');
replace('Every line item matching the current filters.', 'Amounts include 18% GST. Use Previous / Next to inspect every matching row.');
a=s.indexOf('    async function loadItemsView() {');b=s.indexOf('    async function toggleItemsView()',a);
s=s.slice(0,a)+`    function itemQuery(){
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
        a.href=url;a.download='AI_Analysis_GST18.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      }catch(error){alert(error.message);}
    }
    function renderQuality(data){
      const q=data.quality||{}, g=data.gst||{};
      document.getElementById('qualitySummary').innerHTML='<div class="quality-badges"><span>Included: '+(q.included||0)+'</span><span>Needs review: '+(q.review||0)+'</span><span>Excluded: '+(q.excluded||0)+'</span></div><p>Sales before GST: <b>'+inr(g.sales_before_gst)+'</b> + GST 18%: <b>'+inr(g.sales_gst)+'</b>. Cost before GST: <b>'+inr(g.cost_before_gst)+'</b> + GST 18%: <b>'+inr(g.cost_gst)+'</b>.</p><p class="sub">Fixed 18% applied to sales and cost, including Payouts in this analytical view. Profit = displayed sales minus displayed cost. These are product margins, before operating expenses. Unknown historical stores appear as Unknown.</p>';
    }
    function renderAdvanced(data){
      renderQuality(data);
      const a=data.advanced||{},d=a.distribution||{},daily=a.daily_trend||[],stores=a.store_breakdown||[];
      document.getElementById('statsGrid').innerHTML=[['Total cost incl. GST',inr(data.kpis.total_cost)],['Median line sale',inr(d.median_sale)],['Sales standard deviation',inr(d.sale_stddev)],['Loss-making rows',d.loss_rows||0],['Unusual sale amounts',d.outliers_evaluable?d.outlier_rows:'Not enough variation']].map(([label,value])=>'<div class="kpi"><div class="label">'+label+'</div><div class="value">'+value+'</div></div>').join('');
      document.getElementById('scatterNote').textContent='First '+Math.min(a.scatter_total||0,1000)+' of '+(a.scatter_total||0)+' included rows in date order. Export includes all rows. Unusual amounts use median absolute deviation; they are not removed.';
      charts.dailyAdvanced=new Chart(document.getElementById('dailyAdvancedChart'),{type:'line',data:{labels:daily.map(x=>x.date),datasets:[{label:'Sales incl. GST',data:daily.map(x=>x.sales),borderColor:'#155eef',pointRadius:1},{label:'7-day average',data:daily.map(x=>x.rolling_7_sales),borderColor:'#0f9d84',pointRadius:0}]},options:{responsive:true,maintainAspectRatio:false}});
      charts.scatterAdvanced=new Chart(document.getElementById('scatterAdvancedChart'),{type:'scatter',data:{datasets:[{label:'Sales / profit',data:a.scatter||[],backgroundColor:'#7258d9aa'}]},options:{responsive:true,maintainAspectRatio:false,scales:{x:{title:{display:true,text:'Sales incl. GST'}},y:{title:{display:true,text:'Profit incl. GST'}}},plugins:{tooltip:{callbacks:{label:ctx=>(ctx.raw.item||'Item')+': '+inr(ctx.raw.x)+' sale / '+inr(ctx.raw.y)+' profit'}}}}});
      charts.storeAdvanced=new Chart(document.getElementById('storeAdvancedChart'),{type:'bar',data:{labels:stores.map(x=>x.store),datasets:[{label:'Sales',data:stores.map(x=>x.sales),backgroundColor:'#155eef'},{label:'Profit',data:stores.map(x=>x.profit),backgroundColor:'#0f9d84'}]},options:{responsive:true,maintainAspectRatio:false}});
    }

`+s.slice(b);
// Keep filter controls available even when a selection is empty.
a=s.indexOf('      populateFilterOptions(meta);', s.indexOf('    async function init()'));
b=s.indexOf('\n    }',a);
s=s.slice(0,a)+'      populateFilterOptions(meta);\n      await refreshDashboard();'+s.slice(b);
replace('    init();','    init().catch(error=>{document.getElementById("loadingState").classList.add("hidden"); document.getElementById("emptyState").classList.remove("hidden"); document.getElementById("emptyStateText").textContent=error.message;});');
replace('</style>', `
    body { background: linear-gradient(135deg,#f0f5ff 0%,#f6f9fc 60%,#eefaf6 100%); }
    .intro h1 { letter-spacing:-1px; }
    .card { border:1px solid #e0e8f2; box-shadow:0 6px 25px #15375d08; }
    .kpi { border-top:3px solid #155eef; }
    .quality-badges { display:flex; flex-wrap:wrap; gap:10px; }
    .quality-badges span { padding:8px 14px; border-radius:25px; background:#e9f1ff; font-weight:700; }
    .quality-badges span:nth-child(2) { background:#fff3d8; }
    .quality-badges span:nth-child(3) { background:#fceaea; }
    .item-pagination { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-top:16px; }
    #itemTools select { max-width:100%; padding:10px; margin:8px; }
    #statsGrid .value { font-size:20px; }
    .chart-box { position:relative; height:300px; }
  </style>`);
fs.writeFileSync('static/analytics.html',s);
const scripts=[...s.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');
fs.writeFileSync('tmp/analytics-inline.js',scripts);
