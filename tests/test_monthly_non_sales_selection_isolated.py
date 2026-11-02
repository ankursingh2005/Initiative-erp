"""Check non-sales monthly selection validation without the live database."""
import ast
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

class HTTPException(Exception):
    def __init__(self, status_code, detail): self.status_code=status_code
class Selection:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class DB:
    def __init__(self):
        self.kind=NS(incentive_type='non-sales')
        self.release=NS(allowed=True,report_json=json.dumps({'ids_fund_report':{'non_sales_report':{'rows':[{'location':'ALM'},{'location':'Ware House'}]}}}))
        self.selection=None
    def get(self,model,key):return self.kind if model=='type' else self.release if model=='release' else self.selection
    def add(self,row):self.selection=row
    def commit(self):pass
scope=dict(datetime=datetime,json=json,HTTPException=HTTPException,M=NS(EMSMonthlyIncentiveType='type',EMSMonthlyNonSalesSelection=Selection),models=NS(MonthlyIncentiveRelease='release'),month_bounds=lambda m:None,lock_employee=lambda *args:None,record=lambda *args:None)
scope['effective_incentive_settings']=lambda db,model,month,ids:{uid:db.kind for uid in ids}
node=next(n for n in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='save_monthly_non_sales_selection')
node.decorator_list=[];node.args.defaults=[]
for arg in node.args.args:arg.annotation=None
exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)
class NonSalesTests(unittest.TestCase):
    def test_locations_month_and_allowed_report(self):
        db=DB()
        def save(location,field):return scope['save_monthly_non_sales_selection'](1,NS(month='2026-10',location=location,field=field,model_dump_json=lambda:'{}'),db,NS(id=2))
        for location in ['ALM','Ware House','Central Service']:
            save(location,'accounts')
            self.assertEqual((db.selection.location,db.selection.month),(location,'2026-10'))
        for location,field in [('FAKE','accounts'),('','accounts')]:
            with self.assertRaises(HTTPException):save(location,field)
        save('','');self.assertEqual(db.selection.field,'')
        db.release.allowed=False
        with self.assertRaises(HTTPException):save('ALM','ho')
        db.release.allowed=True;db.kind.incentive_type='sales'
        with self.assertRaises(HTTPException):save('ALM','ho')
if __name__=='__main__':unittest.main()
