import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from app import main


class EMSTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.previous = main.DB_PATH
        main.DB_PATH = Path(self.directory.name) / 'ems.sqlite3'
        main.initialize()
        with main.db() as conn:
            self.admin_id = conn.execute("INSERT INTO users(name,email,password_hash,role,status,created_at) VALUES(?,?,?,'admin','active',?)",
                ('Administrator', 'admin@example.test', main.password_hash('SafePassword123'), main.now())).lastrowid
        self.admin = TestClient(main.app)
        self.employee = TestClient(main.app)
        self.other = TestClient(main.app)
        self.sign_in(self.admin, 'admin@example.test')
        self.employee_id = self.register('employee@example.test', 'Asha Singh')
        self.other_id = self.register('other@example.test', 'Ravi Kumar')
        for user_id in (self.employee_id, self.other_id):
            self.approve(user_id)
        self.sign_in(self.employee, 'employee@example.test')
        self.sign_in(self.other, 'other@example.test')

    def tearDown(self):
        self.admin.close()
        self.employee.close()
        self.other.close()
        main.DB_PATH = self.previous
        self.directory.cleanup()

    def sign_in(self, client, email):
        result = client.post('/api/login', json={'email': email, 'password': 'SafePassword123'})
        self.assertEqual(result.status_code, 200, result.text)
        client.headers['X-CSRF-Token'] = result.json()['csrf']

    def register(self, email, name):
        result = self.employee.post('/api/register', json={'name': name, 'email': email, 'password': 'SafePassword123'})
        self.assertEqual(result.status_code, 201, result.text)
        with main.db() as conn:
            return conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def approve(self, user_id, **changes):
        payload = {'status': 'active', 'role': 'employee', 'department': 'Sales',
                   'designation': 'Sales Executive', 'outlet': 'Head Office', 'joining_date': '2026-09-01', **changes}
        result = self.admin.put(f'/api/employees/{user_id}', json=payload)
        self.assertEqual(result.status_code, 200, result.text)

    def test_registration_requires_approval_and_cannot_choose_role(self):
        self.register('pending@example.test', 'Pending User')
        self.assertEqual(self.other.post('/api/login', json={'email': 'pending@example.test', 'password': 'SafePassword123'}).status_code, 403)
        self.assertEqual(self.other.post('/api/register', json={'name': 'Admin', 'email': 'evil@example.test', 'password': 'SafePassword123', 'role': 'admin'}).status_code, 422)
        self.assertEqual(self.employee.post('/api/register', json={'name': 'Duplicate', 'email': 'employee@example.test', 'password': 'SafePassword123'}).status_code, 409)

    def test_employee_permissions_and_csrf(self):
        for path in ('/api/employees', '/api/audit'):
            self.assertEqual(self.employee.get(path).status_code, 403)
        self.assertEqual(self.employee.post('/api/payroll', json={'user_id': self.employee_id, 'month': '2026-09', 'basic': 20000}).status_code, 403)
        self.assertEqual(self.employee.post('/api/attendance/check-in', headers={'X-CSRF-Token': ''}).status_code, 403)
        self.assertEqual(self.employee.post('/api/attendance/check-in', headers={'Origin': 'https://untrusted.example'}).status_code, 403)

    def test_attendance_is_unique_and_scoped(self):
        self.assertEqual(self.employee.post('/api/attendance/check-out').status_code, 409)
        self.assertEqual(self.employee.post('/api/attendance/check-in').status_code, 200)
        self.assertEqual(self.employee.post('/api/attendance/check-in').status_code, 409)
        self.assertEqual(self.employee.post('/api/attendance/check-out').status_code, 200)
        self.assertEqual(self.employee.post('/api/attendance/check-out').status_code, 409)
        self.assertEqual(len(self.employee.get('/api/attendance').json()), 1)
        self.assertEqual(self.other.get('/api/attendance').json(), [])
        self.assertEqual(len(self.admin.get('/api/attendance').json()), 1)

    def test_leave_workflow_and_overlap(self):
        payload = {'start_date': '2026-10-01', 'end_date': '2026-10-03', 'kind': 'Casual', 'reason': 'Family visit'}
        self.assertEqual(self.employee.post('/api/leave', json=payload).status_code, 201)
        self.assertEqual(self.employee.post('/api/leave', json=payload).status_code, 409)
        rows = self.employee.get('/api/leave').json()
        leave_id = rows[0]['id']
        self.assertEqual(self.other.get('/api/leave').json(), [])
        self.assertEqual(self.employee.put(f'/api/leave/{leave_id}', json={'status': 'approved'}).status_code, 403)
        self.assertEqual(self.admin.put(f'/api/leave/{leave_id}', json={'status': 'approved'}).status_code, 200)
        self.assertEqual(self.admin.put(f'/api/leave/{leave_id}', json={'status': 'rejected'}).status_code, 409)
        self.assertEqual(self.employee.get('/api/leave').json()[0]['status'], 'approved')

    def test_payroll_totals_snapshot_duplicate_and_privacy(self):
        for kind, amount in [('incentive', '1250.50'), ('bonus', '500.25')]:
            result = self.admin.post('/api/earnings', json={'user_id': self.employee_id, 'month': '2026-09', 'kind': kind, 'amount': amount, 'note': 'Monthly reward'})
            self.assertEqual(result.status_code, 201, result.text)
        payload = {'user_id': self.employee_id, 'month': '2026-09', 'basic': '20000', 'allowances': '1000', 'deductions': '200.25'}
        self.assertEqual(self.admin.post('/api/payroll', json=payload).status_code, 201)
        row = self.employee.get('/api/payroll').json()[0]
        self.assertEqual(row['net'], 2255050)
        self.assertEqual(self.other.get('/api/payroll').json(), [])
        self.assertEqual(self.other.get('/api/earnings').json(), [])
        self.assertEqual(self.admin.post('/api/payroll', json=payload).status_code, 409)
        self.assertEqual(self.admin.post('/api/earnings', json={'user_id': self.employee_id, 'month': '2026-09', 'kind': 'bonus', 'amount': 50, 'note': 'Too late'}).status_code, 409)
        self.assertEqual(self.admin.put(f'/api/payroll/{row["id"]}/paid').status_code, 200)
        self.assertEqual(self.employee.get('/api/payroll').json()[0]['status'], 'paid')
        self.assertTrue(any(a['action'] == 'payroll_marked_paid' for a in self.admin.get('/api/audit').json()))

    def test_deactivation_revokes_sessions(self):
        self.approve(self.employee_id, status='inactive')
        self.assertEqual(self.employee.get('/api/me').status_code, 401)

    def test_last_admin_and_hr_permissions(self):
        self.assertEqual(self.admin.put(f'/api/employees/{self.admin_id}', json={'status': 'inactive', 'role': 'admin'}).status_code, 409)
        self.approve(self.employee_id, role='hr')
        self.sign_in(self.employee, 'employee@example.test')
        self.assertEqual(self.employee.put(f'/api/employees/{self.other_id}', json={'status': 'active', 'role': 'admin'}).status_code, 403)

    def test_profile_and_identity_details(self):
        self.assertEqual(self.employee.put('/api/me', json={'name': 'Asha Singh Updated', 'phone': '9876543210', 'photo': None}).status_code, 200)
        data = self.employee.get('/api/me').json()
        self.assertEqual(data['name'], 'Asha Singh Updated')
        self.assertEqual(data['joining_date'], '2026-09-01')
        self.assertNotIn('password_hash', data)
        self.assertEqual(self.employee.put('/api/me', json={'name': 'Asha', 'photo': 'data:image/svg+xml;base64,xxxx'}).status_code, 422)

    def test_invalid_values(self):
        self.assertEqual(self.admin.post('/api/payroll', json={'user_id': self.employee_id, 'month': '2026-09', 'basic': 1, 'deductions': 2}).status_code, 422)
        self.assertEqual(self.admin.post('/api/payroll', json={'user_id': self.employee_id, 'month': '2026-13', 'basic': 10}).status_code, 422)
        self.assertEqual(self.employee.post('/api/leave', json={'start_date': '2026-10-05', 'end_date': '2026-10-01', 'kind': 'Casual', 'reason': 'Invalid date range'}).status_code, 422)

    def test_logout_ends_session(self):
        self.assertEqual(self.employee.post('/api/logout').status_code, 200)
        self.assertEqual(self.employee.get('/api/me').status_code, 401)

    def test_static_entrypoint(self):
        result = self.employee.get('/')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Employee Management System', result.text)
        self.assertEqual(self.employee.get('/static/app.js').status_code, 200)


if __name__ == '__main__':
    unittest.main()
