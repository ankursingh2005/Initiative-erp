import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'tests')
import test_analytics as test
import main
from types import SimpleNamespace
from io import BytesIO
from fastapi import UploadFile
import uvicorn

user = SimpleNamespace(id=1, username='preview', role='Admin', status='Active')
main.app.dependency_overrides[main.auth.get_current_user] = lambda: user
data = ('Date,Item,Division,Store,Vch No,Sales Amt,Cost Amt\n'
        '2026-09-01,Demo Refrigerator,HA,ALM,ALM/1/26-27,10000,8500\n'
        '2026-09-01,Demo Mobile,MH,HZT,HZT/1/26-27,20000,18500\n'
        '2026-09-02,Demo Television,HE,ALM,ALM/2/26-27,12000,13000\n'
        '2026-09-02,Unclear XYZ,,ALM,ALM/3/26-27,3000,2500\n')
with main.SessionLocal() as db:
    main.upload_analytics_file(file=UploadFile(filename='synthetic-preview.csv', file=BytesIO(data.encode())),
                               amount_basis='exclusive', current_user=user, db=db)
uvicorn.run(main.app, host='127.0.0.1', port=8769)
