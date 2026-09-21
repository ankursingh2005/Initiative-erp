"""Rename regression coverage using an isolated database, never real accounts."""
from datetime import date, datetime
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import test_analytics as isolated
import auth
import models
import schemas
from attendance_exports import router as exports_router
from openpyxl import load_workbook
from io import BytesIO

main = isolated.main
tearDownModule = isolated.tearDownModule


class UsernameHistoryTests(unittest.TestCase):
    def test_rename_preserves_history_for_admin_and_hr(self):
        for role in ('Admin', 'HR'):
            with self.subTest(role=role):
                engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
                models.Base.metadata.create_all(engine)
                with sessionmaker(bind=engine)() as db:
                    employee = models.User(username='Old name', email='employee@example.test',
                                           password_hash='unchanged', role='Employee', status='Active', weekoff_day='Wednesday')
                    actor = models.User(username='Manager', email='manager@example.test',
                                        password_hash='unused', role=role, status='Active')
                    db.add_all([employee, actor])
                    db.flush()
                    record = models.AttendanceRecord(user_id=employee.id,
                        attendance_date=date(2026, 9, 1), checkin_at=datetime(2026, 9, 1, 9),
                        checkout_at=datetime(2026, 9, 1, 18), checkin_selfie='saved-selfie')
                    db.add(record)
                    db.add(models.AttendanceLeave(user_id=employee.id, leave_date=date(2026, 9, 3), created_by=employee.id))
                    db.commit()
                    user_id = employee.id
                    original = {col.name: getattr(record, col.name) for col in record.__table__.columns}
                    app = FastAPI()
                    app.include_router(exports_router)
                    app.patch('/users/{user_id}/details', response_model=schemas.UserAdminOut)(main.update_user_details)
                    app.get('/attendance')(main.list_attendance)
                    app.get('/history/{user_id}')(main.attendance_user_history)
                    app.put('/api/me/weekoff')(main.update_my_weekoff)
                    app.get('/api/me', response_model=schemas.MyProfileOut)(main.get_my_profile)
                    app.dependency_overrides[main.get_db] = lambda: db
                    app.dependency_overrides[auth.get_current_user] = lambda: actor
                    with TestClient(app) as client:
                        response = client.patch(f'/users/{user_id}/details', json={
                            'username': 'New name', 'email': employee.email, 'weekoff_day': 'Wednesday'})
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['id'], user_id)
                        db.refresh(record)
                        self.assertEqual(original, {col.name: getattr(record, col.name) for col in record.__table__.columns})
                        self.assertEqual(db.query(models.User).count(), 2)
                        self.assertEqual(employee.password_hash, 'unchanged')
                        history_response = client.get(f'/history/{user_id}')
                        self.assertEqual(history_response.status_code, 200)
                        self.assertEqual(history_response.json()['username'], 'New name')
                        self.assertEqual([item['id'] for item in history_response.json()['history']], [record.id])
                        self.assertEqual(client.get(f'/history/{actor.id}').json()['history'], [])
                        for path in (f'/api/attendance/admin-user-export?user_id={user_id}',
                                     '/api/attendance/admin-export?date=2026-09-01',
                                     '/api/attendance/monthly-export?month=2026-09'):
                            download = client.get(path)
                            self.assertEqual(download.status_code, 200, download.text if download.status_code != 200 else '')
                            workbook = load_workbook(BytesIO(download.content))
                            rows = list(workbook.active.values)
                            self.assertTrue(any(row[1] == 'New name' for row in rows[1:]))
                        pdf = client.get(f'/api/attendance/admin-user-export?user_id={user_id}&format=pdf')
                        self.assertEqual(pdf.status_code, 200)
                        self.assertTrue(pdf.content.startswith(b'%PDF'))
                        app.dependency_overrides[auth.get_current_user] = lambda: employee
                        for employee_role in ('Employee', 'BrandPartner', 'SupportingStaff'):
                            employee.role = employee_role
                            employee.weekoff_day = None
                            db.commit()
                            saved = client.put('/api/me/weekoff', json={'weekoff_day': 'Wednesday'})
                            self.assertEqual(saved.status_code, 200, saved.text)
                            self.assertEqual(client.get('/api/me').json()['weekoff_day'], 'Wednesday')
                            self.assertEqual(client.put('/api/me/weekoff', json={'weekoff_day': 'Invalid'}).status_code, 400)
                            self.assertEqual(employee.weekoff_day, 'Wednesday')
                        employee.role = 'Employee'
                        self.assertEqual(client.get('/api/attendance/admin-export?date=2026-09-01').status_code, 403)
                        self.assertEqual(client.get(f'/history/{actor.id}').status_code, 403)
                        history = client.get('/attendance').json()
                        self.assertEqual(len(history), 1)
                        self.assertEqual(history[0]['username'], 'New name')
                        self.assertEqual(history[0]['user_id'], user_id)
                        self.assertEqual(history[0]['checkin_selfie'], 'saved-selfie')
                        summary = main.attendance_admin_summary(store_id=None,
                            from_date=date(2026, 9, 1), to_date=date(2026, 9, 1), db=db, current_user=actor)
                        row = next(row for row in summary['rows'] if row['user_id'] == user_id)
                        self.assertEqual(row['username'], 'New name')
                        self.assertEqual(row['present_days'], 1)
                        for day, expected in [(2, 'Week Off'), (3, 'Leave'), (4, 'Absent')]:
                            summary = main.attendance_admin_summary(store_id=None,
                                from_date=date(2026, 9, day), to_date=date(2026, 9, day), db=db, current_user=actor)
                            row = next(row for row in summary['rows'] if row['user_id'] == user_id)
                            self.assertEqual(row['username'], 'New name')
                            self.assertEqual(row['status'], expected)
                        summary = main.attendance_admin_summary(store_id=None,
                            from_date=date(2026, 9, 1), to_date=date(2026, 9, 4), db=db, current_user=actor)
                        row = next(row for row in summary['rows'] if row['user_id'] == user_id)
                        self.assertEqual([row[key] for key in ('present_days', 'weekoff_days', 'leave_days', 'absent_days')], [1, 1, 1, 1])
                engine.dispose()
