"""Format EMS report snapshots as Excel; never read or write ERP records."""
from io import BytesIO
from decimal import Decimal
from textwrap import wrap

IDS_HEADERS = ['Employee ID', 'Employee Name', 'Branch', 'Category', 'Absent',
    'No. of Days', 'Working Days', 'Expected Basic', 'Actual Basic', 'Other Allowances',
    'Actual VDA', 'Actual Pay (EPF)', 'Actual OA', 'Total Earning', 'Bonus Payable',
    'Actual Gross Earning', 'EPF Employee Contribution', 'ESIC Employee Contribution',
    'Staff Advance & Deduction', 'Total Deductions', 'Net Amount', 'Account No.', 'IFSC Code']
WEEKOFF_HEADERS = ['Employee ID', 'Employee Name', 'Branch', 'Category', 'Total W/O',
    'W/O Availed', 'W/O Credit', 'Gross Salary', 'W/O Credit Pay', 'Incentive', 'Amount Payable']

TOTAL_SALARY_HEADERS = ['Emp ID', 'Emp Name', 'Absent', 'Working Days',
    'Weekoff Credit', 'NET AMOUNT', 'W/O & INCENTIVE', 'Total Salary']

def total_salary_rows(ids_rows, weekoff_rows):
    result = []
    for ids, weekoff in zip(ids_rows, weekoff_rows):
        net, payable = ids[20], weekoff[10]
        total = None if net is None or payable is None else float(Decimal(str(net)) + Decimal(str(payable)))
        result.append([ids[0], ids[1], ids[4], ids[6], weekoff[6], net, payable, total])
    return result


def build_salary_workbook(month, ids_rows, weekoff_rows, provisional=False):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    grid = Side(style='thin', color='A9BBC5')
    table_border = Border(left=grid, right=grid, top=grid, bottom=grid)
    workbook = Workbook()
    workbook.remove(workbook.active)
    total_rows = total_salary_rows(ids_rows, weekoff_rows)
    category_rows = {
        category: [total for ids, total in zip(ids_rows, total_rows)
                   if str(ids[3] or '').strip().casefold() == category.casefold()]
        for category in ('Contract', 'Regular')
    }
    for name, title, headers, rows, money_columns in (
        ('IDS', 'IDS - Phase 1 Salary', IDS_HEADERS, ids_rows, range(8, 22)),
        ('W-O & Incentive', 'W/O & Incentive - Phase 2', WEEKOFF_HEADERS, weekoff_rows, range(8, 12)),
        ('Total Salary', 'Total Salary', TOTAL_SALARY_HEADERS, total_rows, range(6, 9)),
        ('Contract', 'Contract - Total Salary', TOTAL_SALARY_HEADERS, category_rows['Contract'], range(6, 9)),
        ('Regular', 'Regular - Total Salary', TOTAL_SALARY_HEADERS, category_rows['Regular'], range(6, 9)),
    ):
        is_total_salary = name in ('Total Salary', 'Contract', 'Regular')
        if not is_total_salary:
            # Branch is part of the EMS snapshot, but omitted from downloads.
            headers = headers[:2] + headers[3:]
            rows = [values[:2] + values[3:] for values in rows]
            money_columns = range(money_columns.start - 1, money_columns.stop - 1)
        sheet = workbook.create_sheet(name)
        sheet.append([f'Initiative Data Systems Pvt. Ltd. | {title}'])
        sheet.append([f'Salary month: {month}'])
        sheet.append(headers)
        for row_number in (1, 2):
            sheet.merge_cells(start_row=row_number, start_column=1,
                              end_row=row_number, end_column=len(headers))
        for values in rows:
            sheet.append(values)
        last_data = sheet.max_row
        totals = ['Total'] + [None] * (len(headers) - 1)
        for column in money_columns:
            totals[column - 1] = round(sum(values[column - 1] or 0 for values in rows), 2)
        sheet.append(totals)
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    # Names, IDs and account numbers must remain literal text.
                    cell.data_type = 's'
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = table_border
                if cell.row >= 4 and cell.column in money_columns:
                    cell.number_format = '#,##0.00;[Red](#,##0.00);"-"'
                if cell.row in (1, 3, sheet.max_row):
                    cell.font = Font(bold=True, color='FFFFFF' if cell.row == 3 else '153349')
                    cell.fill = PatternFill('solid', fgColor='19485A' if cell.row == 3 else 'EAF3F5')
                if cell.row == 3:
                    cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')
        header_lines = 1
        for column, header in enumerate(headers, 1):
            # Fit data (including formatted totals), rather than the full header sentence.
            values = [sheet.cell(row, column).value for row in range(4, sheet.max_row + 1)]
            def display(value):
                if value is None:
                    return ''
                if column in money_columns and isinstance(value, (int, float)):
                    return f'{value:,.2f}'
                return str(value)
            data_width = max((len(display(value)) for value in values), default=0)
            longest_word = max(map(len, header.split()), default=0)
            width = min(38, max(10, data_width + 3, longest_word + 3))
            sheet.column_dimensions[get_column_letter(column)].width = width
            lines = wrap(header, width=max(7, int(width) - 3),
                         break_long_words=False, break_on_hyphens=False)
            sheet.cell(3, column).value = '\n'.join(lines)
            header_lines = max(header_lines, len(lines))
            for row in range(4, sheet.max_row + 1):
                sheet.cell(row, column).alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        sheet.row_dimensions[3].height = max(36, header_lines * 16 + 12)
        sheet.freeze_panes = 'C4' if is_total_salary else 'D4'
        sheet.auto_filter.ref = f'A3:{get_column_letter(len(headers))}{last_data}'
        sheet.sheet_view.showGridLines = False
        sheet.print_title_rows = '1:3'
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = 'landscape'
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
