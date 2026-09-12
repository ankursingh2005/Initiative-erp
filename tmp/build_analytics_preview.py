import sys
from pathlib import Path
sys.path[:0] = ['.', 'tests', 'tmp/api-test-deps']
import json
import test_analytics as tests
from fastapi.testclient import TestClient
from datetime import date, timedelta

app = tests.main.app
app.dependency_overrides[tests.main.auth.get_current_user] = lambda: tests.SimpleNamespace(id=1,username='Preview',role='Admin',status='Active')
client = TestClient(app)
csv = ['Date,Item,Division,Brand,Store,Sales Amt,Cost Amt,Qty']
categories = [('HA','Air conditioner','Demo Cooling'),('HE','LED TV','Demo Vision'),('MH','Smartphone','Demo Mobile'),('IT','Laptop','Demo Computing'),('ACC','USB cable','Demo Accessories'),('PAYOUT','Partner payout','Demo Partner')]
for i in range(180):
    cat,item,brand=categories[i%6]
    sales = 500+(i%13)*1800
    cost = sales*(1.08 if i%17==0 else 0.72+(i%5)*0.035)
    csv.append(f'{date(2026,8,1)+timedelta(days=i//6)},{item} model {i%12},{cat},{brand},{["ALM","HZT","ASH"][i%3]},{sales},{cost},1')
csv += ['2026-08-30,Grand Total,HA,,ALM,900000,700000,180','2026-08-30,Unclear item,,,ALM,1000,800,1']
response=client.post('/api/analytics/upload',files={'file':('demo.csv','\n'.join(csv),'text/csv')})
assert response.status_code==200,response.text
fixtures={}
for endpoint in ['meta','dashboard','dashboard?store=ALM','dashboard?store=missing','items','items?page=2&page_size=100','items?view=all','items?view=review']:
    response=client.get('/api/analytics/'+endpoint)
    assert response.status_code==200,response.text
    fixtures[endpoint]=response.json()
Path('tmp/analytics-fixtures.json').write_text(json.dumps(fixtures),encoding='utf8')
client.close()
tests.tearDownModule()
