import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'tests')
import test_analytics as test
import main
import analytics_engine as calc
from pathlib import Path
from collections import Counter
from decimal import Decimal
from types import SimpleNamespace
import json

path = Path('C:/Users/Ankur/Desktop/IDSPL_Bill-wiseProfitability 24-25.xlsx')
parsed = main.parse_analytics_file(path.name, path.read_bytes())
staged = main.build_staged_rows(calc.normalize_upload(parsed))
rows, quality = calc.project([SimpleNamespace(**r) for r in staged], main.detect_division_code, gst=False)
decisions = calc.decision_stats(rows)
for field in ('sales_amt', 'cost_amt'):
    before = sum((Decimal(str(r[field])) for r in parsed), Decimal(0))
    after = sum((Decimal(str(r[field])) for r in staged), Decimal(0))
    assert abs(before-after) < Decimal('.01'), (field, before, after)
print(json.dumps({'parsed':len(parsed), 'staged':len(staged), 'quality':quality,
    'outlets':dict(Counter(r['store'] for r in parsed)),
    'categories':dict(Counter(r.division for r in rows)),
    'unclassified_examples':list(dict.fromkeys(r['item'] for r in staged if r['division']=='UNCATEGORIZED'))[:35],
    'summary':{k:v for k,v in decisions.items() if k not in ('matrix','loss_lines','actions')},
    'amounts_preserved_by_merge':True}, indent=2))
test.tearDownModule()
