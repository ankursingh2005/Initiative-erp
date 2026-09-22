"""Dashboard and export category filters must select the same employees."""
import unittest
import test_attendance_outlets as fixtures
from attendance_exports import export_rows

main, models = fixtures.main, fixtures.models
tearDownModule = fixtures.tearDownModule


class AttendanceCategoryTests(unittest.TestCase):
    setUp = fixtures.AttendanceOutletTests.setUp
    tearDown = fixtures.AttendanceOutletTests.tearDown

    def test_each_category_filters_counts_rows_and_exports(self):
        today = main.india_today()
        self.actor.status = 'Inactive'
        for index, role in enumerate(['Employee', 'ACTechnicianA', 'ACTechnicianB']):
            self.db.add(models.User(username=role, email=f'{index}@example.test', role=role,
                status='Active', password_hash='unused', store_id=self.stores[0].id))
        self.db.commit()
        for category, username in [('ids_emp', 'Employee'), ('brand_pro', 'employee'),
                                   ('ac_retails', 'ACTechnicianA'), ('ac_projects', 'ACTechnicianB')]:
            with self.subTest(category=category):
                data = main.attendance_admin_summary(store_id=None, from_date=today, to_date=today,
                    db=self.db, current_user=self.actor, emp_category=category)
                self.assertEqual(data['total'], 1)
                self.assertEqual([r['username'] for r in data['rows']], [username])
                rows = export_rows(self.db, today, today, emp_category=category)
                self.assertEqual([r[1] for r in rows], [username])
                empty = main.attendance_admin_summary(store_id=self.stores[1].id,
                    from_date=today, to_date=today, db=self.db, current_user=self.actor,
                    emp_category=category)
                self.assertEqual(empty['total'], 0)
