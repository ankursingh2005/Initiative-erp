const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const nodes=new Map();
function element(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},addEventListener(){},focus(){},setAttribute(){},setCustomValidity(){},querySelector(){return element();},querySelectorAll(){return [];},checkValidity(){return true;},elements:new Proxy({},{get:(t,k)=>t[k]??=(element())})};}
const context={setInterval(){},console,Intl,Date,Number,String,Math,Set,JSON,URL,setTimeout,Blob,
 location:{pathname:'/ems'},localStorage:{getItem(){return null;}},
 document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},querySelectorAll(){return [];},addEventListener(){}},
 window:{addEventListener(){},matchMedia(){return {matches:false};}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/salary-distribution-math.js','utf8'),context);vm.runInContext(fs.readFileSync('static/ems.js','utf8'),context);

(async()=>{
 nodes.get('month').value='2026-09';
 context.fetch=async()=>({ok:true,status:200,text:async()=>JSON.stringify({allowed:true,source_file:'test.xlsx',report:{exact_summary:[{outlet:'ALM',group:'ALL',exact_incentive:50}],ids_fund_report:{non_sales_report:{rows:[{location:'ALM',outlet:'ALM',ids_fund:100,rates:[35,null,12,15,15],values:[35,null,12,15,15]}],totals:[35,16,12,15,15]}}}})});
 await vm.runInContext('loadMonthlyIncentive()',context);
 assert.match(nodes.get('monthlyIncentiveReports').innerHTML,/SALES INCENTIVE/);
 assert.match(nodes.get('monthlyIncentiveReports').innerHTML,/NON SALES INCENTIVE/);
 assert.match(nodes.get('monthlyIncentiveReports').innerHTML,/Central Service/);
 assert.match(nodes.get('monthlyIncentiveReports').innerHTML,/50/);
 context.fetch=async()=>({ok:true,status:200,text:async()=>JSON.stringify({allowed:false})});
 await vm.runInContext('loadMonthlyIncentive()',context);
 assert.equal(nodes.get('monthlyIncentiveReports').innerHTML,'');
 assert.match(nodes.get('monthlyIncentiveStatus').textContent,/not been allowed/);
 console.log('Monthly Incentive allowed and hidden UI checks passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
