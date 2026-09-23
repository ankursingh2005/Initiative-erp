"""Historical weekly schedules must survive repeated profile edits."""
import unittest
from datetime import date
from types import SimpleNamespace
from attendance_history import change_weekoff, weekoff_on


class AttendanceScheduleHistoryTests(unittest.TestCase):
    def test_changes_and_clearing_preserve_prior_days(self):
        user = SimpleNamespace(weekoff_day='Monday', weekoff_history=None)
        change_weekoff(user, 'Wednesday', date(2026, 9, 23))
        self.assertEqual(weekoff_on(user, date(2026, 9, 21)), 'Monday')
        self.assertEqual(weekoff_on(user, date(2026, 9, 23)), 'Wednesday')
        change_weekoff(user, None, date(2026, 10, 1))
        self.assertEqual(weekoff_on(user, date(2026, 9, 30)), 'Wednesday')
        self.assertIsNone(weekoff_on(user, date(2026, 10, 1)))

    def test_same_day_edits_keep_original_schedule(self):
        user = SimpleNamespace(weekoff_day=None, weekoff_history=None)
        change_weekoff(user, 'Monday', date(2026, 9, 23))
        change_weekoff(user, 'Friday', date(2026, 9, 23))
        self.assertIsNone(weekoff_on(user, date(2026, 9, 22)))
        self.assertEqual(weekoff_on(user, date(2026, 9, 23)), 'Friday')
        saved = user.weekoff_history
        change_weekoff(user, 'Friday', date(2026, 10, 1))
        self.assertEqual(user.weekoff_history, saved)
