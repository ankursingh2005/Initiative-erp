const fs=require('fs');let s=fs.readFileSync('static/analytics.html','utf8').replace(/\r\n/g,'\n');
function rep(a,b){if(!s.includes(a))throw Error('Missing '+a.slice(0,70));s=s.replace(a,b);}
rep('All dashboard amounts include a fixed 18% GST uplift; margin is profit divided by sales.', 'Choose Without GST for base amounts or With GST to add 18% to every calculation; margin is profit divided by sales.');
rep('Review amounts below are BEFORE GST. Dashboard amounts add 18% once.', 'Review amounts follow the Calculation selection. Without GST uses base amounts; With GST adds 18%.');
rep('<label for="amountBasis">Source amounts</label><select id="amountBasis"><option value="exclusive">Without GST</option><option value="inclusive">With GST</option></select>', '<label><input type="checkbox" id="sourceIncludesGst" /> File amounts already include 18% GST</label>');
rep('<div class="filter-bar">','<div class="filter-bar">\n          <div class="filter-field"><label for="amountBasis">Calculation</label><select id="amountBasis" onchange="changeGstMode()"><option value="exclusive">Without GST</option><option value="inclusive">With GST</option></select></div>');
rep("formData.append('amount_basis', document.getElementById('amountBasis').value);", "formData.append('amount_basis', document.getElementById('sourceIncludesGst').checked ? 'inclusive' : 'exclusive');");
rep("if (params.search) query.set('search', params.search);", "if (params.search) query.set('search', params.search);\n      query.set('gst', params.gst || 'false');");
rep('    function currentFilterParams() {', `    function withGst(){ return document.getElementById('amountBasis').value === 'inclusive'; }
    function gstLabel(){ return withGst() ? 'With GST (18%)' : 'Without GST'; }
    function changeGstMode(){
      if(reviewState.rows && reviewState.rows.length) renderReviewTable(reviewState.rows);
      refreshDashboard();
    }
    function currentFilterParams() {`);
rep("division: document.getElementById('divisionFilter').value,", "gst: withGst() ? 'true' : 'false',\n        division: document.getElementById('divisionFilter').value,");
rep('      body.innerHTML = rows.map(r => {', "      body.innerHTML = rows.map(source => {\n        const r = withGst() ? {...source, ...source.with_gst} : source;");
rep('`/api/analytics/stage/${reviewState.token}/download`', '`/api/analytics/stage/${reviewState.token}/download?gst=${withGst()}`');
rep("a.download = 'cleaned_analytics_data.csv';", "a.download = withGst() ? 'cleaned_analytics_With_GST.csv' : 'cleaned_analytics_Without_GST.csv';");
rep('Profit incl. GST</div>', 'Profit (${gstLabel()})</div>');
rep('Amounts include 18% GST. Use Previous / Next', '${gstLabel()}. Use Previous / Next');
rep("a.download='AI_Analysis_GST18.csv';", "a.download=withGst()?'AI_Analysis_With_GST.csv':'AI_Analysis_Without_GST.csv';");
rep("+ GST 18%: <b>'+inr(g.sales_gst)", "+ GST '+(g.rate||0)+'%: <b>'+inr(g.sales_gst)");
rep("+ GST 18%: <b>'+inr(g.cost_gst)", "+ GST '+(g.rate||0)+'%: <b>'+inr(g.cost_gst)");
rep('Fixed 18% applied to sales and cost, including Payouts in this analytical view.', "'+(g.enabled ? 'With GST: 18% is applied to sales and cost, including Payouts.' : 'Without GST: no GST is added to sales or cost.')+'");
rep("['Total cost incl. GST',inr(data.kpis.total_cost)]", "['Total cost ('+gstLabel()+')',inr(data.kpis.total_cost)]");
s=s.replaceAll("label:'Sales incl. GST'", "label:'Sales ('+gstLabel()+')'").replaceAll("text:'Sales incl. GST'", "text:'Sales ('+gstLabel()+')'").replaceAll("text:'Profit incl. GST'", "text:'Profit ('+gstLabel()+')'");
fs.writeFileSync('static/analytics.html',s);
fs.writeFileSync('tmp/analytics-inline.js',[...s.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(x=>x[1]).join('\n'));
