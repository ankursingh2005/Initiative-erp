"""Payroll integration checks use isolated SQLite, never the ERP database."""
import unittest
from datetime import date, datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import auth
import models
import ems_models as M
from database import Base, get_db
from ems import router, pages


class SalaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine, 'connect', lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.users = []
        for role in ['Admin', 'HR', 'Employee', 'AC Technician A', 'AC Technician B', 'BrandPartner']:
            user = models.User(username=role, full_name=role, email=role+'@test.local', password_hash='unused',
                               role=role, status='Active', created_date=datetime(2025, 1, 1), weekoff_day='Sunday')
            self.db.add(user); self.db.flush(); self.users.append(user)
        self.db.commit()
        self.actor = self.users[0]
        app = FastAPI(); app.include_router(router); app.include_router(pages)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def test_ems_reads_preserve_existing_erp_records(self):
        self.db.add(models.IdentityCard(user_id=self.users[2].id,
                    employee_id='LEGACY-UNCHANGED', employee_name='Existing card',
                    designation='Sales', mobile='12345'))
        self.db.commit()
        # Include all shared tables, so unrelated projects are protected too.
        tables = [table for table in Base.metadata.sorted_tables
                  if not table.name.startswith('ems_')]

        def snapshot():
            return {table.name: self.db.execute(table.select()).all() for table in tables}

        before = snapshot()
        for path in ('/api/ems/me', '/api/ems/employees', '/api/ems/attendance',
                     '/api/ems/attendance-summary?month=2026-09',
                     '/api/ems/salary-preview?month=2026-09'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(snapshot(), before, path)

    def setup_salary(self, uid=None, **changes):
        payload = dict(user_id=uid or self.users[2].id, effective_month='2026-09', basic='30000',
                       allowances='3000', deductions='100', divisor='calendar', paid_weekoff=True, paid_leave=False)
        payload.update(changes)
        return self.client.post('/api/ems/salary-profiles', json=payload)

    def preview(self, uid=None, month='2026-09'):
        response = self.client.get('/api/ems/salary-preview', params={'month': month})
        self.assertEqual(response.status_code, 200, response.text)
        return next(r for r in response.json()['rows'] if r['user_id'] == (uid or self.users[2].id))

    def publish(self, row, acknowledge=True):
        return self.client.post('/api/ems/salary-publish', json=dict(user_id=row['user_id'], month='2026-09',
                         preview=row, acknowledge_pending_incentive=acknowledge))

    def test_scope_auth_and_page(self):
        result = self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows']
        self.assertEqual(len(result), 5)
        self.assertEqual({r['category'] for r in result}, {'ids_emp','ac_projects','ac_retails'})
        self.assertEqual(self.setup_salary(self.users[-1].id).status_code, 404)
        self.db.rollback()
        for role in [self.users[2], self.users[-1]]:
            self.actor = role
            self.assertEqual(self.client.get('/api/ems/salary-preview?month=2026-09').status_code, 403)
            self.assertEqual(self.client.get('/api/ems/salary-profiles').status_code, 403)
        self.actor = self.users[1]
        self.assertEqual(self.client.get('/api/ems/salary-preview?month=2026-09').status_code, 200)
        page = self.client.get('/ems').text
        self.assertIn('static/ems.js', page)
        self.assertIn('data-erp="true"', page)

    def test_attendance_pay_and_approved_earnings(self):
        user = self.users[2]
        self.db.add(models.AttendanceRecord(user_id=user.id, attendance_date=date(2026,9,1), checkin_at=datetime(2026,9,1,9)))
        self.db.add(models.AttendanceLeave(user_id=user.id, leave_date=date(2026,9,2), created_by=self.actor.id))
        self.db.add(M.EMSEarning(user_id=user.id, month='2026-09', kind='incentive', amount=50000, note='Approved', created_by=self.actor.id))
        self.db.add(M.EMSEarning(user_id=user.id, month='2026-09', kind='bonus', amount=90000, status='rejected', note='Rejected', created_by=self.actor.id))
        self.db.commit()
        self.assertEqual(self.setup_salary().status_code, 200)
        row = self.preview()
        self.assertEqual(row['counts'], dict(present=1, absent=24, weekoff=4, leave=1, upcoming=0, before_joining=0))
        self.assertEqual((row['basic'],row['allowances'],row['deductions'],row['incentive'],row['bonus'],row['net']),
                         (500000,50000,10000,50000,0,590000))
        self.assertTrue(row['can_publish'])

    def test_weekoff_history_joining_and_future(self):
        user = self.users[2]
        user.weekoff_day = 'Monday'
        user.weekoff_history = '[{"from":"0001-01-01","day":"Sunday"},{"from":"2026-10-01","day":"Monday"}]'
        self.db.add(models.IdentityCard(user_id=user.id, employee_id='IDS-26001', employee_name='Employee', designation='Sales',
                                       joining_date=date(2026,9,15)))
        self.db.commit(); self.setup_salary()
        row = self.preview()
        self.assertEqual(row['counts']['before_joining'],14)
        self.assertEqual(row['counts']['weekoff'],2)
        self.assertEqual(row['counts']['absent'],14)
        future = self.preview(month='2099-01')
        self.assertEqual(future['counts']['upcoming'],31)
        self.assertFalse(future['can_publish'])

    def test_publication_freezes_and_rejects_stale_or_duplicate(self):
        self.setup_salary()
        row = self.preview()
        self.assertEqual(self.publish(row,False).status_code,422)
        self.db.add(models.AttendanceRecord(user_id=row['user_id'], attendance_date=date(2026,9,1), checkin_at=datetime(2026,9,1,9)))
        self.db.commit()
        self.assertEqual(self.publish(row).status_code,409)
        row = self.preview()
        response = self.publish(row)
        self.assertEqual(response.status_code,201,response.text)
        slip_id = response.json()['id']
        self.assertEqual(self.publish(row).status_code,409)
        self.assertEqual(self.setup_salary().status_code,409)
        self.db.rollback()
        slip = self.client.get(f'/api/ems/salary-slips/{slip_id}').json()
        self.assertEqual(slip['snapshot'],row)
        self.assertEqual(slip['payroll']['net'],row['net'])
        self.assertEqual(self.client.put(f'/api/ems/payroll/{slip_id}/paid').status_code,200)
        self.assertEqual(self.client.put(f'/api/ems/payroll/{slip_id}/paid').status_code,409)

    def test_effective_profiles_invalid_month_negative_net(self):
        self.assertEqual(self.setup_salary(effective_month='0000-01').status_code,422)
        self.assertEqual(self.client.get('/api/ems/salary-preview?month=2026-13').status_code,422)
        self.setup_salary()
        self.setup_salary(effective_month='2026-10',basic='60000')
        self.assertEqual(self.preview()['monthly_basic'],3000000)
        self.assertEqual(self.preview(month='2026-10')['monthly_basic'],6000000)
        self.setup_salary(deductions='99999')
        self.assertFalse(self.preview()['can_publish'])

    def test_fixed_thirty_completely_unpaid_february_is_zero(self):
        self.assertEqual(self.setup_salary(effective_month='2026-02', divisor='30', paid_weekoff=False,
                                          paid_leave=False, deductions='0').status_code,200)
        row = self.preview(month='2026-02')
        self.assertEqual(row['unpaid_days'],28)
        self.assertEqual(row['net'],0)

    def test_void_earning_changes_draft_but_not_published_salary(self):
        self.setup_salary()
        uid = self.users[2].id
        self.client.post('/api/ems/earnings',json=dict(user_id=uid,month='2026-09',kind='bonus',amount='500',note='Approved'))
        earning = self.db.query(M.EMSEarning).one()
        self.assertEqual(self.preview()['bonus'],50000)
        self.assertEqual(self.client.put(f'/api/ems/earnings/{earning.id}/void').status_code,200)
        self.assertEqual(self.preview()['bonus'],0)
        self.client.post('/api/ems/earnings',json=dict(user_id=uid,month='2026-09',kind='bonus',amount='100',note='Corrected'))
        row = self.preview()
        self.assertEqual(self.publish(row).status_code,201)
        self.assertEqual(self.client.put(f'/api/ems/earnings/{earning.id}/void').status_code,409)

    def test_full_paid_thirty_one_day_month_is_full_salary(self):
        uid = self.users[2].id
        for day in range(1,32):
            self.db.add(models.AttendanceRecord(user_id=uid,attendance_date=date(2026,8,day),
                                               checkin_at=datetime(2026,8,day,9)))
        self.db.commit()
        self.setup_salary(effective_month='2026-08',divisor='30')
        row = self.preview(month='2026-08')
        self.assertEqual(row['counts']['present'],31)
        self.assertEqual(row['net'],3290000)


if __name__ == '__main__':
    unittest.main()
