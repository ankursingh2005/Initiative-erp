from pathlib import Path
p = Path('main.py')
s = p.read_text(encoding='utf-8')
start = s.index('    fund_sheet = book.create_sheet("IDS Fund")')
end = s.index('    output = BytesIO()', start)
s = s[:start] + '''    fund_report = build_ids_fund_report(calculated_detail)
    fund_sheet = book.create_sheet("IDS Fund")
    fund_sheet.append(["IDS FUND BY OUTLET AND CATEGORY"])
    fund_sheet.merge_cells("A1:F1")
    fund_sheet.append(["IDS Fund share", .30])
    fund_sheet["B2"].number_format = "0%"
    fund_sheet.append(["Category incentive and fund rounded to paise; totals sum category amounts. Missing rates remain Pending."])
    fund_sheet.merge_cells("A3:F3")
    fund_sheet.append(["Outlet", "Category", "Total Sales", "Incentive Rate", "Total Incentive", "IDS Fund (30%)"])
    for fund_row, record in enumerate(fund_report["rows"], 5):
        for col, value in enumerate([record["outlet"], record["category"], record["total_sales"],
                                     "Pending" if record["incentive_rate"] is None else record["incentive_rate"] / 100], 1):
            fund_sheet.cell(fund_row, col, value)
        fund_sheet.cell(fund_row, 4).number_format = "0.000%"
        fund_sheet.cell(fund_row, 5, f'=IF(ISNUMBER(D{fund_row}),ROUND(C{fund_row}*D{fund_row},2),"Pending")')
        fund_sheet.cell(fund_row, 6, f'=IF(ISNUMBER(E{fund_row}),ROUND(E{fund_row}*$B$2,2),"Pending")')
    fund_total_row = 5 + len(fund_report["rows"])
    fund_sheet.cell(fund_total_row, 1, "GRAND TOTAL")
    fund_sheet.cell(fund_total_row, 3, f"=SUM(C5:C{fund_total_row-1})")
    for col in (5, 6):
        letter = get_column_letter(col)
        fund_sheet.cell(fund_total_row, col, f'=IF(COUNT({letter}5:{letter}{fund_total_row-1})=ROWS({letter}5:{letter}{fund_total_row-1}),SUM({letter}5:{letter}{fund_total_row-1}),"Pending")')
    for row in fund_sheet.iter_rows(min_row=4, max_row=fund_total_row):
        for cell in row:
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(horizontal="left" if cell.column <= 2 else "right")
            if cell.row > 4 and cell.column in (3, 5, 6):
                cell.number_format = '#,##0.00'
            if cell.row == 4:
                cell.fill = PatternFill("solid", fgColor=navy)
                cell.font = Font(color=white, bold=True)
            elif cell.row == fund_total_row:
                cell.fill = PatternFill("solid", fgColor=pale)
                cell.font = Font(bold=True)
    fund_sheet["A1"].font = Font(size=15, bold=True)
    fund_sheet.freeze_panes = "C5"
    fund_sheet.sheet_view.showGridLines = False
    for letter, width in zip("ABCDEF", (20, 22, 22, 20, 22, 22)):
        fund_sheet.column_dimensions[letter].width = width

''' + s[end:]
p.write_text(s, encoding='utf-8')
