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
- SQLite
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

- Use PostgreSQL in production. SQLite is fine locally, but hosted file systems on Render and Railway are not a reliable long-term database store.
- The app already supports `DATABASE_URL` and `SECRET_KEY` from environment variables.
- Install command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- For Render, this repo includes `render.yaml`.
- For Railway, add a PostgreSQL service and set `SECRET_KEY` in the project variables.

## Oracle Cloud Free Tier

- For Oracle Cloud Free Tier, deploy this app on an Ubuntu VM with `systemd` and `nginx`.
- Use SQLite for a small single-server setup, or PostgreSQL on the VM for better reliability.
- Full setup instructions are in `ORACLE_CLOUD_FREE_TIER_SETUP.md`.

## License

No license file is included yet.
