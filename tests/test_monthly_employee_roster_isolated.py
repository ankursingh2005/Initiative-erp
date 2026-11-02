"""Verify Monthly Incentive uses exactly the EMS salary employee roster."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
source=ast.parse(Path('ems.py').read_text(encoding='utf-8'))
node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='monthly_incentive_employees')
preview=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='salary_preview')
preview_roster=next(n.iter for n in preview.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and any(isinstance(t,ast.Name) and t.id=='employee' for t in n.target.elts))
endpoint_roster=next(n.iter for n in ast.walk(node) if isinstance(n,ast.comprehension) and isinstance(n.target,ast.Tuple))
assert ast.dump(preview_roster,include_attributes=False)==ast.dump(endpoint_roster,include_attributes=False)
class Col:
    def __init__(self,name):self.name=name
    def __eq__(self,value):return lambda employee:getattr(employee,self.name)==value
    def __le__(self,value):return lambda employee:getattr(employee,self.name)<=value
    def desc(self):return self.name
class Query:
    def __init__(self,rows,roster=False):self.rows=rows;self.roster=roster
    def filter(self,predicate):self.rows=[r for r in self.rows if predicate(r[0] if self.roster else r)];return self
    def order_by(self,*args):return self
    def all(self):return self.rows
calls=[]
def employees(db,include_excluded=True):
    calls.append(include_excluded)
    rows=[(NS(id=1,full_name='ERP Name',username='user1',status='Active',role='Employee',category_code=''),NS(employee_id='IDS-1'),NS(name='ALM')),
          (NS(id=2,full_name='No Setup',username='user2',status='Active',role='EMSManual',category_code='ids_emp'),None,None),
          (NS(id=3,full_name='Inactive',username='user3',status='Inactive',role='Employee',category_code=''),None,None)]
    return Query(rows,True)
scope=dict(month_bounds=lambda m:None,ems_employee_names=lambda db:{1:'Saved EMS Name'},employee_rows=employees,employee_category=lambda employee:'ids_emp',models=NS(User=NS(status=Col('status'),full_name=Col('full_name'))),M=NS(EMSSalaryProfile=NS(effective_month=Col('effective_month'))))
node.decorator_list=[];node.args.defaults=[];node.returns=None
for arg in node.args.args:arg.annotation=None
exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)
class RosterTests(unittest.TestCase):
    def test_names_ids_missing_setup_and_active_roster(self):
        profiles=[NS(user_id=1,effective_month='2026-10',employment_category='Regular')]
        rows=scope['monthly_incentive_employees']('2026-10',NS(query=lambda model:Query(profiles)),NS())
        self.assertEqual(calls, [False])
        self.assertEqual([r['user_id'] for r in rows],[1,2])
        self.assertEqual(rows[0]['name'],'Saved EMS Name')
        self.assertEqual(rows[0]['employee_id'],'IDS-1')
        self.assertEqual(rows[0]['employment_category'],'Regular')
        self.assertEqual(rows[1]['name'],'No Setup')
        self.assertIsNone(rows[1]['employment_category'])
if __name__=='__main__':unittest.main()
