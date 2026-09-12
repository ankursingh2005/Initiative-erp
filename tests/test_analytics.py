"""Run with python -m unittest discover -s tests -p test_analytics.py.

The app initializes its DB on import, so select an isolated temporary SQLite
database BEFORE importing it. No application database or real users are used.
"""
import csv
from datetime import date
from io import StringIO
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_temp = tempfile.TemporaryDirectory(prefix="analytics-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_temp.name)/"test.db").as_posix()
os.environ["SECRET_KEY"] = "analytics-test-secret-not-for-production"

import analytics_engine as calc
import main
import models
from fastapi.testclient import TestClient


def tearDownModule():
    main.engine.dispose()
    _temp.cleanup()


def row(**overrides):
    values = dict(sale_date=date(2026, 9, 1), item="Air conditioner AC", division="HA", brand="Demo",
                  store="ALM", vch_no="INV-1", sales_amt=1000, cost_amt=800, profit_loss=999, qty=1)
    values.update(overrides)
    return SimpleNamespace(**values)


class CalculationTests(unittest.TestCase):
    def test_gst_recalculates_profit_without_mutating_source(self):
        source = row()
        first, _ = calc.project([source])
        second, _ = calc.project([source])
        self.assertEqual((first[0].sales_amt, first[0].cost_amt, first[0].profit_loss), (1180, 944, 236))
        self.assertEqual(first[0].sales_amt, second[0].sales_amt)
        self.assertEqual(source.sales_amt, 1000)

    def test_inclusive_source_not_taxed_twice(self):
        source = vars(row(sales_amt=1180, cost_amt=944))
        calc.normalize_upload([source], "inclusive")
        result, _ = calc.project([SimpleNamespace(**source)])
        self.assertEqual((result[0].sales_amt, result[0].cost_amt), (1180,944))

    def test_rounding_inclusive_paise_and_returns(self):
        source = vars(row(sales_amt=-1180.01, cost_amt=-944.02))
        calc.normalize_upload([source], "inclusive")
        result, _ = calc.project([SimpleNamespace(**source)])
        self.assertEqual((result[0].sales_amt,result[0].cost_amt,result[0].profit_loss),(-1180.01,-944.02,-235.99))

    def test_six_categories_accessory_priority_and_uncertainty(self):
        self.assertEqual(calc.classify("Samsung TV remote", detector=main.detect_division_code),"ACC")
        self.assertEqual(calc.classify("Monthly payouts", detector=main.detect_division_code),"PAYOUT")
        self.assertEqual(calc.classify("Apple MacBook", detector=main.detect_division_code),"IT")
        self.assertEqual(calc.classify("Samsung XYZ", detector=main.detect_division_code),"UNCATEGORIZED")
        self.assertEqual(calc.classify("OnePlus mobile", detector=main.detect_division_code),"MH")

    def test_summary_and_unknown_are_auditable(self):
        data=[row(),row(item="Grand Total"),row(item="Unclear XYZ",division=None)]
        included,q=calc.project(data)
        self.assertEqual(len(included),1)
        self.assertEqual(q,{"included":1,"excluded":1,"review":1})
        self.assertEqual(len(calc.project(data,view="all")[0]),3)

    def test_manual_review_is_not_overridden(self):
        included,quality=calc.project([row(item="Laptop",division="UNCATEGORIZED")],main.detect_division_code)
        self.assertEqual(included,[])
        self.assertEqual(quality,{'review':1})

    def test_ac_voucher_pair_never_merges_across_stores(self):
        data=[vars(row(item="AC INDOOR Demo",store="ALM")),vars(row(item="AC OUTDOOR Demo",store="HZT"))]
        self.assertEqual(len(main.build_staged_rows(data)),2)

    def test_nonfinite_excluded_and_negative_sale_retained(self):
        result,q=calc.project([row(sales_amt=float('nan')),row(sales_amt=-100)])
        self.assertEqual(q['excluded'],1)
        self.assertEqual(result[0].sales_amt,-118)

    def test_calendar_average_and_stddev(self):
        data,_=calc.project([row(),row(sale_date=date(2026,9,8),sales_amt=2000)])
        stats=calc.advanced_stats(data)
        self.assertEqual(stats['daily_trend'][1]['rolling_7_sales'],337.14)
        self.assertEqual(stats['distribution']['median_sale'],1770)
        self.assertEqual(stats['distribution']['sale_stddev'],590)


class AnalyticsApiTests(unittest.TestCase):
    def setUp(self):
        self.user=SimpleNamespace(id=1,username="analytics-test",role="Admin",status="Active")
        main.app.dependency_overrides[main.auth.get_current_user]=lambda:self.user
        self.client=TestClient(main.app)
        with main.SessionLocal() as db:
            db.query(models.AnalyticsSalesRow).delete()
            db.query(models.AnalyticsUpload).delete()
            db.commit()

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()

    def upload(self, text=None, basis="exclusive"):
        text=text or "Date,Item,Division,Store,Sales Amt,Cost Amt,Qty\n2026-09-01,AC,HA,ALM,1000,800,1\n2026-09-02,Laptop,IT,HZT,2000,1500,1\n2026-09-02,Grand Total,HA,ALM,3000,2300,2\n2026-09-02,Unknown XYZ,,ALM,10,5,1\n"
        response=self.client.post('/api/analytics/upload',files={'file':('test.csv',text,'text/csv')},data={'amount_basis':basis})
        self.assertEqual(response.status_code,200,response.text)
        return response

    def test_meta_store_filter_and_matching_items(self):
        self.upload()
        meta=self.client.get('/api/analytics/meta').json()
        self.assertEqual(meta['categories'],list(calc.CATEGORIES))
        self.assertEqual(meta['stores'],['ALM','HZT'])
        data=self.client.get('/api/analytics/dashboard?store=ALM').json()
        self.assertEqual(data['kpis']['total_sales'],1180)
        self.assertEqual(data['kpis']['total_profit'],236)
        self.assertEqual(data['quality'],{'included':1,'excluded':1,'review':1})
        items=self.client.get('/api/analytics/items?store=ALM').json()
        self.assertEqual(items['total'],1)
        self.assertEqual(items['items'][0]['sales_amt'],data['kpis']['total_sales'])

    def test_category_date_and_search_filters(self):
        self.upload()
        self.assertEqual(self.client.get('/api/analytics/dashboard?division=COMPUTER').json()['kpis']['total_sales'],2360)
        self.assertEqual(self.client.get('/api/analytics/dashboard?search=Laptop&start_date=2026-09-02').json()['kpis']['transactions'],1)
        self.assertEqual(self.client.get('/api/analytics/dashboard?start_date=2026-10-01&end_date=2026-09-01').status_code,400)
        self.assertFalse(self.client.get('/api/analytics/dashboard?store=missing').json()['has_data'])

    def test_pagination_and_csv_all_rows(self):
        text='Date,Item,Division,Store,Sales Amt,Cost Amt\n'+''.join(f'2026-09-01,AC {i},HA,ALM,1000,800\n' for i in range(105))
        self.upload(text)
        data=self.client.get('/api/analytics/items?page=2&page_size=100').json()
        self.assertEqual((data['total'],len(data['items'])),(105,5))
        response=self.client.get('/api/analytics/export')
        values=list(csv.DictReader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(values),105)
        self.assertEqual(sum(float(v['Sales incl GST']) for v in values),self.client.get('/api/analytics/dashboard').json()['kpis']['total_sales'])

    def test_review_view_and_safe_csv(self):
        self.upload('Date,Item,Division,Store,Sales Amt,Cost Amt\n2026-09-01,=DEMO(),HA,ALM,10,5\n2026-09-01,Mystery,,ALM,10,5\n')
        self.assertEqual(self.client.get('/api/analytics/items?view=review').json()['total'],1)
        self.assertEqual(self.client.get('/api/analytics/items?view=all').json()['total'],2)
        self.assertIn("'=DEMO()",self.client.get('/api/analytics/export').text)
        self.assertEqual(self.client.get('/api/analytics/items?view=bad').status_code,422)

    def test_stage_inclusive_reassign_commit(self):
        text='Date,Item,Store,Sales Amt,Cost Amt\n2026-09-01,Mystery,ALM,1180,944\n'
        response=self.client.post('/api/analytics/stage',files={'file':('test.csv',text,'text/csv')},data={'amount_basis':'inclusive'})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json(); token=data['staging_token']
        self.assertEqual(data['rows'][0]['sales_amt'],1000)
        self.assertEqual(self.client.post(f'/api/analytics/stage/{token}/reassign',json={'row_ids':[0],'division':'bad'}).status_code,400)
        response=self.client.post(f'/api/analytics/stage/{token}/reassign',json={'row_ids':[0],'division':'Accessories'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post(f'/api/analytics/stage/{token}/commit').status_code,200)
        dashboard=self.client.get('/api/analytics/dashboard').json()
        self.assertEqual(dashboard['kpis']['total_sales'],1180)
        self.assertEqual(dashboard['division_breakdown'][0]['division'],'ACC')

    def test_invalid_source_basis_does_not_replace_existing_rows(self):
        self.upload()
        response=self.client.post('/api/analytics/upload',files={'file':('test.csv','Date,Item,Sales Amt\n2026-09-01,AC,1\n','text/csv')},data={'amount_basis':'invalid'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.get('/api/analytics/items?view=all').json()['total'],4)

    def test_failed_insert_keeps_previous_snapshot(self):
        self.upload()
        with patch('sqlalchemy.orm.Session.bulk_insert_mappings',side_effect=RuntimeError('test insert failure')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/analytics/upload',files={'file':('test.csv','Date,Item,Sales Amt\n2026-09-01,AC,1\n','text/csv')})
        self.assertEqual(self.client.get('/api/analytics/items?view=all').json()['total'],4)


if __name__ == '__main__':
    unittest.main()
