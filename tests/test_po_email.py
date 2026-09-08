import base64
import json
import unittest
from email.mime.text import MIMEText
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from po_email import send_gmail


class GmailTransportTests(unittest.TestCase):
    settings = dict(GMAIL_CLIENT_ID='client', GMAIL_CLIENT_SECRET='secret',
                    GMAIL_REFRESH_TOKEN='refresh', GMAIL_SENDER='sender@gmail.com')

    def test_missing_configuration_does_not_call_google(self):
        with patch.dict('os.environ', {}, clear=True), patch('po_email.urlopen') as network:
            self.assertTrue(send_gmail(MIMEText('PO')).startswith('Not sent:'))
            network.assert_not_called()

    def test_sends_mime_over_https_with_configured_sender(self):
        message = MIMEText('Purchase order items')
        message['From'] = 'old@example.com'
        message['To'] = 'vendor@example.com'
        with patch.dict('os.environ', self.settings, clear=True), patch('po_email.urlopen', side_effect=[
            BytesIO(b'{"access_token":"access"}'), BytesIO(b'{"id":"message-id"}')
        ]) as network:
            self.assertEqual(send_gmail(message), 'Accepted by Gmail for sending.')
            request = network.call_args_list[1].args[0]
            self.assertEqual(request.full_url, 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send')
            decoded = base64.urlsafe_b64decode(json.loads(request.data)['raw']).decode()
            self.assertIn('From: sender@gmail.com', decoded)
            self.assertIn('To: vendor@example.com', decoded)
            self.assertNotIn('old@example.com', decoded)

    def test_uncertain_delivery_is_not_retried(self):
        with patch.dict('os.environ', self.settings, clear=True), patch('po_email.urlopen', side_effect=[
            BytesIO(b'{"access_token":"access"}'), URLError('connection lost')
        ]) as network:
            self.assertIn('Check Sent mail', send_gmail(MIMEText('PO')))
            self.assertEqual(network.call_count, 2)


if __name__ == '__main__':
    unittest.main()
