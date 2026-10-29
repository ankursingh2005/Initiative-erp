(function(root){
 'use strict';
 function calculateDistribution(expectedBasic,absent,otherAllowances=0,staffAdvance=0,weekoffAvailed=4,employmentCategory='Regular'){
  const regular=employmentCategory==='Regular';
  absent=Math.min(30,Math.max(0,Math.trunc(absent)));
  const working=30-absent;
  const ratio=(value,n,d)=>Number((BigInt(value)*BigInt(n)+BigInt(d)/2n)/BigInt(d));
  const actualBasic=ratio(expectedBasic,working,30),vda=ratio(actualBasic,625,10000),epfPay=actualBasic+vda;
  const actualOA=ratio(otherAllowances,working,30),earning=epfPay+actualOA;
  const proposedBonus=ratio(epfPay,833,10000);
  const bonus=regular&&earning+proposedBonus<2100000?proposedBonus:0,gross=earning+bonus;
  const credit=Math.max(0,4-weekoffAvailed),weekoffPay=ratio(gross,credit,30);
  const epf=regular?ratio(epfPay,12,100):0,esic=regular&&gross<2100000?ratio(gross,75,10000):0,deductions=epf+esic+staffAdvance;
  return {absent,no_of_days:30,working_days:working,expected_basic:expectedBasic,actual_basic:actualBasic,
   other_allowances:otherAllowances,actual_vda:vda,actual_pay_epf:epfPay,actual_oa:actualOA,
   total_earning:earning,bonus_payable:bonus,actual_gross_earning:gross,epf_employee:epf,
   esic_employee:esic,staff_advance:staffAdvance,weekoff_availed:weekoffAvailed,weekoff_credit:credit,weekoff_pay:weekoffPay,total_deductions:deductions,net_amount:gross-deductions};
 }
 const api={calculateDistribution};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.salaryDistributionMath=api;
})(globalThis);
