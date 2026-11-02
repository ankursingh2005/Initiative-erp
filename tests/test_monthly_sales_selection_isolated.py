"""Validate monthly sales assignment against the actual allowed report rows."""
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
        self.kind=NS(incentive_type='sales')
        self.release=NS(allowed=True,report_json=json.dumps({'exact_summary':[{'outlet':'ALM','group':'HA + HE','exact_incentive':7649.58}]}))
        self.selection=None
    def get(self, model, key):
        return self.kind if model=='type' else self.release if model=='release' else self.selection
    def add(self,row): self.selection=row
    def commit(self): pass

scope={'datetime':datetime,'json':json,'HTTPException':HTTPException,
       'M':NS(EMSMonthlyIncentiveType='type',EMSMonthlySalesSelection=Selection),
       'models':NS(MonthlyIncentiveRelease='release'), 'month_bounds':lambda m: None,
       'lock_employee':lambda *args:None,'record':lambda *args:None}
scope['effective_incentive_settings']=lambda db,model,month,ids:{uid:db.kind for uid in ids}
node=next(n for n in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='save_monthly_sales_selection')
node.decorator_list=[]
for arg in node.args.args: arg.annotation=None
node.args.defaults=[]
exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)

class SalesSelectionTests(unittest.TestCase):
    def test_save_and_validate_allowed_pairs(self):
        db=DB()
        def save(outlet,group):
            payload=NS(month='2026-10',outlet=outlet,category_group=group,model_dump_json=lambda:'{}')
            return scope['save_monthly_sales_selection'](1,payload,db,NS(id=2))
        save('ALM','HA + HE')
        self.assertEqual((db.selection.month,db.selection.outlet,db.selection.category_group),('2026-10','ALM','HA + HE'))
        for outlet,group in [('ALM','COM'),('FAKE','ALL'),('','HA + HE')]:
            with self.assertRaises(HTTPException):save(outlet,group)
        self.assertEqual(db.selection.category_group,'HA + HE')
        save('ALM','')
        self.assertEqual(db.selection.category_group,'')
        db.release.allowed=False
        with self.assertRaises(HTTPException):save('ALM','HA + HE')
        db.release.allowed=True;db.kind.incentive_type='non-sales'
        with self.assertRaises(HTTPException):save('ALM','HA + HE')

if __name__=='__main__':unittest.main()
