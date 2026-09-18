# EMS — Employee Management System

**ERP integration:** EMS is now available from **ERP Home → EMS** using the
existing ERP login and database. See [ERP_INTEGRATION.md](ERP_INTEGRATION.md).
The startup instructions below are for the separate standalone development mode.

A separate, runnable employee self-service and HR application. It has its own
database, authentication, frontend and tests. No existing ERP data is imported
or modified, and there are no default accounts or sample employee records.

## Start on Windows

Install Python 3.11 or later, then run from this `EMS` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m app.main create-admin
.\start.ps1
```

The administrator command prompts for a name, email and password without
echoing the password. Open **http://127.0.0.1:8010** and sign in. If PowerShell
does not allow the startup script, run the server directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
`requirements.lock.txt` records the tested dependency versions;
`requirements.txt` contains the allowed direct-dependency ranges for upgrades.

## Included workflows

1. An employee registers with a name, email and password.
2. An administrator or HR user opens **Employees**, reviews the pending account
   and assigns its status, department, designation, outlet and joining date.
3. After activation the employee can sign in, update their name, phone and photo,
   record attendance, request leave, print an ID, and view their payslips and rewards.
4. HR reviews leave requests, records approved incentives/bonuses, publishes a
   monthly payslip and records when payment has been made externally.

### Access

| Role | Access |
| --- | --- |
| Employee | Own profile, attendance, leave, identity card, payslips and rewards |
| HR | Organisation-wide employee records, attendance, leave approval, payroll, rewards and activity log |
| Administrator | HR access plus management of HR/admin roles |

Only administrators can create or change management roles. The last active
administrator cannot be demoted or deactivated. Deactivation and role changes
revoke existing sessions. Staff cannot approve their own leave.

### Attendance and leave

- One check-in/out pair per employee per day, recorded with server time in IST.
- Duplicate punches and overlapping pending/approved leave requests are rejected.
- Leave types: Casual, Sick, Earned and Unpaid. Leave balances and accrual policies
  are not calculated in this initial version.
- Attendance history displays the latest 500 records in the signed-in user's scope.

### Salary, incentive and bonus

- HR enters basic salary, allowances and total deductions for a calendar month.
- Approved incentives and bonuses for that month are included automatically.
- Net pay = basic + allowances + incentives + bonuses − deductions.
- All amounts are stored as integer paise; the interface displays INR.
- One payslip per employee/month. Published salary figures are immutable.
- Earnings cannot be added to a month after its payslip is published; record
  adjustments in a later month.
- **Mark paid** records a payment made outside EMS. It does not transfer money.
- Payslips and both sides of the employee ID support browser Print / Save PDF.

Payroll is a manual HR-approved register. Automatic attendance-based salary,
statutory deductions, tax calculation, bank disbursement and sales-linked incentive
formulas are not implemented. Configure those only after business rules are agreed.

## Configuration and data

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `EMS_DATABASE` | `EMS/data/ems.sqlite3` | Separate SQLite database location |
| `EMS_SECURE_COOKIE` | `0` | Set to `1` when serving through HTTPS |

Use a persistent disk for the database, keep backups, and restrict access to it.
Local startup binds only to `127.0.0.1`. Internet deployment requires HTTPS,
secure cookies, a correctly configured trusted reverse proxy and persistent storage.
This repository does not deploy itself or connect to the existing ERP.

Passwords use salted scrypt hashes. Sessions use random HttpOnly cookies, expire
after 12 hours, and require a CSRF token for mutations. Login attempts are limited
per email. Audit entries record changes and approvals without storing passwords.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests create temporary databases and exercise registration, approval, access
boundaries, session revocation, attendance, leave, payroll calculations, duplicate
protection, profile data and audit records.

## Project structure

```text
EMS/
  app/main.py           API, authentication, database and admin setup
  static/index.html     Application shell and sign-in/registration
  static/app.js         Employee and HR workflows
  static/style.css      Responsive interface and print layouts
  tests/test_ems.py      API regression tests
  start.ps1             Local server launcher
  requirements.txt
  data/                 Local database, created at startup and ignored by Git
```

## Next phases

This is the first working version, not the complete advanced HR suite. Planned
extensions include reporting-manager/outlet-scoped approvals, shifts and overnight
attendance, holiday calendars, leave balances, attendance corrections, salary
structures, statutory payroll rules, reimbursements, salary advances, assets,
document verification, announcements, exits and password recovery. Company name,
logo and identity-card branding are currently EMS and can be configured in a later
organisation-settings module.
