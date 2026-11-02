"""Verify editing and resetting monthly-linked W/O incentives without live data."""
import ast
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
class Col:
    def __init__(self,name):self.name=name
    def __eq__(self,value):return (self.name,value)
    def in_(self,value):return (self.name,value)
class Override:
    month=Col('month')
    user_id=Col('user_id')
    def __init__(self,**kwargs):self.__dict__.update(kwargs)
class DB:
    def __init__(self):self.rows={}
    def get(self,model,key):return self.rows.get(key)
    def add(self,row):self.rows[(row.user_id,row.month)]=row
    def delete(self,row):del self.rows[(row.user_id,row.month)]
    def commit(self):pass
    def query(self,model):return NS(filter=lambda *args:NS(all=lambda:[r for r in self.rows.values() if all(getattr(r,k) in v if isinstance(v,list) else getattr(r,k)==v for k,v in args)] if model is Override else []))
scope=dict(datetime=datetime,Decimal=Decimal,month_bounds=lambda m:None,lock_employee=lambda *args:None,record=lambda *args:None,serialize=lambda row:vars(row),employee_rows=lambda *args,**kwargs:NS(all=lambda:[(NS(id=1),None,None)]),monthly_weekoff_amounts=lambda db,month,ids:{1:264300},M=NS(EMSWeekoffIncentiveOverride=Override,EMSWeekoffIncentive=NS(month=Col('month'),user_id=Col('user_id'))))
for node in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body:
    if isinstance(node,ast.FunctionDef) and node.name in {'save_weekoff_incentive','reset_weekoff_incentive_override','weekoff_incentives'}:
        node.decorator_list=[];node.args.defaults=[];node.returns=None
        for arg in node.args.args:arg.annotation=None
        exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)
class OverrideTests(unittest.TestCase):
    def test_increase_reduce_zero_month_scope_and_reset(self):
        db=DB();user=NS(id=2)
        def read(month):return scope['weekoff_incentives'](month,db,user)[0]
        def save(month,value):scope['save_weekoff_incentive'](1,NS(month=month,incentive=Decimal(value),model_dump_json=lambda:'{}'),db,user)
        self.assertEqual(read('2026-10')['incentive'],264300)
        for value,paise in [('3000',300000),('2000.50',200050),('0',0)]:
            save('2026-10',value)
            self.assertEqual(read('2026-10')['incentive'],paise)
            self.assertEqual(read('2026-10')['monthly_amount'],264300)
            self.assertTrue(read('2026-10')['manual_override'])
        save('2026-11','100')
        self.assertEqual(db.rows[(1,'2026-10')].incentive,0)
        scope['reset_weekoff_incentive_override'](1,'2026-10',db,user)
        self.assertEqual(read('2026-10')['incentive'],264300)
        self.assertNotIn('manual_override',read('2026-10'))
        self.assertEqual(db.rows[(1,'2026-11')].incentive,10000)
if __name__=='__main__':unittest.main()
