"""Weekly-off selections must survive database reload and profile serialization."""
import unittest
import test_attendance_outlets as fixtures

main, schemas = fixtures.main, fixtures.schemas
tearDownModule = fixtures.tearDownModule


class WeekoffPreferenceTests(unittest.TestCase):
    setUp = fixtures.AttendanceOutletTests.setUp
    tearDown = fixtures.AttendanceOutletTests.tearDown

    def register_routes(self):
        app = self.client.app
        app.get('/api/me', response_model=schemas.MyProfileOut)(main.get_my_profile)
        app.put('/api/me/weekoff')(main.update_my_weekoff)

    def test_admin_days_survive_refresh(self):
        self.register_routes()
        days = ['Saturday', 'Sunday']
        response = self.client.put('/api/me/weekoff', json={'weekoff_days': days})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        response = self.client.get('/api/me')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['weekoff_days'], days)
        self.assertEqual(response.json()['weekoff_day'], 'Saturday')

    def test_other_roles_keep_single_day_only(self):
        self.register_routes()
        for role in ('Employee', 'HR', 'Owner', 'CategoryManager'):
            with self.subTest(role=role):
                self.actor.role = role
                response = self.client.put('/api/me/weekoff', json={'weekoff_days': ['Saturday', 'Sunday']})
                self.assertEqual(response.status_code, 403)
                response = self.client.put('/api/me/weekoff', json={'weekoff_day': 'Monday'})
                self.assertEqual(response.status_code, 200, response.text)
                self.db.expire_all()
                self.assertEqual(self.client.get('/api/me').json()['weekoff_days'], ['Monday'])
