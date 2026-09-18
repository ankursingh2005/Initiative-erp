# EMS inside Initiative ERP

Open **ERP Home → EMS**, or `/ems` (also `/erp/ems` behind the existing ERP prefix).
Use your existing ERP login. Do not create a separate EMS administrator for this mode.

The main ERP server serves the EMS interface from `EMS/static/`. It does not start
or import the standalone `EMS/app/main.py` application and does not use its SQLite
database, registration or sessions.

## Shared modules

- **Employees:** ERP user accounts and roles. Admin/HR management opens the
  existing password-confirmed User Management panel on ERP Home.
- **Attendance:** reads ERP attendance records. Punches open the existing ERP
  attendance page so selfie, location, geofence and timing checks remain in force.
- **Identity card:** opens the ERP identity-card module, including photos,
  joining dates, font fitting, rotation and printing.
- **Profile:** reads existing ERP account and card details; corrections remain
  in ERP User Management and the HR-controlled card editor.
- **Leave:** employees submit requests; Admin, Owner or HR approves or rejects.
  Approved days are added to ERP attendance leave. Employees cannot override
  HR-approved leave using the daily Working toggle.
- **Salary, incentives and bonuses:** ERP-backed HR-approved records, published
  payslips, and external-payment status. The existing sales incentive calculator
  remains separate; amounts are not automatically assigned from sales reports.
- **Activity log:** records EMS leave, earning and payroll actions.

Employees access only their own leave, attendance, salary and rewards. Admin,
Owner and HR have management access. Existing restrictions remain: only Admin/HR
manage user accounts, and Brand Promoters retain Home/Attendance access only.

## Database and deployment

`ems_models.py` registers four new tables before the ERP's existing `create_all`:
`ems_leave_requests`, `ems_earnings`, `ems_payroll`, and `ems_audit`. All reference
existing ERP users. No separate user migration or account import is needed.
Accounts with EMS leave/payroll history must be deactivated instead of deleted.

Deploy `ems.py`, `ems_models.py`, the updated `main.py`, `static/home.html`,
`static/app-shell.js`, and the `EMS/static` directory together, then restart the
ERP service. Its configured database must permit creating the new tables.
No extra production Python packages are required beyond the ERP requirements.

The standalone starter remains runnable for development, but its data is not
automatically imported into ERP. Advanced features listed in `README.md` remain
future phases; this integration does not add automatic statutory payroll,
leave accrual, bank transfers or automatic sales-to-employee reward allocation.

## Checks

From the ERP project root:

```powershell
python -m unittest discover -s tests -p test_ems_integration.py -v
```

This suite uses an isolated in-memory ERP database and tests shared identity,
Bearer authentication, scope boundaries, attendance, leave synchronization and
payroll. `tests/ems_erp_preview.py` starts a disposable full-ERP test server for
`tests/ems-erp-ui.cjs` browser checks; never use its sample accounts in production.
