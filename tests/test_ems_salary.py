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

    def test_shared_attendance_correction_updates_ems_and_restores_source(self):
        uid = self.users[2].id
        day = date(2026, 9, 6)
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=day,
                                           checkin_at=datetime(2026, 9, 6, 9)))
        self.db.commit()
        path = f'/api/ems/attendance-records/{uid}'
        payload = {'month': '2026-09', 'days': [{'day': str(day), 'status': 'absent', 'note': 'HR correction'}]}
        self.assertEqual(self.client.put(path, json=payload).status_code, 200)
        row = next(r for r in self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows'] if r['user_id'] == uid)
        self.assertEqual(next(d for d in row['days'] if d['day'] == str(day))['status'], 'absent')
        summary = self.client.get('/api/ems/attendance-summary?day=2026-09-06').json()
        self.assertEqual(next(r for r in summary['rows'] if r['user_id'] == uid)['status'], 'Absent')
        self.assertIsNotNone(self.db.query(models.AttendanceRecord).filter_by(user_id=uid, attendance_date=day).first().checkin_at)
        payload['days'][0]['status'] = 'auto'
        self.assertEqual(self.client.put(path, json=payload).status_code, 200)
        row = next(r for r in self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows'] if r['user_id'] == uid)
        self.assertEqual(next(d for d in row['days'] if d['day'] == str(day))['status'], 'present')
        self.actor = self.users[2]
        self.assertEqual(self.client.put(path, json=payload).status_code, 403)

    def test_all_ems_corrections_leave_original_attendance_unchanged(self):
        uid = self.users[2].id
        day = date(2026, 9, 6)
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=day,
            checkin_at=datetime(2026, 9, 6, 9), checkout_at=datetime(2026, 9, 6, 18),
            checkin_selfie='original-in', checkout_selfie='original-out'))
        self.db.add(models.AttendanceLeave(user_id=uid, leave_date=date(2026, 9, 7), created_by=self.actor.id))
        self.db.commit()

        def source_snapshot():
            self.db.expire_all()
            return {model.__tablename__: [tuple(getattr(row, column.name) for column in model.__table__.columns)
                    for row in self.db.query(model).order_by(model.id).all()]
                    for model in (models.AttendanceRecord, models.AttendanceLeave, models.User)}

        original = source_snapshot()
        for status in ('absent', 'present', 'weekoff', 'leave', 'auto'):
            result = self.client.put(f'/api/ems/attendance-records/{uid}', json={
                'month': '2026-09', 'days': [
                    {'day': '2026-09-06', 'status': status},
                    {'day': '2026-09-07', 'status': status},
                    {'day': '2026-09-08', 'status': status}]})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(source_snapshot(), original, status)
        self.assertEqual(self.db.query(M.EMSManualAttendance).filter_by(user_id=uid).count(), 0)

    def test_weekoff_setup_fetches_attendance_and_ignores_manual_counts(self):
        uid = self.users[2].id
        self.assertEqual(self.setup_salary(weekoff_availed=0, weekoff_credit=4).status_code, 200)
        profile = self.client.get('/api/ems/salary-profiles').json()[0]
        self.assertEqual((profile['weekoff_availed'], profile['weekoff_credit'], profile['weekoff_pay']), (4, 0, 0))
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=date(2026, 9, 6),
                                           checkin_at=datetime(2026, 9, 6, 9)))
        self.db.commit()
        self.assertEqual(self.setup_salary(basic='29063', allowances='0', weekoff_availed=0,
                                          weekoff_pay='999').status_code, 200)
        profile = self.client.get('/api/ems/salary-profiles').json()[0]
        self.assertEqual((profile['weekoff_availed'], profile['weekoff_credit'], profile['weekoff_pay']), (3, 1, 96877))

    def test_five_weekoffs_do_not_generate_negative_credit(self):
        self.assertEqual(self.setup_salary(effective_month='2026-08').status_code, 200)
        profile = self.client.get('/api/ems/salary-profiles').json()[0]
        self.assertEqual((profile['weekoff_availed'], profile['weekoff_credit'], profile['weekoff_pay']), (5, 0, 0))

    def test_employment_category_saves_and_appears_in_preview(self):
        for category in ('Regular', 'Contract'):
            self.assertEqual(self.setup_salary(employment_category=category).status_code, 200)
            self.assertEqual(self.preview()['employment_category'], category)
            profile = self.client.get('/api/ems/salary-profiles').json()[0]
            self.assertEqual(profile['employment_category'], category)
        self.assertEqual(self.setup_salary(employment_category='Other').status_code, 422)

    def test_retired_ids_cleanup_preserves_salary_totals(self):
        import json
        from sqlalchemy import text
        from ems import remove_retired_ids_data
        uid = self.users[2].id
        self.setup_salary(uid)
        payroll = M.EMSPayroll(user_id=uid, month='2026-09', basic=2000000,
            allowances=625000, deductions=355000, incentives=0, bonuses=0, net=2270000, created_by=self.actor.id)
        self.db.add(payroll); self.db.flush()
        details = dict(net=2270000, basic=2000000, ids_attributes=dict(account_no='SYNTHETIC'),
                       actual_vda=125000, epf_employee=255000)
        snapshot = M.EMSPayrollSnapshot(payroll_id=payroll.id, details=json.dumps(details))
        self.db.add(snapshot)
        self.db.add(M.EMSAudit(actor_id=self.actor.id, name='Synthetic actor', action='salary_profile_saved',
            target=str(uid), details=json.dumps(details)))
        self.db.commit()
        with self.engine.begin() as connection:
            connection.execute(text('ALTER TABLE ems_salary_profiles ADD COLUMN ids_attributes TEXT'))
            connection.execute(text('UPDATE ems_salary_profiles SET ids_attributes = :value'),
                               dict(value=json.dumps(dict(branch='SYNTHETIC'))))
            remove_retired_ids_data(connection)
            remove_retired_ids_data(connection)
            self.assertIsNone(connection.execute(text('SELECT ids_attributes FROM ems_salary_profiles')).scalar())
        self.db.expire_all()
        self.assertEqual(json.loads(snapshot.details), dict(net=2270000, basic=2000000))
        self.assertEqual(self.db.get(M.EMSPayroll, payroll.id).net, 2270000)
        self.assertEqual(self.db.query(M.EMSSalaryProfile).count(), 1)
        self.assertEqual(self.setup_salary(uid, ids_attributes=dict(branch='REMOVED')).status_code, 422)

    def test_salary_distribution_inputs_are_monthly_and_do_not_change_other_projects(self):
        from salary_distribution import calculate_distribution
        uid = self.users[2].id
        response = self.setup_salary(uid, basic='16000', allowances='0', deductions='0',
            account_no='000123456789', ifsc_code='SBIN0001234')
        self.assertEqual(response.status_code, 200, response.text)
        shared = [t for t in Base.metadata.sorted_tables if not t.name.startswith('ems_')]
        before = {t.name: self.db.execute(t.select()).all() for t in shared}
        path = f'/api/ems/salary-distribution/{uid}'
        response = self.client.put(path, json=dict(month='2026-09', other_allowances='1000.00', staff_advance='500.00'))
        self.assertEqual(response.status_code, 200, response.text)
        result = self.client.get('/api/ems/salary-distribution?month=2026-09')
        self.assertEqual(result.status_code, 200, result.text)
        row = next(r for r in result.json()['rows'] if r['user_id'] == uid)
        absent = self.preview(uid)['counts']['absent']
        expected = calculate_distribution(1600000, absent, 100000, 50000)
        for key, value in expected.items():
            self.assertEqual(row[key], value, key)
        self.assertEqual(row['account_no'], '000123456789')
        self.assertEqual(row['ifsc_code'], 'SBIN0001234')
        october = self.client.get('/api/ems/salary-distribution?month=2026-10').json()
        row = next(r for r in october['rows'] if r['user_id'] == uid)
        self.assertEqual(row['other_allowances'], 0)
        self.assertEqual(row['staff_advance'], 0)
        self.assertEqual({t.name: self.db.execute(t.select()).all() for t in shared}, before)
        self.assertEqual(self.db.query(M.EMSPayroll).count(), 0)
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', other_allowances='-1', staff_advance='0')).status_code, 422)
        self.actor = self.users[2]
        self.assertEqual(self.client.get('/api/ems/salary-distribution?month=2026-09').status_code, 403)
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', other_allowances='0', staff_advance='0')).status_code, 403)

    def create_manual(self, **changes):
        payload = dict(full_name='Synthetic manual employee',
                       joining_date='2026-09-01', employee_group='ids_emp')
        payload.update(changes)
        return self.client.post('/api/ems/manual-employees', json=payload)

    def test_manual_employee_attendance_and_payroll(self):
        response = self.create_manual()
        self.assertEqual(response.status_code, 201, response.text)
        uid = response.json()['user_id']
        self.assertEqual(self.db.get(models.User, uid).role, 'EMSManual')
        second = self.create_manual()
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(response.json()['employee_id'], second.json()['employee_id'])
        self.assertEqual(self.setup_salary(uid, basic='20000', allowances='5000',
            deductions='1000', employment_category='Regular').status_code, 200)
        row = self.preview(uid)
        self.assertTrue(row['manual_employee'])
        self.assertEqual(row['missing_attendance'], 30)
        self.assertFalse(row['can_publish'])
        days = [dict(day=f'2026-09-{day:02d}', status='present') for day in range(1, 31)]
        path = f'/api/ems/manual-employees/{uid}/attendance'
        response = self.client.put(path, json=dict(month='2026-09', days=days))
        self.assertEqual(response.status_code, 200, response.text)
        row = self.preview(uid)
        self.assertEqual(row['missing_attendance'], 0)
        self.assertEqual(row['counts']['present'], 30)
        self.assertEqual(row['net'], 2400000)
        self.assertTrue(row['can_publish'])
        self.assertEqual(self.publish(row).status_code, 201)
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', days=days)).status_code, 409)
        payroll = self.db.query(M.EMSPayroll).filter_by(user_id=uid).one()
        slip = self.client.get(f'/api/ems/salary-slips/{payroll.id}').json()
        self.assertTrue(slip['snapshot']['manual_employee'])
        self.assertEqual(slip['payroll']['net'], 2400000)

    def test_manual_employee_scope_and_attendance_validation(self):
        response = self.create_manual(joining_date='2026-09-10')
        self.assertEqual(response.status_code, 201)
        uid = response.json()['user_id']
        path = f'/api/ems/manual-employees/{uid}/attendance'
        invalid = [dict(day='2026-09-09', status='present')]
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', days=invalid)).status_code, 422)
        days = [dict(day='2026-09-10', status='present')]*2
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', days=days)).status_code, 422)
        self.assertEqual(self.db.query(M.EMSManualAttendance).count(), 0)
        self.actor = self.users[2]
        self.assertEqual(self.create_manual(full_name='Denied').status_code, 403)
        self.assertEqual(self.client.put(path, json=dict(month='2026-09', days=invalid)).status_code, 403)

    def test_outlet_employee_id_preview_and_atomic_assignment(self):
        store = models.Store(name='Raibareli', code='RBL', status='Active')
        self.db.add(store); self.db.commit()
        path = f'/api/ems/manual-employee-id?store_id={store.id}'
        preview = self.client.get(path).json()['employee_id']
        self.assertTrue(preview.startswith('IDS-RBL-'))
        self.assertEqual(self.client.get(path).json()['employee_id'], preview)
        self.assertEqual(self.db.query(models.IdentityCardSequence).count(), 0)
        result = self.create_manual(store_id=store.id)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['employee_id'], preview)
        second = self.create_manual(store_id=store.id)
        self.assertNotEqual(second.json()['employee_id'], preview)
        self.assertEqual(self.db.query(models.IdentityCardSequence).one().last_number, 2)
        self.assertEqual(self.create_manual(employee_id='OVERRIDE').status_code, 422)

    def test_salary_removal_requires_actor_password_and_remove(self):
        uid = self.users[2].id
        self.actor.password_hash = auth.hash_password('SyntheticPassword123')
        self.db.commit()
        path = f'/api/ems/employees/{uid}/exclude'
        self.assertEqual(self.client.put(path).status_code, 422)
        self.assertEqual(self.client.put(path, json=dict(password='wrong', confirmation='REMOVE')).status_code, 403)
        self.assertEqual(self.client.put(path, json=dict(password='SyntheticPassword123', confirmation='remove')).status_code, 422)
        self.assertIsNone(self.db.get(M.EMSExcludedEmployee, uid))
        check = f'/api/ems/employees/{uid}/removal-password'
        self.assertEqual(self.client.post(check, json=dict(password='wrong')).status_code, 403)
        self.assertEqual(self.client.post(check, json=dict(password='SyntheticPassword123')).status_code, 200)
        self.assertIsNone(self.db.get(M.EMSExcludedEmployee, uid))
        self.assertEqual(self.client.put(path, json=dict(password='SyntheticPassword123', confirmation='REMOVE')).status_code, 200)
        audit = self.db.query(M.EMSAudit).filter_by(action='employee_excluded_from_salary').one()
        self.assertNotIn('SyntheticPassword123', audit.details)

    def test_permanent_ems_deletion_is_separate_from_erp(self):
        uid = self.users[2].id
        self.actor.password_hash = auth.hash_password('SyntheticPassword123')
        self.db.commit()
        self.setup_salary(uid)
        self.db.add(models.IdentityCard(user_id=uid, employee_id='PRESERVED-ID',
            employee_name='Synthetic employee', designation='Employee'))
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=date(2026, 9, 1),
            checkin_at=datetime(2026, 9, 1, 9)))
        self.db.add(M.EMSManualAttendance(user_id=uid, day=date(2026, 9, 2), status='present', updated_by=self.actor.id))
        payroll = M.EMSPayroll(user_id=uid, month='2026-09', basic=100, allowances=0,
            deductions=0, incentives=0, bonuses=0, net=100, created_by=self.actor.id)
        self.db.add(payroll); self.db.flush()
        self.db.add(M.EMSPayrollSnapshot(payroll_id=payroll.id, details='{}'))
        self.db.add(M.EMSExcludedEmployee(user_id=uid, created_by=self.actor.id))
        self.db.add(M.EMSDistributionInput(user_id=uid, month='2026-09', other_allowances=10000, staff_advance=0, updated_by=self.actor.id))
        self.db.commit()
        path = f'/api/ems/employees/{uid}'
        self.assertEqual(self.client.request('DELETE', path, json=dict(password='wrong', confirmation='DELETE')).status_code, 403)
        self.assertEqual(self.client.request('DELETE', path, json=dict(password='SyntheticPassword123', confirmation='REMOVE')).status_code, 422)
        response = self.client.request('DELETE', path, json=dict(password='SyntheticPassword123', confirmation='DELETE'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(self.db.get(models.User, uid).ems_deleted)
        self.assertFalse(self.db.get(models.User, uid).erp_deleted)
        self.assertIsNotNone(self.db.get(models.IdentityCard, uid))
        self.assertEqual(self.db.query(models.AttendanceRecord).filter_by(user_id=uid).count(), 1)
        for model in (M.EMSSalaryProfile, M.EMSPayroll, M.EMSManualAttendance, M.EMSExcludedEmployee, M.EMSDistributionInput):
            self.assertEqual(self.db.query(model).filter_by(user_id=uid).count(), 0)
        self.assertEqual(self.db.query(M.EMSPayrollSnapshot).count(), 0)
        self.assertNotIn(uid, [r['user_id'] for r in self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows']])
        self.assertNotIn(uid, [r['user_id'] for r in self.client.get('/api/ems/excluded-employees').json()])
        self.assertEqual(self.client.delete(f'/api/ems/employees/{uid}/exclude').status_code, 404)
        self.assertEqual(self.setup_salary(uid).status_code, 404)
        self.assertEqual(self.client.get(f'/api/ems/salary-slips/{payroll.id}').status_code, 404)
        self.assertEqual(self.db.query(M.EMSAudit).filter_by(action='employee_permanently_deleted_from_ems').count(), 1)

    def test_erp_deleted_employee_stays_in_ems(self):
        uid = self.users[2].id
        self.setup_salary(uid)
        before = self.preview(uid)
        self.users[2].erp_deleted = True
        self.db.commit()
        after = self.preview(uid)
        self.assertTrue(after.pop('erp_account_deleted'))
        before.pop('erp_account_deleted')
        self.assertEqual(before, after)
        self.assertEqual(self.setup_salary(uid, effective_month='2026-10').status_code, 200)
        from fastapi import HTTPException
        token = auth.create_access_token(dict(user_id=uid, session_version=1))
        with self.assertRaises(HTTPException):
            auth.get_current_user(token=token, db=self.db)

    def test_manual_employee_cannot_use_login_token(self):
        uid = self.create_manual().json()['user_id']
        token = auth.create_access_token(dict(user_id=uid, session_version=1))
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            auth.get_current_user(token=token, db=self.db)
        self.assertEqual(error.exception.status_code, 401)

    def test_exclude_and_restore_salary_employee_preserves_records(self):
        uid = self.users[2].id
        self.setup_salary()
        self.actor.password_hash = auth.hash_password('SyntheticPassword123')
        self.db.commit()
        response = self.client.put(f'/api/ems/employees/{uid}/exclude',
            json=dict(password='SyntheticPassword123', confirmation='REMOVE'))
        self.assertEqual(response.status_code, 200)
        rows = self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows']
        self.assertNotIn(uid, {row['user_id'] for row in rows})
        self.assertIsNotNone(self.db.get(models.User, uid))
        self.assertEqual(self.db.query(M.EMSSalaryProfile).filter_by(user_id=uid).count(), 1)
        self.assertEqual(self.setup_salary(uid).status_code, 404)
        self.assertIn(uid, {row['user_id'] for row in self.client.get('/api/ems/excluded-employees').json()})
        self.assertEqual(self.client.delete(f'/api/ems/employees/{uid}/exclude').status_code, 200)
        self.assertEqual(self.preview(uid)['user_id'], uid)
        self.actor = self.users[2]
        self.assertEqual(self.client.put(f'/api/ems/employees/{uid}/exclude',
            json=dict(password='SyntheticPassword123', confirmation='REMOVE')).status_code, 403)

    def test_ems_changes_preserve_other_projects_and_attendance(self):
        uid = self.users[2].id
        self.actor.password_hash = auth.hash_password('SyntheticPassword123')
        self.db.add(models.Store(name='Synthetic shared outlet', code='SYN', status='Active'))
        self.db.add(models.Brand(name='Synthetic shared brand'))
        self.db.add(models.IdentityCard(user_id=uid, employee_id='SHARED-UNCHANGED',
            employee_name='Synthetic employee', designation='Employee', mobile='12345'))
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=date(2026, 9, 1),
            checkin_at=datetime(2026, 9, 1, 9), checkout_at=datetime(2026, 9, 1, 18)))
        self.db.add(models.AttendanceLeave(user_id=uid, leave_date=date(2026, 9, 2), created_by=self.actor.id))
        self.db.commit()
        shared_tables = [table for table in Base.metadata.sorted_tables
                         if not table.name.startswith('ems_') and table.name != 'users']
        def snapshot():
            return {table.name: self.db.execute(table.select()).all() for table in shared_tables}
        before = snapshot()
        original_users = {r.id: {c.name: getattr(r, c.name) for c in models.User.__table__.columns}
                          for r in self.db.query(models.User).all()}
        self.assertEqual(self.setup_salary(uid).status_code, 200)
        self.assertEqual(snapshot(), before)
        earning = self.client.post('/api/ems/earnings', json=dict(user_id=uid,
            month='2026-09', kind='bonus', amount='100', note='Synthetic approval'))
        self.assertEqual(earning.status_code, 201)
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.client.put(f'/api/ems/employees/{uid}/exclude',
            json=dict(password='SyntheticPassword123', confirmation='REMOVE')).status_code, 200)
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.client.delete(f'/api/ems/employees/{uid}/exclude').status_code, 200)
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.client.request('DELETE', f'/api/ems/employees/{uid}',
            json=dict(password='SyntheticPassword123', confirmation='DELETE')).status_code, 200)
        self.assertEqual(snapshot(), before)
        self.db.expire_all()
        expected_users = original_users
        expected_users[uid]['ems_deleted'] = True
        actual_users = {r.id: {c.name: getattr(r, c.name) for c in models.User.__table__.columns}
                        for r in self.db.query(models.User).all()}
        self.assertEqual(actual_users, expected_users)

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
        self.assertEqual(len(result), 3)
        self.assertEqual({r['category'] for r in result}, {'ids_emp'})
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

    def test_ac_salary_includes_only_service_managers_and_coordinator(self):
        added = {}
        for role in ('Service Manager A', 'Service Manager B', 'ServiceCoordinator', 'AC Helper A', 'AC Helper B'):
            employee = models.User(username=role, full_name=role, email=role+'@test.local',
                                   password_hash='unused', role=role, status='Active')
            self.db.add(employee)
            self.db.flush()
            added[role] = employee.id
        self.db.commit()
        rows = self.client.get('/api/ems/salary-preview?month=2026-09').json()['rows']
        ids = {row['user_id'] for row in rows}
        for role, uid in added.items():
            self.assertEqual(uid in ids, role in ('Service Manager A', 'Service Manager B', 'ServiceCoordinator'))
        for employee in self.users[3:5]:
            self.assertNotIn(employee.id, ids)
            self.assertEqual(self.setup_salary(employee.id).status_code, 404)
        self.assertEqual(self.setup_salary(added['Service Manager A']).status_code, 200)
        self.assertEqual(self.setup_salary(added['ServiceCoordinator']).status_code, 200)

    def test_salary_access_is_only_admin_and_hr(self):
        reads = ('salary-preview?month=2026-09', 'salary-profiles',
                 'salary-slips/1', 'payroll', 'earnings')
        writes = (('POST', 'salary-profiles'), ('POST', 'salary-publish'),
                  ('POST', 'payroll'), ('PUT', 'payroll/1/paid'),
                  ('POST', 'earnings'), ('PUT', 'earnings/1/void'))
        self.actor = self.users[0]
        for role in ('Owner', 'Employee', 'AC Technician A', 'AC Technician B',
                     'BrandPartner', 'Accounts', 'MISExecutive', 'CEO', 'Director'):
            self.actor.role = role
            for path in reads:
                with self.subTest(role=role, path=path):
                    self.assertEqual(self.client.get('/api/ems/'+path).status_code, 403)
            for method, path in writes:
                with self.subTest(role=role, method=method, path=path):
                    self.assertEqual(self.client.request(method, '/api/ems/'+path, json={}).status_code, 403)
        for role in ('Admin', 'HR'):
            self.actor.role = role
            for path in reads:
                with self.subTest(role=role, path=path):
                    self.assertEqual(self.client.get('/api/ems/'+path).status_code,
                                     404 if path == 'salary-slips/1' else 200)

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
        self.assertEqual(row['counts']['weekoff'],4)
        self.assertEqual(row['counts']['absent'],26)
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

    def test_legacy_calendar_profile_uses_thirty_day_basis(self):
        uid = self.users[2].id
        self.setup_salary(effective_month='2026-08', divisor='calendar')
        profile = self.db.query(M.EMSSalaryProfile).filter_by(user_id=uid).one()
        self.assertEqual(profile.divisor, '30')
        profile.divisor = 'calendar'
        for day in range(2, 32):
            self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=date(2026, 8, day),
                                               checkin_at=datetime(2026, 8, day, 9)))
        self.db.commit()
        row = self.preview(month='2026-08')
        self.assertEqual(row['divisor'], '30')
        self.assertEqual(row['unpaid_days'], 1)
        self.assertEqual(row['basic'], 2900000)
        self.assertEqual(row['allowances'], 290000)

    def test_salary_counts_match_daily_attendance(self):
        uid = self.users[2].id
        self.db.add(models.IdentityCard(user_id=uid, employee_id='MATCH-001', employee_name='Employee',
                                       designation='Sales', joining_date=date(2026, 9, 15)))
        self.db.add(models.AttendanceRecord(user_id=uid, attendance_date=date(2026, 9, 6),
                                           checkin_at=datetime(2026, 9, 6, 9)))
        self.db.add(models.AttendanceLeave(user_id=uid, leave_date=date(2026, 9, 6), created_by=self.actor.id))
        self.db.add(models.AttendanceLeave(user_id=uid, leave_date=date(2026, 9, 13), created_by=self.actor.id))
        self.db.commit()
        daily = self.client.get('/api/ems/attendance-summary?month=2026-09').json()
        # The daily endpoint wraps rows in its response.
        daily = daily['rows']
        expected = {'Present': 0, 'Absent': 0, 'Week Off': 0, 'Leave': 0, 'Upcoming': 0}
        for day in daily:
            if day['user_id'] == uid:
                expected[day['status']] += 1
        row = self.preview()
        for key, label in [('present', 'Present'), ('absent', 'Absent'), ('weekoff', 'Week Off'),
                           ('leave', 'Leave'), ('upcoming', 'Upcoming')]:
            self.assertEqual(row['counts'][key], expected[label])
        self.assertEqual(row['counts']['present'], 1)
        self.assertEqual(row['counts']['leave'], 1)

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
