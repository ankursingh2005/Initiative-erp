"""Attendance role and lightweight history regression tests; isolated SQLite only."""
from datetime import datetime, timezone
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
        for role in ('ACTechnicianA', 'ACTechnicianB', 'AC Helper'):
            with self.subTest(role=role):
                self.db.query(models.AttendanceRecord).delete()
                self.employee.role, self.employee.store_id = role, None
                record = main.save_attendance(self.payload(), self.db, self.employee)
                self.assertEqual(record.store_id, self.stores[1].id)
                self.assertGreater(record.checkin_distance_m, 100)
                record = main.save_attendance(self.payload('checkout'), self.db, self.employee)
                self.assertIsNotNone(record.checkout_at)

    def test_regular_employee_still_requires_geofence(self):
        self.employee.role = 'Employee'
        with self.assertRaises(HTTPException) as error:
            main.save_attendance(self.payload(), self.db, self.employee)
        self.assertEqual(error.exception.status_code, 403)

    def test_history_skips_selfie_loading(self):
        self.employee.role = 'ACTechnicianA'
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
        self.employee.role, self.employee.store_id = 'AC Helper', None
        record = main.save_attendance(self.payload(), self.db, self.employee)
        response = main.attendance_admin_summary(store_id=None, from_date=record.attendance_date,
            to_date=record.attendance_date, db=self.db, current_user=self.actor)
        row = next(row for row in response['rows'] if row['user_id'] == self.employee.id)
        self.assertEqual(row['outlet_id'], self.stores[1].id)
        self.assertEqual(row['outlet_name'], self.stores[1].name)
        self.assertEqual(row['outlet_abbreviation'], self.stores[1].name)
        self.assertIsNotNone(row['current_distance_from_store_m'])

    def test_inaccurate_live_updates_are_skipped_without_overwriting_location(self):
        self.employee.role = 'AC Helper'
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
