import unittest
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
import models


class AgeingStockWorkbookTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def make_sheet(self, workbook, title, material_centre, closing_qty):
        sheet = workbook.create_sheet(title)
        sheet['A4'] = f'Material Centre : {material_centre}'
        sheet.append([])
        sheet.append(['Item Details', 'Closing Qty', 'Unit', '0-60 Days', '61-90 Days', '91-150 Days', '151-180 Days', '181-365 Days', '>= 366 Days'])
        sheet.append(['Sony LED TV', closing_qty, 'Nos.', closing_qty, 0, 0, 0, 0, 0])
        return sheet

    def test_all_data_copied_to_branch_named_sheets_is_not_counted_as_branch_stock(self):
        workbook = Workbook()
        all_data = workbook.active
        all_data.title = 'ALL'
        all_data['A4'] = 'Material Centre : --All--'
        all_data.append([])
        all_data.append(['Item Details', 'Closing Qty', 'Unit', '0-60 Days', '61-90 Days', '91-150 Days', '151-180 Days', '181-365 Days', '>= 366 Days'])
        all_data.append(['Sony LED TV', 10, 'Nos.', 10, 0, 0, 0, 0, 0])

        self.make_sheet(workbook, 'ALM', '--All--', 10)
        self.make_sheet(workbook, 'HZT', '--All--', 10)
        for code, quantity in [('ASH', 1), ('GNG', 2), ('VKN', 3), ('MWH', 4)]:
            self.make_sheet(workbook, code, code, quantity)

        output = BytesIO()
        workbook.save(output)
        rows, locations, _ = main.parse_ageing_stock_workbook(output.getvalue(), self.db)

        self.assertEqual(len(rows), 1)
        self.assertEqual(set(locations), {'ASH', 'GNG', 'VKN', 'MWH'})
        self.assertEqual(rows[0]['qty_alm'], 0)
        self.assertEqual(rows[0]['qty_hzt'], 0)
        self.assertEqual(
            [rows[0][field] for field in ('qty_ash', 'qty_gng', 'qty_vkn', 'qty_mwh')],
            [1, 2, 3, 4],
        )


    def test_rbl_sheet_quantities_and_age_buckets_are_imported(self):
        workbook = Workbook()
        workbook.remove(workbook.active)
        self.make_sheet(workbook, 'All Data', '--All--', 10)
        self.make_sheet(workbook, 'RBL', 'RBL', 4)
        output = BytesIO()
        workbook.save(output)

        rows, locations, _ = main.parse_ageing_stock_workbook(output.getvalue(), self.db)

        self.assertEqual(locations, ['RBL'])
        self.assertEqual(rows[0]['qty_rbl'], 4)
        self.assertIn('RBL', rows[0]['locations_present'])
        buckets = main.json.loads(rows[0]['location_age_buckets_json'])
        self.assertEqual(buckets['qty_rbl']['age_0_60'], 4)
        item = models.AgeingStockItem(**rows[0])
        self.db.add(item)
        self.db.commit()
        self.assertEqual(self.db.query(models.AgeingStockItem).one().qty_rbl, 4)

    def test_report_quantities_only_include_selected_location_ageing(self):
        item = dict(closing_qty=17, age_366_plus=17, qty_alm=3, qty_hzt=2,
                    location_age_buckets_json=main.json.dumps({
                        'qty_alm': {'age_366_plus': 3, 'age_0_60': 1},
                        'qty_hzt': {'age_366_plus': 2},
                    }))
        scoped = main.scope_ageing_item_to_locations(item, ['qty_alm', 'qty_hzt'])
        self.assertEqual(scoped['closing_qty'], 6)
        self.assertEqual(scoped['age_366_plus'], 5)
        self.assertEqual(main.location_qty_for_durations(scoped, 'qty_alm', ['age_366_plus']), 3)
        self.assertEqual(main.scope_ageing_item_to_locations(item, ['qty_hzt'])['closing_qty'], 2)
        self.assertEqual(main.scope_ageing_item_to_locations(item, ['qty_rbl'])['closing_qty'], 0)
        self.assertEqual(main.scope_ageing_item_to_locations({'qty_alm': 9}, ['qty_alm'])['closing_qty'], 0)

if __name__ == '__main__':
    unittest.main()