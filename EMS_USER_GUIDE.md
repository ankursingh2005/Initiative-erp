# IDSPL Employee Salary Management (EMS)

Open **EMS Salary** from Home, or visit `/ems` (`/erp/ems` when hosted under `/erp`). Restart the ERP server after installing this change so its new database tables are created. Existing ERP accounts, employee IDs, attendance records and login are reused. Admin and HR can manage EMS. Brand promoters/partners are excluded; IDS EMP is included. AC Retail and AC Projects include only Service Manager A, Service Manager B and ServiceCoordinator; AC technicians and helpers are excluded from EMS.

## Monthly workflow

1. Select the salary month and review the employee group or search by name, employee ID or outlet.
2. **Salary setup** lists Emp ID, Emp Name and Expected Basic (basic plus allowances), including employees with no setup. Use **Set up** or **Edit** to fill the form; employee identity fields come from ERP records. Choose the employee, effective month, basic salary, monthly allowances, fixed deductions and attendance pay rules. Salary always uses a fixed 30-day divisor, and explicitly choose whether weekoff and recorded leave are paid.
3. In **Monthly payroll**, review Present, Absent, Weekoff and Leave totals. Open **Review** for each employee's daily attendance and salary calculation.
4. **Manual earnings** accepts individually approved incentive and bonus amounts with a reason. Use **Void entry** to correct a mistaken entry before publication, then record the correct amount. Automatic allocation from the Incentive Project is pending the employee allocation rules.
5. After the month ends, review and publish the salary. The incentive acknowledgment confirms that automatic allocation is still pending. If attendance or salary values changed since review, refresh and review again.
6. Open **Salary records** to print a payslip or save it as PDF. **Mark paid** records a payment made outside EMS; EMS does not transfer money.
7. **Download CSV** exports the filtered attendance and salary preview. Published salary amounts are available from Salary records and their frozen payslips.

Each employee is granted 4 weekoffs. Week Off Availed is fetched automatically from daily attendance for the selected salary month (only dates marked Week Off count; future dates do not). Week Off Credit is calculated automatically as max(0, 4 minus Week Off Availed) and saved with the effective salary setup; attendance pay rules continue to determine payroll, and credit pay is not automatically added. Restart the server after updating to add these columns to an existing database.

## Calculation rules

- Money is stored as integer paise. Earned basic and allowances are rounded separately to the nearest paise using half-up rounding.
- Full eligible months receive the full configured monthly basic and allowances. Unpaid days reduce both by `monthly amount × unpaid days / chosen divisor`, capped at zero. A completely unpaid month earns zero, including February with the 30-day divisor.
- Unpaid days include absences, days before joining and leave/weekoff when configured as unpaid. Fixed monthly deductions are then subtracted.
- Net salary = earned basic + earned allowances + approved manual incentive + approved bonus − fixed deductions.
- Displayed attendance counts use the daily attendance register: future/upcoming, recorded punch-in, recorded leave, historical scheduled weekoff, absent. Joining dates affect salary eligibility separately and do not replace the displayed daily status. Weekoff work therefore counts as Present once. No automatic overtime or extra holiday payment is inferred.
- The employee identity card's joining date is used when available. Otherwise EMS uses the ERP account registration date. Correct the employee joining date before publishing a historical salary if account registration happened after employment began.
- Leave comes from the shared ERP attendance leave register. Its paid/unpaid treatment follows the selected salary profile; it does not infer leave entitlements or different pay by leave type.
- Open-month totals are provisional. Future dates are Upcoming rather than Absent. Publication requires the month to have ended, a salary setup, an eligible joining date and nonnegative net salary.

## Records and changes

Salary profiles have an effective month. The most recent profile effective on or before the salary month is selected. Changes affecting an already published month are blocked. Use a later effective month for future salary changes.

Published payroll stores the reviewed daily attendance, salary rules, totals and salary amounts as a snapshot. Later attendance changes do not change that payslip. Only one payroll record per employee/month is allowed. Existing manual payroll records remain available through the existing APIs.

Automatic Exact Sales and Non-sales incentive distribution is intentionally pending. The system does not divide outlet or department incentive totals among employees until the rules are supplied. Statutory payroll deductions are not calculated automatically; the current setup accepts an explicit fixed deduction amount.

## Validation

`tests/test_ems_salary.py` exercises isolated SQLite payroll calculations, role restrictions, employee groups, historical weekoff changes, joining dates, approved earnings, effective salary setup, stale previews, duplicate publication and frozen payslips.

`tests/ems_salary_preview.py` runs a local preview using synthetic in-memory data; `tests/ems-salary-ui.cjs` checks the ERP prefix, filters, attendance review, publication, payslip and mobile layout against that preview and an isolated Chrome debugger on port 9246.

Week Off Pay is calculated automatically as (Expected Basic / 30) ? Week Off Credit, rounded to the nearest paise. Incentive is manually entered. Amount Payable is their sum, matching the reference sheet; Expected Basic is excluded from this total. These reference amounts do not add approved earnings or change published payroll.

Choose Regular or Contract in Emp Category after Amount Payable, then save the salary setup. The Emp Category filter after Employee Group filters the register, payroll, CSV and employee totals for the selected month. Existing employees remain unclassified until assigned.

Use Remove in the salary setup register to exclude an unpaid employee from EMS. Their ERP account, attendance and saved payroll remain stored. Open Excluded employees and choose Restore to salary list to reverse this. Admin and HR manage these exclusions.

## IDS NEW removed

IDS NEW is no longer part of EMS. Regular and Contract employees use the standard attendance-linked salary calculation. Restart the server to clear legacy IDS NEW attributes and breakdown fields. Published payroll totals, employee records and attendance history are preserved.

## Salary Distribution

Open Salary Distribution for the selected salary month and employee filters. Absence comes from attendance (capped at 30); working days are 30 minus absence. Expected Basic and bank details come from Salary setup. Enter monthly Other Allowances and Staff Advance & Deduction, then select Save inputs in that row. Values are saved per employee and month and recalculate immediately.

VDA is 6.25% of Actual Basic; EPF is 12% of Actual Basic plus VDA. Bonus is 8.33% of Actual Pay (EPF) only when Total Earning is strictly below INR 21,000. ESIC is 0.75% of Actual Gross Earning only when gross is strictly below INR 21,000. Each component is rounded to paise. Net is gross less EPF, ESIC and the entered advance/deduction.

The table scrolls horizontally, with a fixed employee column, formula tooltips, totals and a distribution download. Open months and missing manual attendance are provisional. This report does not publish payroll or transfer money. Existing payroll totals and ERP attendance records are not changed. Restart the server to create the distribution input table.


?Delete from EMS only? permanently removes the employee from EMS, including EMS salary setups, earnings, payroll history, payslips and EMS manual attendance. Their registered ERP account, login, shared Attendance records and access to other modules remain unchanged. A deletion audit is retained.
