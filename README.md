# IDSPL Scheme Management ERP

IDSPL is a FastAPI-based ERP application for managing scheme-driven sales, claims, and role-based operations through a simple web dashboard.

## Highlights

- User authentication with JWT-based login
- Role-based access for Admin, Category Manager, Brand Manager, Brand Partner, Accounts, and MIS Executive
- Sales entry, scoped visibility, and claim tracking
- Scheme creation, activation, pause, and mapping workflows
- Interval sales analytics upload and reporting
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

- App: http://127.0.0.1:8000/login
- API Docs: http://127.0.0.1:8000/docs

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

## Purchase Orders and WhatsApp Alerts

After login, users can choose **Schemes** or **Purchase Orders**. Any logged-in user can submit a stock requisition with branch, division, supplier, delivery address, product/model/serial details, stock balance, sales rate, quantity, and estimated price. Admin and MIS Executive users see every request and can update its status, Busy PO number, order date, and processing notes.

To send an alert to MIS Executive through WhatsApp, configure a WhatsApp Cloud API app and add these Render environment variables to the web service:

- `WHATSAPP_ACCESS_TOKEN` - permanent or system-user access token from Meta
- `WHATSAPP_PHONE_NUMBER_ID` - the sending WhatsApp Business phone number ID
- `WHATSAPP_MIS_RECIPIENTS` - comma-separated recipient numbers in international format, for example `919876543210,919812345678`
- `WHATSAPP_API_VERSION` - optional; defaults to `v23.0`

The PO is saved even when WhatsApp is not configured or its provider rejects a message. WhatsApp Business may require an approved message template for business-initiated alerts outside the customer service window.

## Oracle Cloud Free Tier

- For Oracle Cloud Free Tier, deploy this app on an Ubuntu VM with `systemd` and `nginx`.
- Use SQLite for a small single-server setup, or PostgreSQL on the VM for better reliability.
- Full setup instructions are in `ORACLE_CLOUD_FREE_TIER_SETUP.md`.

## License

No license file is included yet.
