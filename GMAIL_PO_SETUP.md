# Purchase Order email on Render Free

The existing **Send PO** action supports Gmail API over HTTPS. It sends the
existing PO text and item list, not a PDF attachment. Existing Admin/MIS access
and Approved/Ordered status requirements remain in effect.

## Authorize the trial sender

1. Sign in to Google Cloud Console and create/select a project. Enable **Gmail API**.
2. Configure Google Auth Platform branding and an **External** audience. While
   testing, add `singhankur7521@gmail.com` as a test user.
3. Add only `https://www.googleapis.com/auth/gmail.send` under Data Access.
4. Create an OAuth client of type **Desktop app** and download its client JSON.
   Keep that file outside the repository. Authorization runs on your computer,
   so no Render callback URL is required.
5. On a computer with Python, run from this project:

   ```powershell
   py -m pip install google-auth-oauthlib
   py scripts/connect_gmail.py
   ```

6. Select **singhankur7521@gmail.com** in the browser and grant send permission.
   The script saves `.env.gmail` locally (already excluded by `.gitignore`).
   Never commit the downloaded OAuth JSON or share tokens in chat.
7. Copy the values into your Render service's **Environment** settings:

   ```text
   PO_EMAIL_PROVIDER=gmail
   GMAIL_SENDER=singhankur7521@gmail.com
   GMAIL_CLIENT_ID=<from .env.gmail>
   GMAIL_CLIENT_SECRET=<from .env.gmail>
   GMAIL_REFRESH_TOKEN=<from .env.gmail>
   ```

   If entering each field manually, omit surrounding quotes. Deploy the updated
   code. SMTP_PASSWORD is not used for PO mail in Gmail mode.

## Test and replace the sender

Create a trial PO with only addresses you control. The endpoint combines the
brand email book, supplier email book, and the PO supplier address: check all
three before pressing **Send PO**. Verify Gmail Sent mail and receipt. API
acceptance is not proof of inbox delivery. No emails are sent by the setup script.

Google External apps in Testing generally have refresh tokens that expire after
seven days with the Gmail send scope. Reauthorize for another trial, or configure
production publishing and satisfy Google's applicable consent/verification rules.

For a company Gmail/Google Workspace mailbox, authorize that mailbox and replace
GMAIL_SENDER and its OAuth credentials together. Changing only the From address
does not authorize a different mailbox. For non-Google company mail, configure a
provider-specific HTTPS transport, or use SMTP on hosting that permits it.

The application does not automatically retry a Gmail send with an uncertain
response. Check Sent mail before retrying. Password-reset SMTP is separate and
is not changed by PO_EMAIL_PROVIDER.

References:
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/identity/protocols/oauth2#expiration
