const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
function setup(role='Admin',ok=true){
  const elements=[],requests=[],saved=[],errors=[];
  const context={URLSearchParams,today:'2026-10-19',monthPicker:{value:'2026-10'},outletSelect:{value:'2'},
    localStorage:{getItem:key=>key==='role'?role:'token'},alert:message=>errors.push(message),
    setTimeout:fn=>fn(),URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
    fetch:async url=>{requests.push(url);return {ok,status:400,json:async()=>({detail:'Download failed'}),blob:async()=>({})}},
    downloadMenu:{open:true,querySelector:()=>({appendChild(){}})},
    document:{body:{appendChild(){}},createElement:()=>{const el={dataset:{},children:[],textContent:'',setAttribute(k,v){this[k]=v},after(){},appendChild(child){this.children.push(child)},click(){saved.push(this.download)},remove(){}};elements.push(el);return el}}};
  vm.createContext(context);
  vm.runInContext(html.slice(html.indexOf('const monthlyButton='),html.indexOf('function addAttendanceExportFilters(')),context);
  vm.runInContext(html.slice(html.indexOf('async function downloadMonthlyAttendance('),html.indexOf('async function downloadAttendance(format)')),context);
  return {context,elements,requests,saved,errors};
}
test('monthly opens IDS EMP and ISP choices, then downloads complete selected group',async()=>{
  for(const group of ['ids_emp','isp']){
    const {context,elements,requests,saved}=setup();
    const [button,choices]=elements;
    assert.equal(choices.hidden,true);button.onclick({stopPropagation(){}});assert.equal(choices.hidden,false);
    assert.deepEqual(choices.children.map(item=>item.textContent),['IDS EMP','ISP']);
    await context.downloadMonthlyAttendance(group,choices.children.find(item=>item.dataset.monthlyGroup===group));
    const params=new URL(requests[0],'https://example.test').searchParams;
    assert.equal(params.get('monthly_group'),group);assert.equal(params.get('month'),'2026-10');assert.equal(params.get('store_id'),'2');
    for(const key of ['status','emp_category','weekoff_day'])assert.equal(params.has(key),false);
    assert.deepEqual(saved,[group+'-attendance-2026-10.xlsx']);assert.equal(context.downloadMenu.open,false);
  }
});
test('service managers only see IDS choice and failures restore the download button',async()=>{
  const {context,elements,errors}=setup('Service Manager A',false);
  const choice=elements[1].children[0];assert.equal(elements[1].children.length,1);
  await context.downloadMonthlyAttendance('ids_emp',choice);
  assert.equal(choice.disabled,false);assert.equal(choice.textContent,'IDS EMP');assert.deepEqual(errors,['Download failed']);
});
