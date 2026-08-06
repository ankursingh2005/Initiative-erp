# IDSPL Scheme Management ERP

IDSPL is a FastAPI-based ERP application for managing scheme-driven sales, claims, and role-based operations through a simple web dashboard.

## Highlights

- User authentication with JWT-based login
- Role-based access for Admin, Category Manager, Brand Manager, Brand Partner, Accounts, and MIS Executive
- Sales entry, scoped visibility, and claim tracking
- Scheme creation, activation, pause, and mapping workflows
- Scheme document upload with Claude-powered OCR/extraction into Draft schemes for Admin review
- Interval sales analytics upload and reporting, with a Scheme-Matched Sales profitability view
- Purchase Orders with WhatsApp alerts and emailed PO documents
- Admin-managed user list and password reset (no outbound account-recovery email)
- Static dashboard UI served directly by FastAPI

## Tech Stack

- FastAPI
- SQLAlchemy
- SQLite for local development, PostgreSQL for hosted deployments
- JWT authentication with bcrypt
- HTML, CSS, and JavaScript frontend

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open:

- App:https://scheme-management-for-idspl.onrender.com
  
Optional dependencies for file-based analytics uploads:

```powershell
pip install openpyxl pypdf pillow pytesseract
```

## Project Structure

- `main.py` - application entry point, routes, schema checks, and startup setup
- `models.py` - database models
- `schemas.py` - request and response schemas
- `auth.py` - password hashing and JWT helpers
- `database.py` - database configuration and session handling
- `scheme_engine.py` - scheme evaluation logic
- `schemes.py` - scheme-related helpers
- `static/` - login, signup, dashboard, and PWA assets

## Notes

- The app uses SQLite by default and creates required tables on startup.
- Default master data and branches are seeded automatically.
- Set `SECRET_KEY` in the environment before using this in production.

## Deploy on Render or Railway

Use PostgreSQL in production. SQLite is fine locally, but Render's web-service filesystem is temporary. Data written to SQLite can disappear whenever the service is restarted or redeployed.

The included `render.yaml` creates both the `idspl` web service and the `idspl-postgres` managed PostgreSQL database. Render automatically passes the PostgreSQL connection string to the web service as `DATABASE_URL`. The application creates its tables on first startup, and every user's sales, schemes, accounts, and uploads are then stored in PostgreSQL rather than on one laptop or one temporary Render instance.

To deploy:

1. Push this repository to GitHub.
2. In Render, choose **New** > **Blueprint** and select the repository. Render will read `render.yaml` and create both services.
3. Confirm the persistent `basic-256mb` PostgreSQL plan shown by Render, then apply the blueprint and wait for the first deploy to finish. This paid tier is required because Render's free PostgreSQL databases expire after 30 days.
4. Open the web-service URL and create the initial Admin account. Admin users can see, edit, and delete all sales in the dashboard.

For an existing Render web service, create a Render PostgreSQL database, copy its **Internal Database URL** into the web service's `DATABASE_URL` environment variable, add `psycopg2-binary` through this repository change, and redeploy.

Existing data in `scheme_erp.db` is local SQLite data. It is not automatically copied to PostgreSQL; export/import or migrate it before removing the old database file.

- Install command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- For Railway, add a PostgreSQL service and set `SECRET_KEY` in the project variables.

## Scheme documents (OCR + LLM extraction)

Under Scheme Maintenance, an Admin/BrandManager/BrandPartner can attach the scheme circular they received from a brand - an image, PDF, or Excel file - via **Attach Scheme Document**. This:

1. Creates a new scheme with status `Draft`.
2. Saves the uploaded file (stored in the database, not on disk, so it survives Render restarts/redeploys).
3. Sends the document to the Claude API, which reads it (tables, stamps, handwriting for images/PDFs; a flattened cell dump for Excel/CSV) and returns the scheme's terms - brand, product, dates, reward type/value or slabs, min/max quantity, offer type, circular number, and remarks.
4. Pre-fills the Draft scheme with whatever was extracted. **It is never activated automatically** - it stays in "Draft Schemes Pending Review" until an Admin reviews the extracted fields, corrects anything needed, and clicks **Activate**.

If extraction fails, or the document type isn't supported, or `ANTHROPIC_API_KEY` isn't set, the document is still saved and the scheme still appears in the Draft queue - it just needs to be filled in by hand before activating.

