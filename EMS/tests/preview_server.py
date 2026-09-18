"""Disposable browser-test server. Never writes to the real EMS database."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn


if __name__ == '__main__':
    with TemporaryDirectory(prefix='ems-preview-') as directory:
        os.environ['EMS_DATABASE'] = str(Path(directory) / 'preview.sqlite3')
        from app import main
        with main.db() as conn:
            for name, email, role, status, department in [
                ('Ananya Mehra', 'admin@example.test', 'admin', 'active', 'People Operations'),
                ('Aarav Sharma', 'employee@example.test', 'employee', 'active', 'Sales'),
                ('Meera Kapoor', 'pending@example.test', 'employee', 'pending', 'Operations'),
            ]:
                conn.execute('INSERT INTO users(name,email,password_hash,role,status,department,designation,outlet,joining_date,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (name, email, main.password_hash('PreviewOnly123'), role, status, department,
                     'People Manager' if role == 'admin' else 'Executive', 'Head Office', '2026-09-01', main.now()))
        uvicorn.run(main.app, host='127.0.0.1', port=8011)
