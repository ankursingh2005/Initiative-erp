"""Disposable full ERP integration server for EMS browser checks."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn

if __name__ == '__main__':
    with TemporaryDirectory(prefix='erp-ems-preview-') as directory:
        os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(directory) / 'erp.sqlite3').as_posix()
        os.environ['SECRET_KEY'] = 'isolated-ems-browser-tests-only'
        import main
        import models
        import auth
        with main.SessionLocal() as db:
            for email, name, role in [('admin@ems.test', 'HR Administrator', 'Admin'), ('employee@ems.test', 'Aarav Sharma', 'Employee')]:
                db.add(models.User(username=email, email=email, full_name=name,
                                   password_hash=auth.hash_password('PreviewOnly123'), role=role, status='Active'))
            db.commit()
        from fastapi import FastAPI
        host = FastAPI()
        host.mount('/erp', main.app)
        uvicorn.run(host, host='127.0.0.1', port=8012)
        main.engine.dispose()
