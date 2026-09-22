"""Attendance role and lightweight history regression tests; isolated SQLite only."""
from datetime import datetime, timezone
import unittest
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
        for role in ('ACTechnicianA', 'ACTechnicianB'):
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
