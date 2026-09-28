from pathlib import Path
import unittest

from jose import jwt

import auth


class PersistentLoginTests(unittest.TestCase):
    def test_access_token_has_no_expiration_claim(self):
        token = auth.create_access_token({"user_id": 1, "role": "Admin", "session_version": 1})
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])

        self.assertEqual(payload["user_id"], 1)
        self.assertNotIn("exp", payload)

    def test_attendance_page_does_not_require_tab_session_marker(self):
        html = Path("static/attendance.html").read_text(encoding="utf-8")

        self.assertNotIn("activeLoginSession", html)

    def test_login_page_resumes_existing_saved_session(self):
        html = Path("static/login.html").read_text(encoding="utf-8")

        self.assertIn("resumeExistingSession", html)
        self.assertNotIn("['token', 'role', 'username'].forEach(key => localStorage.removeItem(key));", html)


if __name__ == "__main__":
    unittest.main()
