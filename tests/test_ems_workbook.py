"""Excel formatting checks use synthetic report data only."""
import unittest
from io import BytesIO
from openpyxl import load_workbook
from ems_workbook import build_salary_workbook, IDS_HEADERS


class SalaryWorkbookTests(unittest.TestCase):
    def test_three_ordered_sheets_preserve_money_accounts_and_literal_names(self):
        ids = ['EMP001', '=Literal employee', 'Branch', 'Regular', 2, 30, 28,
               *([100.25] * 14), '000123456789', 'SBIN0001234']
        self.assertEqual(len(ids), len(IDS_HEADERS))
        phase2 = ['EMP001', '=Literal employee', 'Branch', 'Regular', 4, 2, 2,
                  100.25, 6.68, 500, 506.68]
        data = build_salary_workbook('2026-09', [ids], [phase2], True)
        self.assertTrue(data.startswith(b'PK'))
        workbook = load_workbook(BytesIO(data))
        self.assertEqual(workbook.sheetnames, ['IDS', 'W-O & Incentive', 'Total Salary'])
        first, second, third = workbook.worksheets
        self.assertEqual(first['V5'].value, '000123456789')
        self.assertEqual(first['V5'].data_type, 's')
        self.assertEqual(first['B5'].data_type, 's')
        self.assertEqual(first['H5'].value, 100.25)
        self.assertEqual(first['U6'].value, first['U5'].value)
        self.assertEqual(second['K5'].value, 506.68)
        self.assertEqual(second['K6'].value, 506.68)
        self.assertEqual([cell.value for cell in third[5]],
                         ['EMP001', '=Literal employee', 2, 28, 2, 100.25, 506.68, 606.93])
        self.assertEqual(third['B5'].data_type, 's')
        self.assertEqual(third['H6'].value, 606.93)
        self.assertEqual(third['F5'].number_format, first['U5'].number_format)
        self.assertEqual(third.freeze_panes, 'C5')
        self.assertEqual(third.auto_filter.ref, 'A4:H5')
        self.assertIn('Provisional', first['A3'].value)
        self.assertEqual(first.freeze_panes, 'E5')
        self.assertEqual(first.auto_filter.ref, 'A4:W5')

    def test_total_salary_preserves_missing_setup_and_decimal_accuracy(self):
        from ems_workbook import total_salary_rows
        ids = ['EMP001', 'Employee', '', '', 0, 30, 30, *([0] * 14), '', '']
        weekoff = ['EMP001', 'Employee', '', '', 4, 3, 1, 0, 0, 0, 0.2]
        ids[20] = 0.1
        self.assertEqual(total_salary_rows([ids], [weekoff])[0][-1], 0.3)
        ids[20] = None
        self.assertIsNone(total_salary_rows([ids], [weekoff])[0][-1])


if __name__ == '__main__':
    unittest.main()
