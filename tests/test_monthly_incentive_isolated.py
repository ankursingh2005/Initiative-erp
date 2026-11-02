"""Exercise release endpoints without importing the live database or optional dependencies."""
import ast
import calendar
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code

class DB:
    def __init__(self): self.rows = {}; self.upload = NS(report_json='{"exact_summary": [{"outlet": "ALM", "exact_incentive": 50}], "ids_fund_report": {"non_sales_report": {"totals": [12]}}}', source_file='original.xlsx')
    def get(self, model, month): return self.rows.get(month)
    def add(self, row): self.rows[row.month] = row
    def commit(self): pass

class Release:
    def __init__(self, month): self.month = month

scope = dict(datetime=datetime, calendar=calendar, json=json, HTTPException=HTTPException,
             models=NS(MonthlyIncentiveRelease=Release), latest_incentive_upload=lambda db: db.upload)
for file, names in [('ems.py', {'month_bounds', 'monthly_incentive'}), ('main.py', {'allow_monthly_incentive', 'incentive_allow_status'})]:
    tree=ast.parse(Path(file).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list=[]; node.returns=None
            for arg in node.args.args: arg.annotation=None
            node.args.defaults=[]
            exec(compile(ast.Module(body=[node],type_ignores=[]),file,'exec'),scope)
scope['ems']=NS(month_bounds=scope['month_bounds'])

class ReleaseTests(unittest.TestCase):
    def test_month_snapshot_allow_revoke_and_source_independence(self):
        db=DB(); user=NS(id=1)
        read=lambda month: scope['monthly_incentive'](month,db,user)
        save=lambda month,allowed: scope['allow_monthly_incentive'](NS(month=month,allowed=allowed),user,db)
        self.assertFalse(read('2026-09')['allowed'])
        save('2026-09', True)
        self.assertEqual(read('2026-09')['report']['exact_summary'][0]['exact_incentive'],50)
        self.assertEqual(read('2026-09')['report']['ids_fund_report']['non_sales_report']['totals'],[12])
        db.upload=NS(report_json='{}',source_file='new.xlsx')
        save('2026-10',True)
        self.assertEqual(read('2026-09')['source_file'],'original.xlsx')
        db.upload=None
        save('2026-09',False)
        self.assertFalse(read('2026-09')['allowed'])
        self.assertTrue(read('2026-10')['allowed'])
        with self.assertRaises(HTTPException): save('2026-11',True)
        with self.assertRaises(HTTPException): read('2026-13')

if __name__ == '__main__': unittest.main()
