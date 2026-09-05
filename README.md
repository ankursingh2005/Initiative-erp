# Initiative ERP — IDSPL

Initiative ERP is a web application for employee attendance, outlet incentives, sales schemes, pricing, purchase orders, and business reporting. It uses a Python FastAPI backend and HTML/CSS/JavaScript pages served by the same application.

- **Website:** https://erp.initiative.co.in
- **Live incentive page:** https://erp.initiative.co.in/incentive
- **Hosting:** Render

The website URL and hosting platform above are supplied by the project owner. The technical instructions below describe this repository; they do not confirm the settings or deployed revision of the live Render service.

## Application modules

| Module | Route in this checkout | Features |
| --- | --- | --- |
| Login and signup | `/login`, `/signup` | Account login, invite-code signup, role-based access |
| Home | `/home` | Navigation to available modules |
| Attendance | `/attendance` | GPS and selfie punch-in/out, working hours, weekly off, leave/working status, location tracking, reports and exports |
| Incentives | `/incentive.html` | Monthly sales upload, outlet and category summaries, configurable profit/incentive rates, Excel export |
| Schemes, sales and claims | `/dashboard` | Scheme maintenance, document uploads, sales records, claims and status changes |
| Price list | `/price-list` | Price records, brand filtering and file uploads |
| Purchase orders | `/purchase-orders` | Order creation, status changes, supplier details, email sending and export tracking |
| Analytics | `/analytics` | File upload, staged review/reassignment and dashboard reporting |
| Ageing stock | `/ageing-stock` | Stock workbook upload, classification, reports and export |
| Daily profitability | `/daily-profitability` | Profitability dashboard, item details and downloadable reports |
| Scheme calculator | `/scheme-calculator` | Scheme calculation page and image extraction endpoint |

**Incentive route difference:** the owner's live URL is `/incentive`, but `main.py` currently declares only `/incentive.html`. Use `/incentive.html` locally. Check the deployed revision or routing configuration when investigating a `/incentive` 404; this README does not assume an alias exists.

The project also includes a web app manifest, service worker, offline page, mobile navigation and app icons. Offline behavior varies by feature; verify that attendance reaches the server before treating it as saved.

## Incentive calculation

Upload an `.xlsx` / `.xlsm` workbook or text-based PDF containing monthly outlet sales. The parser supports outlet/category/sale reports, standard monthly sales rows, outlet columns and grouped layouts. Scanned PDF support should not be assumed for this module.

Default rates:

```text
Average profit = Total sales × 7%
Incentive      = Average profit × 2.5%
```

Both rates are editable. For example, sales of 100,000 at the defaults produce profit of 7,000 and incentive of 175. Reports include outlet totals and category breakdowns for HA, HE, MOB, COM, DC and ACC. The download endpoint generates an Excel report with formulas.

The calculation and export APIs allow Admin, Owner, HR, Accounts and MIS Executive accounts.

## Attendance and access

Current attendance policy in the source:

- **Service Manager, AC Technician A, AC Technician B and HR** can punch in and out from any location. A nearby active outlet is used as a reporting reference when available; an assigned outlet is not required by their attendance API.
- Other roles require an assigned outlet with GPS coordinates and must be within its configured radius, capped at 100 metres.
- The attendance page requires GPS and a camera selfie. Location accuracy checks still apply to unrestricted-location roles.
- Punch times are recorded using server Indian Standard Time, rather than trusting the phone clock.
- Working-location uploads require an open attendance record. Duplicate punches and checkout before check-in are rejected.
- Attendance includes personal records, administrative summaries, exports and optional WhatsApp reporting.

Role permissions are enforced per endpoint. Admin, Owner and HR share many administrative permissions, but are not identical: the current user-management guard permits **Admin and HR**, and excludes Owner. Brand Partner accounts have an additional backend restriction to Home and Attendance.

The complete account role list is in `VALID_ROLES` in `main.py`; permission helpers are in `auth.py`. Consult these checks before changing access rules.

## Technology and files

| File or folder | Purpose |
| --- | --- |
| `main.py` | FastAPI app, page/API routes, startup schema updates, reports and integrations |
| `models.py` | SQLAlchemy database models |
| `schemas.py` | API request and response schemas |
| `auth.py` | Password hashing, JWT tokens and role guards |
| `database.py` | Database URL, engine and session setup |
| `scheme_engine.py`, `schemes.py` | Scheme-related calculation and helper code |
| `static/` | HTML pages, JavaScript, styles, icons and supporting assets |
| `requirements.txt` | Python dependencies |
| `.python-version` | Python version declaration: `3.13` |
| `render.yaml` | Render web service and PostgreSQL Blueprint configuration |
| `Procfile` | Uvicorn production start command |
| `deploy/oracle/` | Alternative deployment files; not the stated live hosting setup |

