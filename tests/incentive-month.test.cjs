const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const context={};vm.createContext(context);vm.runInContext(fs.readFileSync('static/incentive-month.js','utf8'),context);
for(const [file,expected] of [
 ['OCTOBER incentive Data 2026.xlsx','2026-10'],
 ['November incentive 2026.xlsx','2026-11'],
 ['SEP_2025.xlsx','2025-09'],['incentive_2026-10.xlsx','2026-10'],
 ['10-2026 incentive.xlsx','2026-10'],['incentive.xlsx',''],
 ['October November 2026.xlsx',''],['October 2025 2026.xlsx','']
])assert.equal(context.incentiveMonthFromFilename(file),expected,file);
const html=fs.readFileSync('static/incentive.html','utf8');
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);
assert.match(html,/syncIncentiveMonth\(shared.file_name,/);
assert.match(html,/syncIncentiveMonth\(selectedFile.name,/);
assert.match(html,/syncIncentiveMonth\(file.name\)/);
assert.doesNotMatch(html,/allowParts/);
console.log('Uploaded and restored filename month checks passed; October 2026 selects 2026-10.');
