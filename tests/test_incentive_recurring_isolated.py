"""Exercise recurring incentive settings and automatic monthly uploads in isolation."""
import ast
import calendar
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from incentive_period import detect_incentive_month

class HTTPException(Exception):
    def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
class Col:
    def __init__(self,name):self.name=name
    def __eq__(self,value):return lambda r:getattr(r,self.name)==value
    def __le__(self,value):return lambda r:getattr(r,self.name)<=value
    def in_(self,value):return lambda r:getattr(r,self.name) in value
    def desc(self):return self.name
class Row:
    month=Col('month');user_id=Col('user_id')
    def __init__(self,**kwargs):self.__dict__.update(kwargs)
class Type(Row):pass
class Sales(Row):pass
class NonSales(Row):pass
class Percentage(Row):pass
class Release(Row):pass
class Upload(Row):pass
class Query:
    def __init__(self,db,model):self.db=db;self.model=model;self.predicates=[];self.sort=None
    def filter(self,*predicates):self.predicates.extend(predicates);return self
    def order_by(self,sort):self.sort=sort;return self
    def all(self):
        rows=[r for r in self.db.rows.get(self.model,[]) if all(p(r) for p in self.predicates)]
        return sorted(rows,key=lambda r:getattr(r,self.sort),reverse=True) if self.sort else rows
    def delete(self):self.db.rows[self.model]=[]
class DB:
    def __init__(self):self.rows={}
    def query(self,model):return Query(self,model)
    def add(self,row):self.rows.setdefault(type(row),[]).append(row)
    def get(self,model,key):
        return next((r for r in self.rows.get(model,[]) if ((r.user_id,r.month) if isinstance(key,tuple) else r.month)==key),None)
    def commit(self):pass

M=NS(EMSMonthlyIncentiveType=Type,EMSMonthlySalesSelection=Sales,EMSMonthlyNonSalesSelection=NonSales,EMSMonthlyIncentivePercentage=Percentage)
models=NS(MonthlyIncentiveRelease=Release,IncentiveUpload=Upload)
scope=dict(datetime=datetime,calendar=calendar,Decimal=Decimal,ROUND_HALF_UP=ROUND_HALF_UP,BytesIO=BytesIO,SimpleNamespace=NS,json=json,HTTPException=HTTPException,M=M,models=models,serialize=lambda r:dict(vars(r)),employee_rows=lambda *args,**kwargs:NS(all=lambda:[(NS(id=i),None,None) for i in [1,2]]))
def load(file,names):
    for node in ast.parse(Path(file).read_text(encoding='utf-8')).body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            node.decorator_list=[];node.args.defaults=[];node.returns=None
            for arg in node.args.args:arg.annotation=None
            exec(compile(ast.Module(body=[node],type_ignores=[]),file,'exec'),scope)
load('ems.py',{'month_bounds','effective_incentive_settings','monthly_incentive_types','monthly_incentive_amount','monthly_weekoff_amounts','save_monthly_incentive_percentage'})
scope['lock_employee']=lambda *args:None
scope['record']=lambda *args:None
scope['ems']=NS(month_bounds=scope['month_bounds'])
scope['calculate_incentive_report_from_bytes']=lambda filename,raw,p,i:{'report_version':7,'exact_summary':[{'outlet':'HZT','group':'ALL','exact_incentive':1000 if 'OCT' in filename else 2000}]}
scope['parse_incentive_upload']=lambda file:[{'month':'2026-12'}]
load('main.py',{'calculate_incentive_endpoint'})

