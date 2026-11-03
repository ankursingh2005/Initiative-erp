const fs=require('fs');let p='static/ems.js',s=fs.readFileSync(p,'utf8');s=s.replace("const input=event.target;if(!input.matches('[data-incentive-percentage]'))return;","const input=event.target;if(input.matches('[data-incentive-addition]'))return previewMonthlyAddition(event);if(!input.matches('[data-incentive-percentage]'))return;");s=s.replace("$('monthlyIncentiveEmployees').addEventListener('input',event=>{\n const input=event.target;if(!input.matches('[data-incentive-addition]'))return;","function previewMonthlyAddition(event){\n const input=event.target;");s=s.replace("input.closest('tr').cells[7].innerHTML=monthlyAmountBadge(fields[2]);\n});\nasync function saveMonthlyAddition", "input.closest('tr').cells[7].innerHTML=monthlyAmountBadge(fields[2]);\n}\nasync function saveMonthlyAddition");fs.writeFileSync(p,s);
p='tests/monthly-incentive-ui.test.cjs';s=fs.readFileSync(p,'utf8').replaceAll('cells[6]','cells[7]').replace("row.cells=[{},{},{},{},{},{},{innerHTML:''}];","row.cells=[{},{},{},{},{},{},{},{innerHTML:''}];");let marker=' // Percentage edits preview';let test=` // Additional amount previews immediately, saves, and clears without changing percentage.
 row.cells=[{},{},{},{},{},{},{},{innerHTML:''}];
 vm.runInContext("monthlySalesReports.set('2026-09',[{outlet:'ALM',group:'ALL',exact_incentive:141}]);monthlyIncentiveTypes.set('2026-09:1','sales');monthlyPercentages.set('2026-09:1',10);",context);
 const additionInput={value:'100',dataset:{incentiveAddition:'1'},checkValidity:()=>true,reportValidity:()=>true,closest:()=>row,parentElement:{querySelector:()=>liveStatus},matches:selector=>selector==='[data-incentive-addition]'};
 nodes.get('monthlyIncentiveEmployees').input({target:additionInput});
 assert.match(row.cells[7].innerHTML,/114.10/);
 await nodes.get('monthlyIncentiveEmployees').change({target:additionInput});
 assert.deepEqual(submitted,{month:'2026-09',additional_amount:100});
 assert.equal(vm.runInContext("monthlyAdditions.get('2026-09:1')",context),100);
 assert.match(vm.runInContext("monthlyDashboardCells(state.rows[0],'sales','2026-09')[4]",context),/data-incentive-addition/);
 additionInput.value='';nodes.get('monthlyIncentiveEmployees').input({target:additionInput});
 assert.match(row.cells[7].innerHTML,/14.10/);
 await nodes.get('monthlyIncentiveEmployees').change({target:additionInput});
 assert.deepEqual(submitted,{month:'2026-09',additional_amount:0});
`;s=s.replace(marker,test+marker);fs.writeFileSync(p,s);
