import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import auth
import models
import password_reset as recovery


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = models.User(username='shared', email='user@example.com',
                                password_hash=auth.hash_password('original-password'),
                                role='StoreManager', status='Active')
        self.other = models.User(username='shared', email='other@example.com',
                                 password_hash='unchanged', role='Admin', status='Active')
        self.db.add_all([self.user, self.other])
        self.db.commit()
        self.settings = patch.dict('os.environ', {
            'PO_EMAIL_PROVIDER': 'gmail', 'GMAIL_SENDER': 'sender@example.com',
            'GMAIL_CLIENT_ID': 'test', 'GMAIL_CLIENT_SECRET': 'test',
            'GMAIL_REFRESH_TOKEN': 'test',
        }, clear=True)
        self.settings.start()
        self.sender = patch('password_reset.send_gmail', return_value='Accepted by Gmail for sending.').start()
        patch('password_reset.secrets.randbelow', return_value=123456).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def request(self, email='user@example.com'):
        return recovery.request_reset(SimpleNamespace(identifier=email), self.db)

    def confirm(self, code='123456', email='user@example.com', password='replacement-password'):
        return recovery.confirm_reset(SimpleNamespace(identifier=email, code=code, new_password=password), self.db)

    def assert_rejected(self, callback):
        with self.assertRaises(HTTPException) as error:
            callback()
        self.assertEqual(error.exception.status_code, 400)

    def test_email_selects_individual_user_and_code_is_single_use(self):
        self.request(' USER@EXAMPLE.COM ')
        self.assertEqual(self.sender.call_args.args[0]['To'], 'user@example.com')
        self.assertNotEqual(self.user.reset_token, '123456')
        self.confirm()
        self.db.refresh(self.user)
        self.assertTrue(auth.verify_password('replacement-password', self.user.password_hash))
        self.assertFalse(auth.verify_password('original-password', self.user.password_hash))
        self.assertEqual(self.other.password_hash, 'unchanged')
        self.assert_rejected(self.confirm)

    def test_unknown_username_and_inactive_accounts_do_not_send(self):
        self.user.status = 'Inactive'
        self.db.commit()
        for email in ['user@example.com', 'missing@example.com', 'shared']:
            self.assertEqual(self.request(email), recovery.REQUEST_MESSAGE)
        self.sender.assert_not_called()

    def test_cooldown_and_hourly_limit(self):
        self.request()
        self.request()
        self.assertEqual(self.sender.call_count, 1)
        for _ in range(5):
            self.user.reset_requested_at = datetime.utcnow() - timedelta(seconds=61)
            self.db.commit()
            self.request()
        self.assertEqual(self.sender.call_count, 5)
        self.user.reset_request_window = datetime.utcnow() - timedelta(hours=2)
        self.db.commit()
        self.request()
        self.assertEqual(self.sender.call_count, 6)

    def test_five_wrong_guesses_block_even_the_correct_code(self):
        self.request()
        for _ in range(5):
            self.assert_rejected(lambda: self.confirm('999999'))
        self.assert_rejected(self.confirm)

    def test_expired_code_is_rejected(self):
        self.request()
        self.user.reset_token_expires = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        self.assert_rejected(self.confirm)

    def test_account_disabled_after_request_cannot_reset(self):
        self.request()
        self.user.status = 'Inactive'
        self.db.commit()
        self.assert_rejected(self.confirm)

    def test_resend_invalidates_old_code(self):
        self.request()
        self.user.reset_requested_at = datetime.utcnow() - timedelta(seconds=61)
        self.db.commit()
        with patch('password_reset.secrets.randbelow', return_value=654321):
            self.request()
        self.assert_rejected(self.confirm)
        self.confirm('654321')

    def test_delivery_failure_clears_code_and_keeps_send_limit(self):
        self.sender.return_value = 'Not sent: provider unavailable'
        with self.assertRaises(HTTPException) as error:
            self.request()
        self.assertEqual(error.exception.status_code, 503)
        self.db.refresh(self.user)
        self.assertIsNone(self.user.reset_token)
        self.assertEqual(self.user.reset_request_count, 1)

    def test_missing_configuration_does_not_send(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(HTTPException) as error:
                self.request()
        self.assertEqual(error.exception.status_code, 503)
        self.sender.assert_not_called()

    def test_password_length_validation(self):
        self.request()
        self.assert_rejected(lambda: self.confirm(password='short'))
        self.assert_rejected(lambda: self.confirm(password='x' * 73))


if __name__ == '__main__':
    unittest.main()