To enable extraction, set `ANTHROPIC_API_KEY` on the web service (Render dashboard -> `idspl` -> Environment). Without it, document upload still works, but scheme fields must be entered manually.

## IDS Price System - price list upload (Excel, or AI-read image/PDF)

Under **IDS Price System**, Admin/Accounts/MISExecutive can bulk-upload the price list via **Upload Price List**, in either of two ways:

1. **Excel (`.xlsx`/`.xls`)** - the same brand-section-header layout as the existing price sheets (a brand name row followed by an Item Details / Total Stock / Purchase Price / MSP / ISP table). Parsed directly, no AI involved.
2. **Photo/scan (`.jpg`/`.jpeg`/`.png`/`.webp`) or PDF** - an AI vision model reads the brand sections and item rows directly from the image/PDF and returns the same row shape as the Excel parser.

Either path updates existing items (matched by brand + item name), adds new items, and creates any brand not yet in the system - exactly the same insert/update logic either way.

**Any one of these three keys enables the image/PDF path** - whichever is set on the web service is used automatically, checked in this order (override with `VISION_PROVIDER=anthropic|xai|openai` if more than one happens to be set):

| Env var | Provider | Images | PDFs |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | Yes | Yes |
| `XAI_API_KEY` | Grok (xAI) | Yes | No - use an image or Excel instead |
| `OPENAI_API_KEY` | OpenAI | Yes | No - use an image or Excel instead |

If none of these three keys are set, the Excel upload still works exactly as before - only the image/PDF option is disabled, with a message pointing the user at Excel or an Admin.

AI-read values can occasionally misread a digit or a column, especially from a blurry photo - review the upload summary (new/updated/skipped counts and which provider read it) and spot-check a few items after an image/PDF upload.

## AI Analysis dashboard

After login, the **AI Analysis** tile on the home page opens `/analytics` - a profitability dashboard built from an uploaded sales export.

- **Upload (Admin only):** drop or choose an Excel (`.xlsx`/`.xls`) or CSV file. Every sheet in a workbook is read, so one file with a tab per financial year works in a single upload. Column names are matched loosely and in any order - it looks for `Date`, `Item`, `Sales Amt`, `Cost Amt`, `Profit/Loss` (`Division` and `Qty` are optional extras that unlock the division breakdown and unit counts). Each new upload replaces the previous dataset - this is a current-snapshot dashboard, not a history of every file ever uploaded.
- **Viewing:** any logged-in user can view the dashboard once data has been uploaded; only Admin can upload or clear it.
- **What it shows:** KPI cards (total sales/cost/profit, margin %, transactions, item and division counts, date coverage), a yearly and monthly sales/profit trend, top 10 profitable items, profit share by division, loss-making items, and margin leaders/laggards - with a division and date-range filter that re-queries the same figures.
- **Recommendations:** a rule-based panel (no external AI call) that flags the leading profit-driving division, year-over-year growth/decline per division, loss-making items worth a pricing review, high-revenue/low-margin items worth bundling with a scheme, seasonal best/worst months, and an overall margin health check. Every number quoted is computed directly from the uploaded data.
- **Data quality note:** a "Bill-wise Profitability" export can include non-inventory lines (brand payouts, banners, incentives, commissions) alongside real product sales, and some line items may carry a cost with no matching sale value (e.g. transfers/write-offs) or a sale with no recorded cost. These pass through the rankings as-is rather than being silently filtered, since guessing which rows to exclude risks hiding real figures - review the Top Items and Loss-Making Items tables with that in mind.

## Scheme-matched sales (profitability report)

In **Sales in your scope**, the **Profitability Report - Scheme Matched Sales** panel filters your uploaded profitability report (Interval Sales Analytics Upload - the Date/Vch No/Account/Item/Qty/Unit/Sales Amt/Cost/Profit-Loss/Profit% format exported from Busy) down to only the rows that:

- fall inside an Active scheme's start/end date, and
- exactly match that scheme's product (or, for a brand-wide scheme with no specific product, any product under that brand).

Each matched row shows the computed backend claim amount, using the same Fixed/Percentage/Slab reward math as the automatic claim engine (`scheme_engine.py`), so Admin can see at a glance which Busy sales are scheme-eligible without manual cross-checking.

## Purchase Orders and WhatsApp Alerts

