const {test}=require('node:test');const assert=require('node:assert/strict');
const {calculateDistribution:calc}=require('../static/salary-distribution-math.js');
test('full pay above threshold has no bonus or ESIC',()=>{
 const r=calc(2000000,0,500000,100000);
 assert.equal(r.actual_basic,2000000);assert.equal(r.actual_vda,125000);assert.equal(r.actual_pay_epf,2125000);
 assert.equal(r.actual_oa,500000);assert.equal(r.total_earning,2625000);assert.equal(r.bonus_payable,0);
 assert.equal(r.epf_employee,255000);assert.equal(r.esic_employee,0);assert.equal(r.total_deductions,355000);assert.equal(r.net_amount,2270000);
});
test('below threshold bonus and ESIC use their distinct bases',()=>{
 const r=calc(1600000,0,0,10000);
 assert.equal(r.total_earning,1700000);assert.equal(r.bonus_payable,141610);assert.equal(r.actual_gross_earning,1841610);
 assert.equal(r.epf_employee,204000);assert.equal(r.esic_employee,13812);assert.equal(r.net_amount,1613798);
});
test('exactly INR 21000 excludes bonus and ESIC',()=>{
 const r=calc(1600000,0,400000,0);assert.equal(r.total_earning,2100000);assert.equal(r.bonus_payable,0);assert.equal(r.esic_employee,0);
});
test('bonus can raise gross above ESIC threshold',()=>{
 const r=calc(1600000,0,399999,0);assert.equal(r.total_earning,2099999);assert.equal(r.bonus_payable,141610);assert.equal(r.esic_employee,0);
});
test('attendance prorates basic and allowances using 30 minus absence',()=>{
 const r=calc(2000000,15,400000,0);assert.equal(r.working_days,15);assert.equal(r.actual_basic,1000000);assert.equal(r.actual_oa,200000);assert.equal(r.actual_vda,62500);
});
test('all absent yields zero earnings and retains a fixed advance deduction',()=>{
 const r=calc(2000000,30,400000,10000);assert.equal(r.actual_gross_earning,0);assert.equal(r.epf_employee,0);assert.equal(r.esic_employee,0);assert.equal(r.net_amount,-10000);
 assert.equal(calc(2000000,31).working_days,0);
});
test('paise are rounded half up consistently',()=>{const r=calc(100,15,100,0);assert.equal(r.actual_basic,50);assert.equal(r.actual_oa,50);assert.equal(r.actual_vda,3);});

test('unused weekoff pay stays in phase 2 without changing phase 1 net',()=>{
 const base=calc(2000000,0,500000,100000,4);
 const r=calc(2000000,0,500000,100000,2);
 assert.equal(r.weekoff_credit,2);assert.equal(r.weekoff_pay,175000);
 assert.equal(r.net_amount,base.net_amount);
 assert.equal(calc(2000000,0,500000,100000,5).weekoff_pay,0);
 assert.equal(calc(2000000,30,0,0,0).weekoff_pay,0);
});