There is no Node frontend build step. Node is useful for checking standalone JavaScript syntax. Python dependencies include FastAPI, Uvicorn, SQLAlchemy, PostgreSQL support, JWT/password tools, OpenPyXL, PDF/image libraries and ReportLab.

## Local development on Windows

Install Python 3.13 and open PowerShell in the repository root. Create the virtual environment on your own computer; do not reuse a copied environment containing another computer's Python paths.

```powershell
cd C:\Users\Ankur\Desktop\IDSPL
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a local `.env` file. Replace the placeholder secrets and invite codes before use:

```dotenv
DATABASE_URL=sqlite:///./scheme_erp_test.db
SECRET_KEY=replace-with-a-long-random-local-secret
SIGNUP_CODE_ADMIN=replace-with-a-local-admin-invite-code
SIGNUP_CODE_UNIVERSAL=replace-with-a-local-staff-invite-code
```

Start the app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open:

- Login: http://localhost:8000/login
- Signup: http://localhost:8000/signup
- Incentives: http://localhost:8000/incentive.html
- API explorer: http://localhost:8000/docs

A new test database has no existing employee accounts. Create test accounts using your local invite codes and supply the assignments required by each role. Do not use production account credentials or a production database for routine tests.

The app loads `.env` before database initialization. Existing process environment variables take precedence. Without `DATABASE_URL`, it uses `sqlite:///./scheme_erp.db`. Startup creates tables, applies built-in schema adjustments and seeds master data, so even starting the app can write to the selected database.

For VS Code, select `.venv\Scripts\python.exe` using **Python: Select Interpreter**. If that executable reports a missing Python path under another Windows user, rename the old environment and create a fresh one using the commands above.

## Render deployment

The project is hosted on Render under `erp.initiative.co.in`. Use the existing Render service for updates; creating another service is only needed for a separate environment.

