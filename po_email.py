"""Gmail HTTPS transport. Credentials belong in host environment variables."""
import base64
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def send_gmail(message):
    settings = {name: os.getenv(name, '').strip() for name in (
        'GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN', 'GMAIL_SENDER')}
    if not all(settings.values()):
        return 'Not sent: configure GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN and GMAIL_SENDER on the host.'
    sender = settings['GMAIL_SENDER']
    if '\r' in sender or '\n' in sender or '@' not in sender:
        return 'Not sent: GMAIL_SENDER is invalid.'
    if message.get('From'):
        message.replace_header('From', sender)
    else:
        message['From'] = sender
    try:
        token_request = Request('https://oauth2.googleapis.com/token', data=urlencode({
            'client_id': settings['GMAIL_CLIENT_ID'],
            'client_secret': settings['GMAIL_CLIENT_SECRET'],
            'refresh_token': settings['GMAIL_REFRESH_TOKEN'],
            'grant_type': 'refresh_token',
        }).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with urlopen(token_request, timeout=20) as response:
            access_token = json.load(response)['access_token']
    except (HTTPError, URLError, KeyError, ValueError, TimeoutError):
        return 'Not sent: Gmail authorization failed. Reconnect the sender account and check the Gmail configuration.'
    try:
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
        request = Request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                          data=json.dumps({'raw': raw}).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        if not result.get('id'):
            return 'Not sent: Gmail did not confirm acceptance. Check Sent mail before retrying.'
    except HTTPError as exc:
        return f'Not sent: Gmail rejected the request (HTTP {exc.code}). Check permissions and sending limits.'
    except (URLError, ValueError, TimeoutError):
        return 'Not sent: Gmail delivery could not be confirmed. Check Sent mail before retrying to avoid duplicates.'
    return 'Accepted by Gmail for sending.'