class RecurringTests(unittest.TestCase):
    def setUp(self):
        self.db=DB();self.actor=NS(id=9,username='HR')
        self.db.add(Type(user_id=1,month='2026-10',incentive_type='sales'))
        self.db.add(Sales(user_id=1,month='2026-10',outlet='HZT',category_group='ALL'))
        self.db.add(Percentage(user_id=1,month='2026-10',percentage_basis_points=2500))
    def upload(self,name,month=''):
        return scope['calculate_incentive_endpoint'](NS(filename=name,content_type='test',file=BytesIO(b'workbook')),7,2.5,month,self.actor,self.db)
    def test_upload_auto_releases_and_reuses_settings(self):
        self.upload('OCTOBER incentive Data 2026.xlsx')
        self.assertEqual(scope['monthly_weekoff_amounts'](self.db,'2026-10',[1]),{1:25000})
        self.upload('NOVEMBER incentive Data 2026.xlsx')
        settings=scope['monthly_incentive_types']('2026-11',self.db,self.actor)[0]
        self.assertEqual((settings['month'],settings['outlet'],settings['percentage']),('2026-11','HZT',25))
        self.assertEqual(scope['monthly_weekoff_amounts'](self.db,'2026-11',[1]),{1:50000})
        self.assertEqual(scope['monthly_weekoff_amounts'](self.db,'2026-10',[1]),{1:25000})
        self.assertTrue(self.db.get(Release,'2026-11').allowed)
        self.assertEqual(scope['monthly_incentive_types']('2026-09',self.db,self.actor),[])
    def test_non_sales_mapping_and_percentage_also_carry_forward(self):
        self.db.add(Type(user_id=2,month='2026-10',incentive_type='non-sales'))
        self.db.add(NonSales(user_id=2,month='2026-10',location='HZT',field='accounts'))
        self.db.add(Percentage(user_id=2,month='2026-10',percentage_basis_points=2500))
        self.upload('NOVEMBER incentive Data 2026.xlsx')
        release=self.db.get(Release,'2026-11')
        report=json.loads(release.report_json)
        report['ids_fund_report']={'non_sales_report':{'rows':[{'location':'HZT','outlet':'HZT','rates':[35,None,12,15,12],'values':[1200,None,100,150,120]}]}}
        release.report_json=json.dumps(report)
        self.assertEqual(scope['monthly_weekoff_amounts'](self.db,'2026-11',[2]),{2:30000})
        row=next(r for r in scope['monthly_incentive_types']('2026-11',self.db,self.actor) if r['user_id']==2)
        self.assertEqual((row['non_sales_location'],row['non_sales_field'],row['percentage']),('HZT','accounts',25))

    def test_change_applies_forward_and_clear_is_respected(self):
        self.db.add(Percentage(user_id=1,month='2026-11',percentage_basis_points=5000))
        getter=scope['monthly_incentive_types']
        self.assertEqual(getter('2026-10',self.db,self.actor)[0]['percentage'],25)
        self.assertEqual(getter('2026-12',self.db,self.actor)[0]['percentage'],50)
        self.db.add(Type(user_id=1,month='2026-12',incentive_type=''))
        self.assertEqual(getter('2027-01',self.db,self.actor)[0]['incentive_type'],'')
        self.assertEqual(getter('2026-11',self.db,self.actor)[0]['incentive_type'],'sales')
    def test_edit_inherited_setting_without_repeating_category(self):
        payload=NS(month='2026-11',percentage=Decimal('12.5'),model_dump_json=lambda:'{}')
        scope['save_monthly_incentive_percentage'](1,payload,self.db,self.actor)
        getter=scope['monthly_incentive_types']
        self.assertEqual(getter('2026-10',self.db,self.actor)[0]['percentage'],25)
        self.assertEqual(getter('2026-12',self.db,self.actor)[0]['percentage'],12.5)

    def test_bad_month_does_not_replace_existing_upload(self):
        self.upload('OCTOBER incentive Data 2026.xlsx')
        with self.assertRaises(HTTPException):self.upload('NOVEMBER incentive Data 2026.xlsx','2026-10')
        self.assertEqual(self.db.rows[Upload][0].source_file,'OCTOBER incentive Data 2026.xlsx')
        self.assertIsNone(self.db.get(Release,'2026-11'))
    def test_month_from_file_contents_and_explicit_choice(self):
        self.assertEqual(self.upload('incentive.xlsx')['report_month'],'2026-12')
        self.assertEqual(self.upload('another.xlsx','2027-01')['report_month'],'2027-01')
        self.assertEqual(detect_incentive_month('2027-02 sales.pdf'),'2027-02')
        self.assertEqual(detect_incentive_month('October November 2026.xlsx'),'')
if __name__=='__main__':unittest.main()