The repository's deployment commands match [Render's FastAPI setup](https://render.com/docs/deploy-fastapi):

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Python declaration | `.python-version` contains `3.13` |

`render.yaml` declares a service named `idspl` and a PostgreSQL database named `idspl-postgres`. It connects `DATABASE_URL` to that database and generates `SECRET_KEY`. These are Blueprint declarations, not evidence that the existing service uses those exact names or settings. Check the Render dashboard before applying infrastructure changes.

For an update:

1. Validate the change locally using a test database.
2. Commit and push to the branch connected to the existing Render service.
3. Check whether automatic deployment is enabled; otherwise deploy the intended commit through Render.
4. Review build and runtime logs, then verify login and the changed feature on the live domain.

Configure `erp.initiative.co.in` in the service's **Settings → Custom Domains** and use the DNS values Render provides. Render manages HTTPS certificates for verified custom domains. See [Render custom-domain instructions](https://render.com/docs/custom-domains). Existing working DNS does not need to be recreated for normal code updates.

### Database persistence

The Blueprint selects PostgreSQL. Confirm the live service's `DATABASE_URL` in Render; this repository alone cannot establish which database production currently uses.

Render's default filesystem is ephemeral, so a SQLite file outside a persistent disk can be lost on restart or redeployment. See [Render persistent storage](https://render.com/docs/disks). Keep production data in the configured persistent database and maintain backups before schema or bulk-data changes. Local SQLite data is not automatically transferred to PostgreSQL by deploying the code.

## Configuration

Set production values in Render's environment settings. Keep local values in the ignored `.env` file. Do not commit passwords, API tokens or database credentials.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection; defaults to local `scheme_erp.db` |
| `SECRET_KEY` | JWT signing secret; set explicitly in production |
| `SIGNUP_CODE_ADMIN` | Invite code for Admin signup |
| `SIGNUP_CODE_UNIVERSAL` | Invite code for other signup roles |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime; current code defaults to one year |
| `BCRYPT_ROUNDS` | Password hashing work factor; code enforces a minimum of 10 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Outbound email configuration |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Cloud API credentials |
| `WHATSAPP_MIS_RECIPIENTS` | Comma-separated purchase-order notification recipients |
| `WHATSAPP_ATTENDANCE_RECIPIENTS` | Comma-separated attendance-report recipients |
| `WHATSAPP_API_VERSION` | WhatsApp API version override |
| `WHATSAPP_ATTENDANCE_TEMPLATE`, `WHATSAPP_ATTENDANCE_TEMPLATE_LANGUAGE` | Attendance message template configuration |
| `ATTENDANCE_WHATSAPP_CRON_SECRET` | Secret for the scheduled attendance endpoint |
| `ANTHROPIC_API_KEY` | AI extraction for scheme documents, calculator images and supported price-list uploads |
| `XAI_API_KEY`, `OPENAI_API_KEY` | Alternative vision providers for supported price-list image uploads |
| `VISION_PROVIDER` | Price-list vision provider override |
| `PRICE_LIST_ANTHROPIC_MODEL`, `PRICE_LIST_XAI_MODEL`, `PRICE_LIST_OPENAI_MODEL` | Price-list model overrides |

### Email sending

SMTP is used by purchase-order email sending and password-reset requests. Configure the mailbox, credentials and sender appropriate to the deployment. The code includes Gmail defaults; these do not prove the live mailbox is configured. User management also provides a separate password-reset action for authorized staff.

### WhatsApp attendance scheduling

`POST /api/attendance/whatsapp-daily` sends the current IST day's report and expects an `X-Cron-Secret` header matching `ATTENDANCE_WHATSAPP_CRON_SECRET`. Configure an external scheduler to call it if daily delivery is required. The current `render.yaml` declares credentials but does **not** declare a cron service.

`POST /api/attendance/whatsapp-send` provides an authenticated administrative send action. Use test recipients when testing either integration.

### Scheme documents (OCR + LLM extraction)

Scheme document extraction uses Anthropic when configured. Price-list image extraction supports additional providers; supported formats vary by provider. The incentive module's text-PDF parser is separate from these AI features.

The requirements include `pytesseract`, but installing that Python package does not install the external Tesseract executable. Verify system dependencies when enabling an OCR path that requires it.

## Testing

No automated test suite was found in this checkout. Start with syntax checks, then exercise real workflows on a separate local database.

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py models.py schemas.py auth.py database.py scheme_engine.py schemes.py
node --check static/app-shell.js
```

These checks do not prove API behavior, database compatibility or inline HTML-script correctness.

| Area | Checks |
| --- | --- |
| Authentication | Valid/invalid login, invite-code signup, inactive account, role-based access |
| Attendance | All four exempt roles outside 100 m; ordinary employee inside/outside assigned radius; punch-out; duplicate punch; refresh and saved records |
| Incentives | Known sales totals; editable rates; outlet/category totals; Excel formulas; invalid/empty upload |
| Reporting | Date/brand/outlet filters and exported totals agree with the displayed report |
| Purchases and schemes | Create/edit/status changes using test records and permitted roles |
| Browser | Desktop/mobile layout, camera/GPS permissions, Console and Network errors |
| Integrations | Email/WhatsApp only with configured test recipients |

For the incentive calculation, use 100,000 total sales with 7% profit and 2.5% incentive: expected results are 7,000 profit and 175 incentive. Open the downloaded workbook and verify the same totals.

Use `http://localhost:8000/docs` to inspect API schemas. Check server output and the browser's **F12 → Network / Console** when a request fails. For attendance, refresh after submitting and confirm the record is retrieved from the server. Phone testing needs a secure site for camera/location access; a plain HTTP LAN address is not equivalent to desktop localhost.

## Troubleshooting

- **Missing Python executable:** recreate the virtual environment with the installed Python version and select it in VS Code.
- **JavaScript `}` expected:** run `node --check` against the reported `.js` file. If the saved file passes, inspect unsaved editor changes and reload the editor if the diagnostic is stale.
- **401 / session expired:** sign in again; check account status and JWT configuration if the issue repeats.
- **403 / access denied:** inspect the endpoint's role guard and the account's assignments.
- **Attendance location blocked:** confirm the account's server-side role, assigned coordinates and deployed revision. The unrestricted roles are defined in `ATTENDANCE_ANYWHERE_ROLES` and the attendance page.
- **Incentive 404:** compare `/incentive` with `/incentive.html` and check the deployed route definitions.
- **Changes not appearing online:** confirm the deployed commit, inspect Render logs and refresh the browser; check service-worker caching if old assets remain.
- **Missing data after deployment:** verify `DATABASE_URL` and database persistence before creating or importing replacement records.
