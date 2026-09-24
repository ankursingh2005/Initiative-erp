"""Dashboard and export category filters must select the same employees."""
import unittest
import test_attendance_outlets as fixtures
from attendance_exports import export_rows

main, models = fixtures.main, fixtures.models
tearDownModule = fixtures.tearDownModule


class AttendanceCategoryTests(unittest.TestCase):
    setUp = fixtures.AttendanceOutletTests.setUp
    tearDown = fixtures.AttendanceOutletTests.tearDown

    def test_dashboard_returns_assigned_brand_names_for_daily_and_range_views(self):
        from datetime import timedelta
        today = main.india_today()
        for name in ['Samsung', 'LG']:
            brand = models.Brand(name=name)
            self.db.add(brand)
            self.db.flush()
            self.db.add(models.UserBrand(user_id=self.employee.id, brand_id=brand.id))
        self.db.commit()
        for end in [today, today + timedelta(days=1)]:
            data = main.attendance_admin_summary(store_id=None, from_date=today, to_date=end,
                db=self.db, current_user=self.actor, emp_category='brand_pro')
            row = data['rows'][0]
            self.assertEqual(row['username'], self.employee.username)
            self.assertEqual(row['brand_names'], ['LG', 'Samsung'])
            self.assertEqual(row['promoter_brand'], 'LG, Samsung')

    def test_all_six_roles_follow_category_regardless_of_email(self):
        from attendance_access import can_view_attendance
        from types import SimpleNamespace
        today = main.india_today()
        expected = {}
        for suffix, category in [('A', 'ac_projects'), ('B', 'ac_retails')]:
            expected[category] = set()
            for prefix in ['Service Manager', 'AC Technician', 'AC Helper']:
                role = prefix + ' ' + suffix
                user = models.User(username=role, email=role.replace(' ', '')+'@example.test', role=role, status='Active', password_hash='unused')
                self.db.add(user)
                self.db.flush()
                expected[category].add(user.id)
        self.db.commit()
        for suffix, category in [('A', 'ac_projects'), ('B', 'ac_retails')]:
            actor = SimpleNamespace(id=-1, role='Service Manager '+suffix, email='unlisted@example.test', store_id=None)
            data = main.attendance_admin_summary(store_id=None, from_date=today, to_date=today, db=self.db, current_user=actor)
            self.assertEqual({row['user_id'] for row in data['rows']}, expected[category])
            self.assertEqual({row[0] for row in export_rows(self.db, today, today, emp_category=category)}, expected[category])
            for user in self.db.query(models.User).all():
                self.assertEqual(can_view_attendance(actor, user), user.id in expected[category])

    def test_each_category_filters_counts_rows_and_exports(self):
        today = main.india_today()
        self.actor.status = 'Inactive'
        for index, role in enumerate(['Employee', 'AC Technician A', 'AC Technician B']):
            self.db.add(models.User(username=role, email=f'{index}@example.test', role=role,
                status='Active', password_hash='unused', store_id=self.stores[0].id))
        self.db.commit()
        for category, username in [('ids_emp', 'Employee'), ('brand_pro', 'employee'),
                                   ('ac_retails', 'AC Technician B'), ('ac_projects', 'AC Technician A')]:
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


    def test_ac_helpers_belong_to_projects_and_are_visible_to_noor(self):
        from types import SimpleNamespace
        from attendance_access import can_view_attendance
        from attendance_categories import filter_manager_employees, manager_employee_visible
        today = main.india_today()
        helper = models.User(username='Project Helper', email='helper@example.test', role='AC Helper A', status='Active', password_hash='unused', store_id=self.stores[0].id)
        self.db.add(helper)
        self.db.commit()
        noor = SimpleNamespace(id=-1, role='Service Manager A', email='akhtarnoor3112@gmail.com', store_id=None)
        for actor in (self.actor, noor):
            data = main.attendance_admin_summary(store_id=None, from_date=today, to_date=today, db=self.db, current_user=actor, emp_category='ac_projects')
            self.assertIn(helper.id, {row['user_id'] for row in data['rows']})
        self.assertIn(helper.id, {row[0] for row in export_rows(self.db, today, today, emp_category='ac_projects')})
        for category in ('ids_emp', 'ac_retails', 'brand_pro'):
            self.assertNotIn(helper.id, {row[0] for row in export_rows(self.db, today, today, emp_category=category)})
        self.assertTrue(can_view_attendance(noor, helper))
        self.assertFalse(manager_employee_visible(helper))
        self.assertNotIn(helper.id, {user.id for user in filter_manager_employees(self.db.query(models.User)).all()})
