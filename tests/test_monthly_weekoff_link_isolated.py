"""Verify monthly report amounts and the W/O overlay without the live database."""
import ast
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
scope=dict(Decimal=Decimal,ROUND_HALF_UP=ROUND_HALF_UP)
node=next(n for n in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='monthly_incentive_amount')
exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),scope)
amount=scope['monthly_incentive_amount']
report={'exact_summary':[{'outlet':'HZT','group':'HA + HE','exact_incentive':5771.23}], 'ids_fund_report':{'non_sales_report':{'rows':[{'outlet':'HZT','location':'HZT','ids_fund':7551.21,'rates':[35,None,12,15,12],'values':[2643,None,906,1133,906]},{'outlet':'MWH','location':'Ware House','ids_fund':17127.81,'rates':[None,16,None,None,None],'values':[None,2740.45,None,None,None]}],'totals':[5996,2740.45,2055,2570,2219]}}}
class AmountTests(unittest.TestCase):
    def test_sales_percentage_rounding_zero_and_missing_pair(self):
        sale=NS(outlet='HZT',category_group='HA + HE')
        self.assertEqual(amount(report,'sales',sales=sale),577123)
        self.assertEqual(amount(report,'sales',sales=sale,percentage=2500),144281)
        self.assertEqual(amount(report,'sales',sales=sale,percentage=0),0)
        self.assertEqual(amount(report,'sales',sales=NS(outlet='ALM',category_group='ALL')),0)
        self.assertEqual(amount(report,'sales'),0)
    def test_non_sales_report_fields_and_dashes(self):
        selected=NS(location='HZT',field='accounts')
        self.assertEqual(amount(report,'non-sales',non_sales=selected),264300)
        self.assertEqual(amount(report,'non-sales',non_sales=selected,percentage=1250),33038)
        selected.field='ware_house'
        self.assertEqual(amount(report,'non-sales',non_sales=selected),0)
        selected.location='Ware House'
        self.assertEqual(amount(report,'non-sales',non_sales=selected),274045)
        selected.field='ids_fund'
        self.assertEqual(amount(report,'non-sales',non_sales=selected),0)
        selected.location='Central Service';selected.field='accounts'
        self.assertEqual(amount(report,'non-sales',non_sales=selected),599600)
    def test_weekoff_overlay_preserves_manual_records(self):
        source=NS(user_id=1,incentive=999,month='2026-10')
        other=NS(user_id=2,incentive=4500,month='2026-10')
        class Query:
            def filter(self,*args):return self
            def all(self):return [source,other]
        node=next(n for n in ast.parse(Path('ems.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='weekoff_incentives')
        node.decorator_list=[];node.args.defaults=[];node.returns=None
        for arg in node.args.args:arg.annotation=None
        env=dict(month_bounds=lambda m:None,employee_rows=lambda *args,**kwargs:NS(all=lambda:[(NS(id=i),None,None) for i in [1,2,3]]),M=NS(EMSWeekoffIncentiveOverride=NS(month='2026-10',user_id=NS(in_=lambda ids:True)),EMSWeekoffIncentive=NS(month='2026-10',user_id=NS(in_=lambda ids:True))),serialize=lambda row:dict(vars(row)),monthly_weekoff_amounts=lambda db,month,ids:{1:264300,3:577123})
        exec(compile(ast.Module(body=[node],type_ignores=[]),'ems.py','exec'),env)
        rows={r['user_id']:r for r in env['weekoff_incentives']('2026-10',NS(query=lambda model:Query() if model is env['M'].EMSWeekoffIncentive else NS(filter=lambda *args:NS(all=lambda:[]))),NS())}
        self.assertEqual(rows[1]['incentive'],264300)
        self.assertEqual(rows[1]['source'],'monthly')
        self.assertEqual(rows[2]['incentive'],4500)
        self.assertEqual(rows[3]['incentive'],577123)
        self.assertEqual(source.incentive,999)
if __name__=='__main__':unittest.main()
