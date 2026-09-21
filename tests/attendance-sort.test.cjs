const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('static/attendance.html','utf8'),context={};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function sortAttendanceByCheckin('),html.indexOf('async function loadAdminSummary(')),context);
test('newest check-in appears first, with unpunched users last',()=>{
  const rows=[{id:1,checkin_at:'2026-09-21T11:33:00'}, {id:2,checkin_at:null},
    {id:3,checkin_at:'2026-09-21T12:03:00'}, {id:4,checkin_at:'2026-09-21T09:05:00'},
    {id:5,checkin_at:'invalid'}, {id:6,checkin_at:'2026-09-21T11:33:00'}];
  assert.deepEqual(Array.from(context.sortAttendanceByCheckin(rows),row=>row.id),[3,1,6,4,2,5]);
  assert.deepEqual(rows.map(row=>row.id),[1,2,3,4,5,6]);
});
test('initial, refreshed, and week-off filtered tables all sort check-ins',()=>{
  assert.equal((html.match(/sortAttendanceByCheckin\(data.rows\).map/g)||[]).length,3);
});
