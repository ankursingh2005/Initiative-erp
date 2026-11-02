"""Check exact monthly percentage storage without touching the live database."""
import ast
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
class HTTPException(Exception):
    def __init__(self,status_code,detail):self.status_code=status_code
class Percentage:
    def __init__(self,**kwargs):self.__dict__.update(kwargs)
class DB:
    def __init__(self):self.rows={};self.kind=NS(incentive_type='sales')
    def get(self,model,key):return self.kind if model=='type' else self.rows.get(key)
    def add(self,row):self.rows[(row.user_id,row.month)]=row
    def commit(self):pass
scope=dict(datetime=datetime,HTTPException=HTTPException,M=NS(EMSMonthlyIncentiveType='type',EMSMonthlyIncentivePercentage=Percentage),month_bounds=lambda m:None,lock_employee=lambda *args:None,record=lambda *args:None)
scope['effective_incentive_settings']=lambda db,model,month,ids:{uid:db.kind for uid in ids}
node=next(n for n in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='save_monthly_incentive_percentage')
node.decorator_list=[];node.args.defaults=[]
for arg in node.args.args:arg.annotation=None
exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)
class PercentageTests(unittest.TestCase):
    def test_exact_decimal_storage_and_month_scope(self):
        db=DB()
        def save(month,value):return scope['save_monthly_incentive_percentage'](1,NS(month=month,percentage=Decimal(value),model_dump_json=lambda:'{}'),db,NS(id=2))
        for kind in ['sales','non-sales']:
            db.kind.incentive_type=kind
            for value,expected in [('12.35',1235),('0',0),('100',10000)]:
                result=save('2026-10',value)
                self.assertEqual(db.rows[(1,'2026-10')].percentage_basis_points,expected)
                self.assertEqual(result['percentage'],float(value))
        save('2026-11','25')
        self.assertEqual(db.rows[(1,'2026-10')].percentage_basis_points,10000)
        self.assertEqual(db.rows[(1,'2026-11')].percentage_basis_points,2500)
        db.kind.incentive_type=''
        with self.assertRaises(HTTPException):save('2026-11','10')
if __name__=='__main__':unittest.main()
