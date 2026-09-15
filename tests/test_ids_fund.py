import unittest
from unittest.mock import patch
from io import BytesIO
from types import SimpleNamespace
import test_analytics as isolated
from fastapi.testclient import TestClient
from openpyxl import load_workbook
main = isolated.main
tearDownModule = isolated.tearDownModule


class IdsFundTests(unittest.TestCase):
    def test_non_sales_screenshot_and_pending(self):
        summary = [dict(outlet=code, ids_fund=fund) for code, fund in
                   zip(['ALM', 'ASH', 'HZT', 'GNG', 'VKN'], [11479, 837, 7214, 2166, 1675])]
        report = main.build_non_sales_report(summary)
        self.assertEqual([r['values'] for r in report['rows']], [
            [4018, None, 1377, 1722, 1722], [293, None, 84, 126, 84],
            [2525, None, 866, 1082, 866], [758, None, 217, 325, 217],
            [586, None, 168, 251, 168], [None, 3739.36, None, None, None]])
        self.assertEqual(report['rows'][-1]['ids_fund'], 23371)
        self.assertEqual(report['totals'], [8180, 3739.36, 2712, 3506, 3057])
        self.assertEqual(main.build_non_sales_report(summary[:-1])['totals'], [None] * 5)
        summary[0]['ids_fund'] = None
        self.assertEqual(main.build_non_sales_report(summary)['totals'], [None] * 5)
        for row in summary:
            row['ids_fund'] = 0
        self.assertEqual(main.build_non_sales_report(summary)['totals'], [0] * 5)
        summary[0]['ids_fund'] = -10
        self.assertEqual(main.build_non_sales_report(summary)['rows'][0]['values'][0], -4)

    def test_rates_rounding_zero_and_returns(self):
        self.assertEqual(main.ids_fund_amounts(100000, .125, 30),
                         dict(total_sales=100000, total_incentive=125, ids_fund=37.5))
        self.assertEqual(main.ids_fund_amounts(0, .125, 30)['ids_fund'], 0)
        self.assertEqual(main.ids_fund_amounts(-100000, .125, 30)['ids_fund'], -37.5)
        self.assertEqual(main.ids_fund_amounts(4, .125, 30)['total_incentive'], .01)
        self.assertEqual(main.ids_fund_amounts(40, .125, 30)['ids_fund'], .02)

    def test_every_outlet_category_rate_and_missing_data(self):
        for outlet in ['Alambagh','Ashiyana','Gomti   Nagar','VKN','Hazratganj','HTZ']:
            for category in ['MOB','COM','HA','HE','DC','ACC','ACC COM']:
                expected = .125 if category=='MOB' else .25
                if category in ['ACC','ACC COM']:
                    expected = (.5 if category=='ACC' else .25) if outlet in ['Hazratganj','HTZ'] else 1
                report = main.build_ids_fund_report([dict(outlet=outlet,category=category,total_sales=100000)])
                self.assertEqual(report['rows'][0]['incentive_rate'],expected,(outlet,category))
                share = {'MOB':30,'COM':20,'DC':25,'HA':20,'HE':25,'ACC COM':25,'ACC':25}[category]
                self.assertEqual(report['rows'][0]['fund_rate'],share)
                self.assertEqual(report['totals']['ids_fund'],expected*10*share)
        for outlet,category in [('OTHER','ACC'),('ALM',None),('HZT','ACC UNB')]:
            report = main.build_ids_fund_report([dict(outlet=outlet,category=category,total_sales=100)])
            self.assertIsNone(report['totals']['ids_fund'])
            self.assertEqual(report['pending_rows'],1)

    def test_accessories_stay_separate_and_totals_sum_rounded_categories(self):
        report = main.build_ids_fund_report([
            dict(outlet='HTZ',category='ACC',total_sales=100000),
            dict(outlet='Hazratganj',category='ACC COM',total_sales=100000)])
        self.assertEqual(len(report['rows']),2)
        self.assertEqual(report['totals']['total_incentive'],750)
        self.assertEqual(report['totals']['ids_fund'],187.5)
        small = main.build_ids_fund_report([
            dict(outlet='ALM',category='MOB',total_sales=4),
            dict(outlet='ALM',category='COM',total_sales=2)])
        self.assertEqual(small['totals']['total_incentive'], .02)
        self.assertEqual(small['totals']['ids_fund'], 0)

    def test_report_and_export_use_sales_independent_of_other_rates(self):
        source = [dict(month='September 2026', outlet='ALM', category='HA', total_sales=100000),
                  dict(month='September 2026', outlet='HZT', category='HE', total_sales=200000)]
        main.app.dependency_overrides[main.auth.get_current_user] = lambda: SimpleNamespace(id=1, role='Admin', status='Active')
        try:
            with TestClient(main.app) as client, patch.object(main, 'parse_incentive_upload', return_value=source):
                def post(endpoint, rates):
                    return client.post(endpoint, files={'file':('sales.xlsx', b'test')}, data=rates)
                result = post('/api/incentive/calculate', {'profit_rate':7,'incentive_rate':2.5})
                self.assertEqual(result.status_code,200,result.text)
                report = result.json()['ids_fund_report']
                self.assertEqual(report['totals']['ids_fund'],175)
                self.assertEqual(report['rows'][0]['ids_fund'],50)
                changed = post('/api/incentive/calculate', {'profit_rate':10,'incentive_rate':5})
                self.assertEqual(changed.json()['ids_fund_report'],report)
                export = post('/api/incentive/export', {'profit_rate':7,'incentive_rate':2.5})
                self.assertEqual(export.status_code,200)
                book = load_workbook(BytesIO(export.content), data_only=False)
                sheet = book['IDS Fund']
                self.assertEqual(sheet['F5'].value,.2)
                self.assertEqual(sheet['D5'].value,.0025)
                self.assertEqual(sheet['E5'].value,'=IF(ISNUMBER(D5),ROUND(C5*D5,2),"Pending")')
                self.assertEqual(sheet['G5'].value,'=IF(AND(ISNUMBER(E5),ISNUMBER(F5)),ROUND(E5*F5,2),"Pending")')
                self.assertEqual(sheet['A7'].value,'GRAND TOTAL')
                self.assertEqual(sheet['C7'].value,'=SUM(C5:C6)')
                self.assertEqual(sheet['G7'].value,'=IF(COUNT(G5:G6)=ROWS(G5:G6),SUM(G5:G6),"Pending")')
                summary = book['IDS Fund Outlet Summary']
                self.assertEqual(summary['A3'].value,'ALM')
                self.assertIn("'IDS Fund'!G5",summary['B3'].value)
                self.assertEqual(summary['A5'].value,'GRAND TOTAL')
                staff = book['Non-sales Staff Incentive']
                self.assertEqual(staff['B2'].value, "='IDS Fund Outlet Summary'!B3")
                self.assertEqual(staff['B3'].value, 'Pending')
                self.assertEqual(staff['C2'].value, .35)
                self.assertEqual(staff['D7'].value, .16)
                self.assertEqual(staff['C11'].value, '=IF(ISNUMBER(B2),ROUND(B2*C2,0),"Pending")')
                self.assertEqual(staff['D16'].value, '=IF(ISNUMBER(B7),ROUND(B7*D7,2),"Pending")')
                self.assertEqual(staff['D18'].value, '=D16')
                self.assertIn('non_sales_report', report)
                book.close()
        finally:
            main.app.dependency_overrides.clear()


if __name__ == '__main__':
    unittest.main()
