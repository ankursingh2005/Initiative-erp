const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
for(const ok of [true,false])test(`previously unset weekly off ${ok?'can be saved and cleared':'shows the save error'}`,async()=>{
  let change,alertText;
  const select={value:'',addEventListener:(event,fn)=>{change=fn}},label={classList:{add(){},remove(){}}},selected={};
  const context={profile:{},document:{getElementById:id=>({weekoffSelect:select,weekoffLabel:label,selectedWeekoff:selected}[id])},
    localStorage:{getItem:()=> 'token'},alert:text=>{alertText=text},setTimeout(){},
    fetch:async(path,options)=>options?{ok,json:async()=>ok?JSON.parse(options.body):{detail:'Could not save'}}:{ok:true,json:async()=>({weekoff_day:null})}};
  vm.createContext(context);
  await vm.runInContext(html.slice(html.indexOf('(async function initializeWeekoffPreference'),html.indexOf('(function addAdminWeekoffFilter')),context);
  select.value='Sunday';await change();assert.equal(select.disabled,false);
  if(ok){assert.equal(select.value,'Sunday');assert.equal(context.profile.weekoff_day,'Sunday');select.value='';await change();assert.equal(select.value,'')}
  else{assert.equal(select.value,'');assert.equal(alertText,'Could not save')}
});
