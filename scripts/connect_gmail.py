"""Run locally to authorize the PO sender; never deploy this setup script."""
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow


def main():
    sender = input('Gmail sender [singhankur7521@gmail.com]: ').strip() or 'singhankur7521@gmail.com'
    client_file = input('Path to downloaded Google Desktop OAuth client JSON: ').strip().strip('"')
    flow = InstalledAppFlow.from_client_secrets_file(client_file, scopes=[
        'https://www.googleapis.com/auth/gmail.send'])
    credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent', login_hint=sender)
    if not credentials.refresh_token:
        raise SystemExit('Google did not return a refresh token. Revoke the previous app grant and authorize again.')
    output = Path('.env.gmail')
    # Exclusive creation avoids overwriting an existing mailbox configuration.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        for key, value in {
            'PO_EMAIL_PROVIDER': 'gmail', 'GMAIL_SENDER': sender,
            'GMAIL_CLIENT_ID': credentials.client_id,
            'GMAIL_CLIENT_SECRET': credentials.client_secret,
            'GMAIL_REFRESH_TOKEN': credentials.refresh_token,
        }.items():
            handle.write(f'{key}={json.dumps(value)}\n')
    print('Saved .env.gmail (git-ignored). Copy its values into Render Environment; do not share this file.')


if __name__ == '__main__':
    main()
