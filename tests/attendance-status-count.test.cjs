const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8');
const context={};vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function attendanceStatusCount('),html.indexOf('(function addWeekOffSummaryCard')),context);
test('week off and leave cards count daily and range statuses',()=>{
  const count=context.attendanceStatusCount;
  assert.equal(count('Week Off','Week Off'),1);
  assert.equal(count('Leave','Leave'),1);
  assert.equal(count('Absent','Leave'),0);
  const status='10/15 Present · 2 Week Off · 1 Leave · 2 Absent';
  assert.equal(count(status,'Week Off'),2);
  assert.equal(count(status,'Leave'),1);
  assert.equal(count('0/1 Present · 0 Week Off · 0 Leave · 1 Absent','Leave'),0);
});
test('attendance page scripts parse',()=>{
  for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
});
