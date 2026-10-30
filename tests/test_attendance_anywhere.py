"""Attendance role and lightweight history regression tests; isolated SQLite only."""
from datetime import datetime, timezone, timedelta
import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import inspect
import test_attendance_outlets as fixtures

main, models, schemas = fixtures.main, fixtures.models, fixtures.schemas
tearDownModule = fixtures.tearDownModule


class AnywhereAttendanceTests(unittest.TestCase):
    setUp = fixtures.AttendanceOutletTests.setUp
    tearDown = fixtures.AttendanceOutletTests.tearDown

    def payload(self, action='checkin'):
        return schemas.AttendanceCreate(action=action, captured_at=datetime.now(timezone.utc),
            latitude=28, longitude=82, accuracy_m=10, distance_m=0, selfie='test-selfie')

    def test_both_technicians_can_punch_in_and_out_without_assignment(self):
        for role in ('Service Manager A', 'Service Manager B', 'AC Technician A', 'AC Technician B', 'AC Helper A', 'AC Helper B'):
            with self.subTest(role=role):
                self.db.query(models.AttendanceRecord).delete()
                self.employee.role, self.employee.store_id = role, None
                record = main.save_attendance(self.payload(), self.db, self.employee)
                self.assertEqual(record.store_id, self.stores[1].id)
                self.assertGreater(record.checkin_distance_m, 100)
                record = main.save_attendance(self.payload('checkout'), self.db, self.employee)
                self.assertIsNotNone(record.checkout_at)

    def test_new_punches_preserve_history_and_other_project_records(self):
        self.employee.role = 'AC Helper A'
        previous_day = main.india_today() - timedelta(days=1)
        historical = models.AttendanceRecord(user_id=self.employee.id,
            attendance_date=previous_day, store_id=self.stores[0].id,
            checkin_at=datetime.combine(previous_day, datetime.min.time()).replace(hour=9),
            checkout_at=datetime.combine(previous_day, datetime.min.time()).replace(hour=18),
            checkin_selfie='synthetic old punch in', checkout_selfie='synthetic old punch out')
        self.db.add(historical)
        self.db.commit()
        original = {column.name: getattr(historical, column.name)
                    for column in models.AttendanceRecord.__table__.columns}
        unrelated = [table for table in models.Base.metadata.sorted_tables
                     if table.name != 'attendance_records']
        def snapshot():
            return {table.name: self.db.execute(table.select()).all() for table in unrelated}
        before = snapshot()
        current = main.save_attendance(self.payload(), self.db, self.employee)
        main.save_attendance(self.payload('checkout'), self.db, self.employee)
        self.db.expire_all()
        self.assertEqual(snapshot(), before)
        self.db.refresh(historical)
        self.assertEqual({column.name: getattr(historical, column.name)
                          for column in models.AttendanceRecord.__table__.columns}, original)
        self.assertNotEqual(current.id, historical.id)
        self.assertEqual(self.db.query(models.AttendanceRecord).count(), 2)

    def test_stale_future_and_blank_selfie_punches_are_rejected(self):
        self.employee.role = 'AC Helper A'
        now = datetime.now(timezone.utc)
        for captured in (now-timedelta(minutes=3), now+timedelta(minutes=1)):
            with self.assertRaises(HTTPException) as error:
                main.save_attendance(self.payload().model_copy(update={'captured_at': captured}), self.db, self.employee)
            self.assertEqual(error.exception.status_code, 422)
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload().model_copy(update={'selfie': '   '}), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(self.db.query(models.AttendanceRecord).count(), 0)

    def test_duplicate_punch_does_not_overwrite_original(self):
        self.employee.role = 'AC Helper A'
        original = main.save_attendance(self.payload(), self.db, self.employee)
        stamp = original.checkin_at
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload().model_copy(update={'selfie': 'different selfie'}), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 409)
        self.db.refresh(original)
        self.assertEqual(original.checkin_at, stamp)
        self.assertEqual(original.checkin_selfie, 'test-selfie')
        self.assertEqual(self.db.query(models.AttendanceRecord).count(), 1)

    def test_checkout_requires_checkin_and_cannot_precede_it(self):
        self.employee.role = 'AC Helper A'
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload('checkout'), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 409)
        now = datetime.now(timezone.utc)
        record = main.save_attendance(self.payload().model_copy(update={'captured_at': now+timedelta(seconds=10)}), self.db, self.employee)
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload('checkout').model_copy(update={'captured_at': now}), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 409)
        self.db.refresh(record)
        self.assertIsNone(record.checkout_at)

    def test_concurrent_punches_create_one_daily_record(self):
        import tempfile
        from pathlib import Path
        from threading import Barrier
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        with tempfile.TemporaryDirectory(prefix='attendance-concurrency-') as directory:
            engine = create_engine('sqlite:///' + (Path(directory)/'isolated.db').as_posix(),
                connect_args={'check_same_thread': False, 'timeout': 10})
            models.Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine)
            try:
                with sessions() as db:
                    employee = models.User(username='Synthetic staff', email='synthetic@tests.invalid',
                        role='AC Helper A', status='Active', password_hash='unused')
                    db.add(employee)
                    db.add(models.Store(name='Synthetic outlet', status='Active', latitude=0, longitude=0))
                    db.commit(); uid = employee.id
                for action in ('checkin', 'checkout'):
                    barrier = Barrier(2)
                    def punch(_):
                        with sessions() as db:
                            user = db.get(models.User, uid)
                            barrier.wait(timeout=10)
                            try:
                                main.save_attendance(self.payload(action), db, user)
                                return 200
                            except HTTPException as error:
                                db.rollback()
                                return error.status_code
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        self.assertEqual(sorted(pool.map(punch, range(2))), [200, 409])
                with sessions() as db:
                    self.assertEqual(db.query(models.AttendanceRecord).count(), 1)
                    saved = db.query(models.AttendanceRecord).one()
                    self.assertIsNotNone(saved.checkin_at)
                    self.assertIsNotNone(saved.checkout_at)
            finally:
                engine.dispose()

    def test_regular_employee_still_requires_geofence(self):
        self.employee.role = 'Employee'
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload(), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 403)

    def test_history_skips_selfie_loading(self):
        self.employee.role = 'AC Technician A'
        record = main.save_attendance(self.payload(), self.db, self.employee)
        self.db.expire_all()
        rows = main.list_attendance(self.db, self.employee, scope='self', include_selfies=False)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['checkin_selfie'])
        self.assertIn('checkin_selfie', inspect(record).unloaded)
        self.assertIsNotNone(rows[0]['checkin_at'])

    def test_nearest_outlet_and_distance_follow_latest_location(self):
        first, second = self.stores[:2]
        record = SimpleNamespace(checkin_at=datetime(2026, 9, 23, 9), checkout_at=None,
            checkin_latitude=first.latitude, checkin_longitude=first.longitude,
            checkout_latitude=None, checkout_longitude=None, store_id=first.id,
            checkin_distance_m=0, checkout_distance_m=None)
        outlet, distance = main.nearest_attendance_outlet(self.stores, record, None)
        self.assertEqual(outlet.id, first.id)
        self.assertEqual(distance, 0)
        point = SimpleNamespace(captured_at=datetime(2026, 9, 23, 10), latitude=second.latitude,
            longitude=second.longitude, store_id=first.id, distance_from_store_m=100000)
        outlet, distance = main.nearest_attendance_outlet(self.stores, record, point)
        self.assertEqual(outlet.id, second.id)
        self.assertEqual(distance, 0)
        record.checkout_at = datetime(2026, 9, 23, 18)
        record.checkout_latitude, record.checkout_longitude = first.latitude, first.longitude
        outlet, distance = main.nearest_attendance_outlet(self.stores, record, point)
        self.assertEqual(outlet.id, first.id)
        self.assertEqual(distance, 0)
        self.assertEqual(main.nearest_attendance_outlet(self.stores, None, None), (None, None))

    def test_anywhere_summary_displays_nearest_outlet_without_assignment(self):
        self.employee.role, self.employee.store_id = 'AC Helper A', None
        record = main.save_attendance(self.payload(), self.db, self.employee)
        response = main.attendance_admin_summary(store_id=None, from_date=record.attendance_date,
            to_date=record.attendance_date, db=self.db, current_user=self.actor)
        row = next(row for row in response['rows'] if row['user_id'] == self.employee.id)
        self.assertEqual(row['outlet_id'], self.stores[1].id)
        self.assertEqual(row['outlet_name'], self.stores[1].name)
        self.assertEqual(row['outlet_abbreviation'], self.stores[1].name)
        self.assertIsNotNone(row['current_distance_from_store_m'])

    def test_inaccurate_live_updates_are_skipped_without_overwriting_location(self):
        self.employee.role = 'AC Helper A'
        main.save_attendance(self.payload(), self.db, self.employee)
        for accuracy in (None, 0, 5000):
            point = schemas.AttendanceLocationCreate(captured_at=datetime.now(timezone.utc),
                latitude=28, longitude=82, accuracy_m=accuracy)
            result = main.save_attendance_location(point, self.db, self.employee)
            self.assertFalse(result['accepted'])
        self.assertEqual(self.db.query(models.AttendanceLocationPoint).count(), 0)
        point = schemas.AttendanceLocationCreate(captured_at=datetime.now(timezone.utc),
            latitude=28, longitude=82, accuracy_m=10)
        self.assertTrue(main.save_attendance_location(point, self.db, self.employee)['accepted'])
        self.assertEqual(self.db.query(models.AttendanceLocationPoint).count(), 1)
