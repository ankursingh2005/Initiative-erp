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

    def test_named_accounts_override_role_group_without_changing_roles(self):
        today = main.india_today()
        accounts = [
            ('Zubair', 'akhtarnoor3112@gmail.com', 'ServiceManager'),
            ('Chandra dutt sood', 'cdsood@gmail.com', 'ServiceManager'),
            ('Jagriti', 'jagritiawasthi123@gmail.com', 'Other'),
            ('Other manager', 'other-manager@example.test', 'ServiceManager'),
        ]
        for name, email, role in accounts:
            self.db.add(models.User(username=name, email=email, role=role,
                status='Active', password_hash='unused'))
        self.db.commit()
        for category, expected in [('ac_projects', {'Zubair'}),
                                   ('ac_retails', {'Chandra dutt sood', 'Jagriti'})]:
            result = main.attendance_admin_summary(store_id=None, from_date=today, to_date=today,
                db=self.db, current_user=self.actor, emp_category=category)
            self.assertEqual({row['username'] for row in result['rows']}, expected)
            self.assertEqual(result['total'], len(expected))
            self.assertEqual({row[1] for row in export_rows(self.db, today, today, emp_category=category)}, expected)
        ids = {row[1] for row in export_rows(self.db, today, today, emp_category='ids_emp')}
        self.assertFalse(ids & {'Zubair', 'Chandra dutt sood', 'Jagriti'})
        self.assertIn('Other manager', ids)
        for name, email, role in accounts:
            self.assertEqual(self.db.query(models.User).filter_by(email=email).one().role, role)

    def test_each_category_filters_counts_rows_and_exports(self):
        today = main.india_today()
        self.actor.status = 'Inactive'
        for index, role in enumerate(['Employee', 'ACTechnicianA', 'ACTechnicianB']):
            self.db.add(models.User(username=role, email=f'{index}@example.test', role=role,
                status='Active', password_hash='unused', store_id=self.stores[0].id))
        self.db.commit()
        for category, username in [('ids_emp', 'Employee'), ('brand_pro', 'employee'),
                                   ('ac_retails', 'ACTechnicianB'), ('ac_projects', 'ACTechnicianA')]:
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