After login, users can choose **Schemes** or **Purchase Orders**. Any logged-in user can submit a stock requisition with branch, division, supplier, delivery address, product/model/serial details, stock balance, sales rate, quantity, and estimated price. Admin and MIS Executive users see every request and can update its status, Busy PO number, order date, and processing notes.

To send an alert to MIS Executive through WhatsApp, configure a WhatsApp Cloud API app and add these Render environment variables to the web service:

- `WHATSAPP_ACCESS_TOKEN` - permanent or system-user access token from Meta
- `WHATSAPP_PHONE_NUMBER_ID` - the sending WhatsApp Business phone number ID
- `WHATSAPP_MIS_RECIPIENTS` - comma-separated recipient numbers in international format, for example `919876543210,919812345678`
- `WHATSAPP_API_VERSION` - optional; defaults to `v23.0`

The PO is saved even when WhatsApp is not configured or its provider rejects a message. WhatsApp Business may require an approved message template for business-initiated alerts outside the customer service window.

## Account recovery (Admin-managed, no email)

There is no "forgot password" email flow. A locked-out user is told on the login page to ask their Admin. Instead:

- Admin logs in and opens **Purchase Orders -> Manage Users** (visible only to the Admin role).
- The panel lists every registered account (username, email, role, status) and shows the total number of registered accounts, broken down by role, on the Schemes dashboard too.
- Clicking **Reset Password** on any user opens a small dialog to set a new password directly. No email is sent, no token or expiring link is involved, and it works identically whether or not SMTP is configured.
- This calls `POST /api/users/{user_id}/reset-password`, Admin-only, which hashes and saves the new password and invalidates any old reset token that may still exist from before this flow was introduced.

The old email-based `/auth/forgot-password` and `/auth/reset-password` endpoints, and the `forgot_password.html` / `reset_password.html` pages, no longer exist in this codebase.

## Email sending (Purchase Order emails)

The "Final Order" / "Send PO Email" action on a Purchase Order sends a real email through SMTP. In code, the host, username, port, and from-address already default to the company Gmail mailbox:

- `SMTP_HOST` defaults to `smtp.gmail.com`
- `SMTP_USER` / `SMTP_FROM` default to `initiative.lucknow@gmail.com`
- `SMTP_PORT` defaults to `587`

So on Render, the **only thing you must set yourself is `SMTP_PASSWORD`** - a Gmail **App Password**, not the normal account password (Gmail blocks plain-password SMTP login).

### 1. Generate a Gmail App Password

1. Sign in to `initiative.lucknow@gmail.com`.
2. Turn on 2-Step Verification if it isn't already on: Google Account -> Security -> 2-Step Verification.
3. Go to Google Account -> Security -> App passwords (or visit `myaccount.google.com/apppasswords` while signed in as that account).
4. Create an app password (name it e.g. "Initiative ERP"). Google shows a 16-character code - copy it.

### 2. Set it on Render

In the Render dashboard, open the `idspl` web service -> **Environment**, and add:

| Key | Value |
|---|---|
| `SMTP_PASSWORD` | the 16-character app password from step 1 |

`render.yaml` already declares this key with `sync: false`, so if you deploy via Blueprint, Render will prompt you for it instead of trying to read it from the repo (and it's never committed).

Redeploy (or just save the environment changes - Render restarts the service automatically) and test:

- Purchase Orders -> process a request -> **Send PO Email** or **Final Order**. The response message should say `Emailed to N recipient(s).` instead of `Not sent: ...`.

### Notes

- If SMTP fails (wrong app password, Gmail blocking the login, network issue), the PO/request itself is still saved - only the email send is reported as failed, so nothing is lost.
- To send from a different mailbox instead, just override `SMTP_HOST`, `SMTP_USER`, `SMTP_FROM`, and `SMTP_PASSWORD` with that provider's values; nothing else in the code needs to change.
- SMTP configuration only affects Purchase Order emails now. Account recovery never uses email - see "Account recovery" above.

## Oracle Cloud Free Tier

- For Oracle Cloud Free Tier, deploy this app on an Ubuntu VM with `systemd` and `nginx`.
- Use SQLite for a small single-server setup, or PostgreSQL on the VM for better reliability.
- Full setup instructions are in `ORACLE_CLOUD_FREE_TIER_SETUP.md`.