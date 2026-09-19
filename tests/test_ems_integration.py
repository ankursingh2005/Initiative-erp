"""Exercise ERP EMS against temporary in-memory ERP users and tables."""
from datetime import date, datetime
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import auth
import models
import ems_models as M
from database import get_db
from ems import router, pages


class EMSIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.users = []
        for role in ('Admin', 'HR', 'Owner', 'Employee', 'Employee', 'BrandPartner'):
            user = models.User(username=f'user{len(self.users)}', full_name=f'Person {len(self.users)}',
                               email=f'{len(self.users)}@example.test', password_hash='unused', role=role, status='Active')
            self.db.add(user); self.db.flush(); self.users.append(user)
        self.db.commit()
        self.actor = self.users[0]
        self.app = FastAPI()
        self.app.include_router(router); self.app.include_router(pages)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def test_existing_accounts_and_identity_are_reused(self):
        self.actor = self.users[3]
        self.db.add(models.IdentityCard(user_id=self.actor.id, employee_id='IDS-26001', employee_name='Card Name', designation='Sales Executive', mobile='9876543210', joining_date=date(2026, 9, 1)))
        self.db.commit()
        response = self.client.get('/api/ems/me')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['id'], self.actor.id)
        self.assertEqual(data['employee_id'], 'IDS-26001')
        self.assertEqual(data['joining_date'], '2026-09-01')
        self.assertEqual(data['erp_role'], 'Employee')
        self.assertNotIn('password_hash', data)
        self.assertEqual(self.db.query(models.User).count(), 6)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_employee_and_promoter_access(self):
        self.actor = self.users[3]
        for route in ('employees', 'audit'):
            self.assertEqual(self.client.get('/api/ems/'+route).status_code, 403)
        self.assertEqual(self.client.post('/api/ems/payroll', json={'user_id': self.actor.id, 'month': '2026-09', 'basic': 20000}).status_code, 403)
        # No duplicate registration, profile edit or bypass of ERP attendance controls.
        for path in ('/api/ems/register', '/api/ems/attendance/check-in'):
            self.assertEqual(self.client.post(path, json={}).status_code, 404)
        self.actor = self.users[-1]
        self.assertEqual(self.client.get('/api/ems/me').status_code, 403)

    def test_management_roles_and_user_management_scope(self):
        for actor in self.users[:3]:
            self.actor = actor
            self.assertEqual(len(self.client.get('/api/ems/employees').json()), 5)
            self.assertEqual(self.client.get('/api/ems/me').json()['can_manage_users'], actor.role != 'Owner')

    def test_existing_attendance_is_scoped(self):
        self.db.add(models.AttendanceRecord(user_id=self.users[3].id, attendance_date=date(2026, 9, 18), checkin_at=datetime(2026, 9, 18, 9)))
        self.db.commit()
        self.actor = self.users[3]
        result = self.client.get('/api/ems/attendance').json()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['check_in'], '2026-09-18T09:00:00+05:30')
        self.actor = self.users[4]
        self.assertEqual(self.client.get('/api/ems/attendance').json(), [])

    def test_management_attendance_excludes_brand_promoters(self):
        for employee in (self.users[3], self.users[-1]):
            self.db.add(models.AttendanceRecord(user_id=employee.id,
                        attendance_date=date(2026, 9, 19), checkin_at=datetime(2026, 9, 19, 9)))
        self.db.commit()
        for actor in self.users[:3]:
            self.actor = actor
            response = self.client.get('/api/ems/attendance')
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row['user_id'] for row in response.json()], [self.users[3].id])

    def test_leave_approval_updates_erp_attendance_leave(self):
        self.actor = self.users[3]
        payload = {'start_date': '2026-10-01', 'end_date': '2026-10-03', 'kind': 'Casual', 'reason': 'Family visit'}
        self.assertEqual(self.client.post('/api/ems/leave', json=payload).status_code, 201)
        self.assertEqual(self.client.post('/api/ems/leave', json=payload).status_code, 409)
        self.db.rollback()
        leave_id = self.client.get('/api/ems/leave').json()[0]['id']
        self.actor = self.users[4]
        self.assertEqual(self.client.get('/api/ems/leave').json(), [])
        self.actor = self.users[1]
        self.assertEqual(self.client.put(f'/api/ems/leave/{leave_id}', json={'status': 'approved'}).status_code, 200)
        self.assertEqual(self.db.query(models.AttendanceLeave).filter_by(user_id=self.users[3].id).count(), 3)
        self.assertEqual(self.client.put(f'/api/ems/leave/{leave_id}', json={'status': 'approved'}).status_code, 409)

    def test_payroll_rewards_and_isolation(self):
        uid = self.users[3].id
        self.client.get('/api/ems/me')
        for kind, amount in [('incentive', '1250.50'), ('bonus', '500.25')]:
            response = self.client.post('/api/ems/earnings', json={'user_id': uid, 'month': '2026-09', 'kind': kind, 'amount': amount, 'note': 'Approved award'})
            self.assertEqual(response.status_code, 201, response.text)
        payload = {'user_id': uid, 'month': '2026-09', 'basic': '20000', 'allowances': '1000', 'deductions': '200.25'}
        response = self.client.post('/api/ems/payroll', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.client.post('/api/ems/payroll', json=payload).status_code, 409)
        self.assertEqual(self.client.post('/api/ems/earnings', json={'user_id': uid, 'month': '2026-09', 'kind': 'bonus', 'amount': 1, 'note': 'Too late'}).status_code, 409)
        self.db.rollback()
        row = self.client.get('/api/ems/payroll').json()[0]
        self.assertEqual(row['net'], 2255050)
        self.assertTrue(row['employee_id'].startswith('IDS-'))
        self.assertEqual(self.client.put(f'/api/ems/payroll/{row["id"]}/paid').status_code, 200)
        self.actor = self.users[3]
        self.assertEqual(self.client.get('/api/ems/payroll').json()[0]['status'], 'paid')
        self.actor = self.users[4]
        self.assertEqual(self.client.get('/api/ems/payroll').json(), [])
        self.assertEqual(self.client.get('/api/ems/earnings').json(), [])

    def test_page_uses_shared_assets_and_erp_mode(self):
        page = self.client.get('/ems')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-erp="true"', page.text)
        self.assertIn('"ems-assets/app.js"', page.text)
        self.assertNotIn('"/static/app.js"', page.text)

    def test_real_erp_bearer_authentication(self):
        self.app.dependency_overrides.pop(auth.get_current_user)
        self.assertEqual(self.client.get('/api/ems/me').status_code, 401)
        token = auth.create_access_token({'user_id': self.users[3].id, 'role': 'Employee'})
        headers = {'Authorization': 'Bearer '+token}
        self.assertEqual(self.client.get('/api/ems/me', headers=headers).status_code, 200)
        self.users[3].status = 'Inactive'; self.db.commit()
        self.assertEqual(self.client.get('/api/ems/me', headers=headers).status_code, 401)


if __name__ == '__main__':
    unittest.main()
