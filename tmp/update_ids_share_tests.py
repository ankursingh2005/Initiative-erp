from pathlib import Path
p=Path('tests/test_ids_fund.py');s=p.read_text()
import re
s=re.sub(r'ids_fund_amounts\(([-\d]+), \.125\)',r'ids_fund_amounts(\1, .125, 30)',s)
s=s.replace("self.assertEqual(report['totals']['ids_fund'],expected*300)","share = {'MOB':30,'COM':20,'DC':25,'HA':20,'HE':25,'ACC COM':25,'ACC':25}[category]\n                self.assertEqual(report['rows'][0]['fund_rate'],share)\n                self.assertEqual(report['totals']['ids_fund'],expected*10*share)")
s=s.replace("self.assertEqual(report['totals']['ids_fund'],225)","self.assertEqual(report['totals']['ids_fund'],187.5)",1)
s=s.replace("self.assertEqual(small['totals']['ids_fund'], .01)","self.assertEqual(small['totals']['ids_fund'], 0)")
s=s.replace("self.assertEqual(report['totals']['ids_fund'],225)","self.assertEqual(report['totals']['ids_fund'],175)")
s=s.replace("self.assertEqual(report['rows'][0]['ids_fund'],75)","self.assertEqual(report['rows'][0]['ids_fund'],50)")
s=s.replace("self.assertEqual(sheet['B2'].value,.3)","self.assertEqual(sheet['F5'].value,.2)")
s=s.replace("self.assertEqual(sheet['F5'].value,'=IF(ISNUMBER(E5),ROUND(E5*$B$2,2),\"Pending\")')", "self.assertEqual(sheet['G5'].value,'=IF(AND(ISNUMBER(E5),ISNUMBER(F5)),ROUND(E5*F5,2),\"Pending\")')")
s=s.replace("self.assertEqual(sheet['F7'].value,'=IF(ISNUMBER(E7),ROUND(E7*$B$2,2),\"Pending\")')", "self.assertEqual(sheet['G7'].value,'=IF(COUNT(G5:G6)=ROWS(G5:G6),SUM(G5:G6),\"Pending\")')\n                summary = book['IDS Fund Outlet Summary']\n                self.assertEqual(summary['A3'].value,'ALM')\n                self.assertIn(\"'IDS Fund'!G5\",summary['B3'].value)\n                self.assertEqual(summary['A5'].value,'GRAND TOTAL')")
p.write_text(s)
p=Path('tests/ids-fund.test.cjs');s=p.read_text().replace("idsFundRows:{innerHTML:''}","idsFundRows:{innerHTML:''},idsOutletReport:{hidden:true},idsOutletRows:{innerHTML:''}").replace('version:2','version:3').replace("category:'MOB',incentive_rate:.125","category:'MOB',fund_rate:30,incentive_rate:.125")
s += "\nassert.equal(elements.idsOutletReport.hidden,false);\nassert.match(elements.idsOutletRows.innerHTML,/37.50/);\nassert.match(elements.idsOutletRows.innerHTML,/GRAND TOTAL/);\n"
p.write_text(s)
