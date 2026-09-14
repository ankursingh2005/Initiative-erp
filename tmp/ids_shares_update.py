from pathlib import Path
p=Path('main.py'); s=p.read_text(encoding='utf-8')
s=s.replace('fund_sheet.merge_cells("A1:F1")','fund_sheet.merge_cells("A1:G1")').replace('fund_sheet.merge_cells("A3:F3")','fund_sheet.merge_cells("A3:G3")')
s=s.replace('fund_sheet.append(["IDS Fund share", .30])','fund_sheet.append(["IDS Fund shares: MOB 30%; COM / HA 20%; DC / HE / ACC COM / ACC 25%."])')
s=s.replace('Total incentive sums category incentives; total IDS Fund is 30% of that total. Rounded detail may differ by paise.','Outlet and grand totals sum rounded category IDS Fund amounts. Missing rates remain Pending.')
s=s.replace('"Total Incentive", "IDS Fund (30%)"]','"Total Incentive", "IDS Fund Share", "IDS Fund"]')
s=s.replace('        fund_sheet.cell(fund_row, 6, f\'=IF(ISNUMBER(E{fund_row}),ROUND(E{fund_row}*$B$2,2),"Pending")\')', '''        fund_sheet.cell(fund_row, 6, "Pending" if record["fund_rate"] is None else record["fund_rate"] / 100)
        fund_sheet.cell(fund_row, 6).number_format = "0%"
        fund_sheet.cell(fund_row, 7, f'=IF(AND(ISNUMBER(E{fund_row}),ISNUMBER(F{fund_row})),ROUND(E{fund_row}*F{fund_row},2),"Pending")')''')
s=s.replace('    for col in (5, 6):\n        letter = get_column_letter(col)','    for col in (5, 7):\n        letter = get_column_letter(col)')
s=s.replace('    fund_sheet.cell(fund_total_row, 6, f\'=IF(ISNUMBER(E{fund_total_row}),ROUND(E{fund_total_row}*$B$2,2),"Pending")\')\n','')
s=s.replace('cell.column in (3, 5, 6):','cell.column in (3, 5, 7):').replace('zip("ABCDEF", (20, 22, 22, 20, 22, 22))','zip("ABCDEFG", (20, 22, 22, 20, 22, 20, 22))')
marker='    output = BytesIO()\n    book.save(output)\n    filename = f"Outlet_Incentive_Report_'
pos=s.index(marker)
addition='''    outlet_fund = book.create_sheet("IDS Fund Outlet Summary")
    outlet_fund.append(["TOTAL IDS FUND BY OUTLET"])
    outlet_fund.merge_cells("A1:B1")
    outlet_fund.append(["Outlet", "Total IDS Fund"])
    for summary_row, record in enumerate(fund_report["summary"], 3):
        outlet_fund.cell(summary_row, 1, record["outlet"])
        refs = [f"'IDS Fund'!G{i}" for i, detail in enumerate(fund_report["rows"], 5) if detail["outlet"] == record["outlet"]]
        arguments = ",".join(refs)
        outlet_fund.cell(summary_row, 2, f'=IF(COUNT({arguments})={len(refs)},SUM({arguments}),"Pending")')
    summary_total = 3 + len(fund_report["summary"])
    outlet_fund.cell(summary_total, 1, "GRAND TOTAL")
    outlet_fund.cell(summary_total, 2, f'=IF(COUNT(B3:B{summary_total-1})=ROWS(B3:B{summary_total-1}),SUM(B3:B{summary_total-1}),"Pending")')
    outlet_fund.column_dimensions["A"].width = 28
    outlet_fund.column_dimensions["B"].width = 24
    outlet_fund.freeze_panes = "B3"
    outlet_fund.sheet_view.showGridLines = False
    outlet_fund["A1"].font = Font(size=15, bold=True)
    for cells in outlet_fund.iter_rows(min_row=2, max_row=summary_total):
        for cell in cells:
            cell.alignment = Alignment(horizontal="left" if cell.column == 1 else "right")
            cell.border = Border(bottom=thin)
            if cell.column == 2 and cell.row > 2:
                cell.number_format = '#,##0.00'
            if cell.row == 2:
                cell.fill = PatternFill("solid", fgColor=navy)
                cell.font = Font(color=white, bold=True)
            elif cell.row == summary_total:
                cell.fill = PatternFill("solid", fgColor=pale)
                cell.font = Font(bold=True)

'''
s=s[:pos]+addition+s[pos:];p.write_text(s,encoding='utf-8')
p=Path('static/incentive.html');s=p.read_text(encoding='utf-8')
s=s.replace('IDS Fund = that incentive × 30%.','IDS Fund = that incentive × category share (MOB 30%; COM / HA 20%; DC / HE / ACC COM / ACC 25%).')
s=s.replace('Outlet and grand IDS Fund totals apply 30% to their total incentive, so rounded detail may differ by paise.','Outlet and grand IDS Fund totals sum the rounded category fund amounts.')
s=s.replace('<col style="width:14%"><col style="width:14%"><col style="width:20%"><col style="width:14%"><col style="width:19%"><col style="width:19%">','<col style="width:13%"><col style="width:12%"><col style="width:18%"><col style="width:13%"><col style="width:17%"><col style="width:12%"><col style="width:15%">')
s=s.replace('<th scope="col">IDS Fund (30%)</th>','<th scope="col">Fund Share</th><th scope="col">IDS Fund</th>')
s=s.replace('</main>','''  <section class="card table-card" id="idsOutletReport" hidden>
    <div class="table-head"><div><h3>Total IDS Fund by Outlet</h3><div class="category-legend">Sum of category IDS Fund amounts for each outlet. Included as a separate sheet in Download Report.</div></div></div>
    <div class="scroll"><table style="table-layout:fixed"><thead><tr><th scope="col">Outlet</th><th scope="col" style="text-align:right">Total IDS Fund</th></tr></thead><tbody id="idsOutletRows"></tbody></table></div>
  </section>
</main>''')
s=s.replace("    document.getElementById('idsFundReport').hidden=true;","    document.getElementById('idsFundReport').hidden=true;\n    document.getElementById('idsOutletReport').hidden=true;\n    document.getElementById('idsOutletRows').innerHTML='';")
s=s.replace('    if(report?.version!==2)',"    document.getElementById('idsOutletReport').hidden=true;\n    document.getElementById('idsOutletRows').innerHTML='';\n    if(report?.version!==3)").replace('colspan="6" class="empty">Click Calculate','colspan="7" class="empty">Click Calculate')
s=s.replace('<td class="num">${amount(r.ids_fund)}</td>', '<td class="num">${r.isTotal?\'\':r.fund_rate==null?\'Pending\':r.fund_rate+\'%\'}</td><td class="num">${amount(r.ids_fund)}</td>')
anchor="  }\n  function renderExactIncentive(rows){"
s=s.replace(anchor,'''    document.getElementById('idsOutletRows').innerHTML=[...report.summary,{outlet:'GRAND TOTAL',...report.totals}].map((r,i)=>`<tr${i===report.summary.length?' style="font-weight:700;background:#d9eaf7"':''}><td>${escapeHtml(r.outlet)}</td><td class="num">${amount(r.ids_fund)}</td></tr>`).join('');
    document.getElementById('idsOutletReport').hidden=false;
  }
  function renderExactIncentive(rows){''')
p.write_text(s,encoding='utf-8')
