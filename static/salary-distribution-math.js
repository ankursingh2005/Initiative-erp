(function(root){
 'use strict';
 function calculateDistribution(expectedBasic,absent,otherAllowances=0,staffAdvance=0){
  absent=Math.min(30,Math.max(0,Math.trunc(absent)));
  const working=30-absent;
  const ratio=(value,n,d)=>Number((BigInt(value)*BigInt(n)+BigInt(d)/2n)/BigInt(d));
  const actualBasic=ratio(expectedBasic,working,30),vda=ratio(actualBasic,625,10000),epfPay=actualBasic+vda;
  const actualOA=ratio(otherAllowances,working,30),earning=epfPay+actualOA;
  const bonus=earning<2100000?ratio(epfPay,833,10000):0,gross=earning+bonus;
  const epf=ratio(epfPay,12,100),esic=gross<2100000?ratio(gross,75,10000):0,deductions=epf+esic+staffAdvance;
  return {absent,no_of_days:30,working_days:working,expected_basic:expectedBasic,actual_basic:actualBasic,
   other_allowances:otherAllowances,actual_vda:vda,actual_pay_epf:epfPay,actual_oa:actualOA,
   total_earning:earning,bonus_payable:bonus,actual_gross_earning:gross,epf_employee:epf,
   esic_employee:esic,staff_advance:staffAdvance,total_deductions:deductions,net_amount:gross-deductions};
 }
 const api={calculateDistribution};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.salaryDistributionMath=api;
})(globalThis);
