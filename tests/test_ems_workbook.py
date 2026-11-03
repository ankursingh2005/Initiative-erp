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
        self.assertEqual(first['U4'].value, '000123456789')
        self.assertEqual(first['U4'].data_type, 's')
        self.assertEqual(first['B4'].data_type, 's')
        self.assertEqual(first['G4'].value, 100.25)
        self.assertEqual(first['T5'].value, first['T4'].value)
        self.assertEqual(second['J4'].value, 506.68)
        self.assertEqual(second['J5'].value, 506.68)
        for sheet in (first, second):
            self.assertNotIn('Branch', [cell.value for cell in sheet[3]])
            self.assertNotIn('Branch', [cell.value for cell in sheet[4]])
            self.assertEqual(sheet['C4'].value, 'Regular')
        self.assertEqual(first.max_column, 22)
        self.assertEqual(second.max_column, 10)
        self.assertEqual(second.freeze_panes, 'D4')
        self.assertEqual(second.auto_filter.ref, 'A3:J4')
        self.assertEqual([cell.value for cell in third[4]],
                         ['EMP001', '=Literal employee', 2, 28, 2, 100.25, 506.68, 606.93])
        self.assertEqual(third['B4'].data_type, 's')
        self.assertEqual(third['H5'].value, 606.93)
        self.assertEqual(third['F4'].number_format, first['T4'].number_format)
        self.assertEqual(third.freeze_panes, 'C4')
        self.assertEqual(third.auto_filter.ref, 'A3:H4')
        self.assertEqual(third['D3'].value, 'Working\nDays')
        self.assertTrue(third['D3'].alignment.wrap_text)
        self.assertLess(third.column_dimensions['D'].width, third.column_dimensions['B'].width)
        self.assertGreaterEqual(third.row_dimensions[3].height, 44)
        for sheet in workbook.worksheets:
            self.assertEqual(sheet['A1'].alignment.horizontal, 'center')
            self.assertEqual(sheet['A2'].alignment.horizontal, 'center')
            self.assertIn('ID', sheet['A3'].value)
            self.assertEqual(sheet.print_title_rows, '$1:$3')
            for row in sheet.iter_rows(min_row=3):
                for cell in row:
                    self.assertEqual(cell.alignment.horizontal, 'center')
                    self.assertEqual(cell.alignment.vertical, 'center')
                    for side in ('left', 'right', 'top', 'bottom'):
                        self.assertEqual(getattr(cell.border, side).style, 'thin')
            self.assertFalse(any(isinstance(cell.value, str) and 'Provisional:' in cell.value
                                 for row in sheet for cell in row))
        self.assertEqual(first.freeze_panes, 'D4')
        self.assertEqual(first.auto_filter.ref, 'A3:V4')

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
