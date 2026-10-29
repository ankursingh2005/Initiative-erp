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

Each employee is granted 4 weekoffs. Week Off Availed is fetched automatically from daily attendance for the selected salary month (only dates marked Week Off count; future dates do not). Week Off Credit is calculated automatically as max(0, 4 minus Week Off Availed) and saved with the effective salary setup; attendance pay rules continue to determine payroll, and unused weekoff pay is paid separately in Phase 2 using IDS Actual Gross Earning. Restart the server after updating to add these columns to an existing database.

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

Week Off Pay is calculated automatically as (earned gross salary / 30) multiplied by Week Off Credit, rounded to the nearest paise. Incentive is manually entered. Amount Payable is their sum, matching the reference sheet; Expected Basic is excluded from this total. For the two-phase payment workflow, IDS shows Phase 1 and W/O & Incentive shows Phase 2. Previously published payroll stays unchanged.

Choose Regular or Contract in Emp Category after Amount Payable, then save the salary setup. The Emp Category filter after Employee Group filters the register, payroll, CSV and employee totals for the selected month. Existing employees remain unclassified until assigned.

Use Remove in the salary setup register to exclude an unpaid employee from EMS. Their ERP account, attendance and saved payroll remain stored. Open Excluded employees and choose Restore to salary list to reverse this. Admin and HR manage these exclusions.

## IDS NEW removed

IDS NEW is no longer part of EMS. Regular and Contract employees use the standard attendance-linked salary calculation. Restart the server to clear legacy IDS NEW attributes and breakdown fields. Published payroll totals, employee records and attendance history are preserved.

## Salary Distribution

Open Salary Distribution for the selected salary month and employee filters. Unpaid days come from attendance and salary pay rules (capped at 30); salary days are 30 minus unpaid days. Expected Basic and bank details come from Salary setup. Enter monthly Other Allowances and Staff Advance & Deduction, then select Save inputs in that row. Values are saved per employee and month and recalculate immediately.

VDA is 6.25% of Actual Basic; EPF is 12% of Actual Basic plus VDA. Bonus is 8.33% of Actual Pay (EPF), payable only when gross including the proposed bonus is strictly below INR 21,000. If adding the bonus would bring gross to INR 21,000 or more, Bonus Payable is zero. ESIC is 0.75% of Actual Gross Earning only when gross is strictly below INR 21,000. Each component is rounded to paise. Net is gross less EPF, ESIC and the entered advance/deduction.

The table scrolls horizontally, with a fixed employee column, formula tooltips, totals and a distribution download. Open months and missing manual attendance are provisional. This report does not publish payroll or transfer money. Existing payroll totals and ERP attendance records are not changed. Restart the server to create the distribution input table.


?Delete from EMS only? permanently removes the employee from EMS, including EMS salary setups, earnings, payroll history, payslips and EMS manual attendance. Their registered ERP account, login, shared Attendance records and access to other modules remain unchanged. A deletion audit is retained.

- **CL (Casual Leave)** is available between A and WO in Attendance Record. Type CL or choose Casual Leave in the attendance editor. CL totals are separate from L. CL is always paid; L follows the salary profile's paid leave setting.

## Paid unused weekoffs
Each month allows 4 weekoffs. Unused weekoff days = max(0, 4 - WO availed). Additional weekoff pay = earned gross salary / 30 * unused weekoff days, rounded to paise. Monthly payroll adds this pay before fixed deductions; the payslip shows it separately. IDS and Salary Distribution show Phase 1 net only. W/O & Incentive uses IDS Actual Gross Earning for the same formula and shows the separate Phase 2 payment. More than 4 weekoffs gives zero extra pay. CL is always paid; L follows the salary profile's paid leave rule; unpaid days, including ineligible days before joining, reduce salary. Open months remain provisional. Previously published payslips retain their saved values.

## Two-phase salary payments

Open **IDS**, immediately before **W/O & Incentive**, for the Phase 1 pay sheet. It shows attendance-based Actual Basic, VDA, prorated Other Allowances, Total Earning, Bonus, Actual Gross Earning, EPF, ESIC, Staff Advance & Deduction and Net Amount, with totals and a Download IDS button. Enter and save Other Allowances and Staff Advance & Deduction in Salary Distribution; IDS uses the same monthly saved values and shows unsaved edits as provisional.

- **Phase 1 (IDS):** Net Amount = Actual Gross Earning minus Total Deductions. Weekoff credit pay and incentive are excluded.
- **Phase 2 (W/O & Incentive):** Amount Payable = Actual Gross Earning / 30 multiplied by max(0, 4 minus Weekoffs Availed), plus the separately entered monthly incentive. Gross is taken from the same IDS calculation, before deductions.
- Example: IDS gross INR 29,063 and deductions INR 2,348 gives Phase 1 INR 26,715. With 3 weekoffs availed, Phase 2 weekoff credit pay is INR 968.77, plus the entered incentive. Amounts retain the existing paise rounding.

Both tabs follow the selected month, employee group and category filters. The reports do not transfer money or change previously published payslips. The legacy Monthly payroll publication calculation is separate from these two payment reports.

Attendance edits immediately recalculate Unpaid Days, Working Days, earnings and totals in Salary Distribution and IDS, and gross-based credit pay in W/O & Incentive. A to CL reduces unpaid days by one and increases working days by one (within the 30-day salary cap); CL is paid regardless of the L leave setting. WO edits also recalculate weekoff credit. Unsaved attendance is labelled provisional until automatic saving or Save now completes. Dates before joining stay unpaid, future dates stay Upcoming, and published attendance remains locked. These EMS corrections do not change original ERP punches or shared leave records.

## Combined Excel salary download

Download Salary, Download Salary Excel in IDS, Salary Distribution, or W/O & Incentive now creates one .xlsx workbook. The first sheet is IDS (Phase 1); the second is W-O & Incentive (Phase 2). Excel does not permit a slash in worksheet names. Both sheets contain the same selected employees and month, numeric INR amounts, totals, frozen headings and text bank account numbers. Report category choices and existing employee filters apply to both sheets. The workbook uses current calculated values, including unsaved edits, and marks open-month, incomplete or unsaved reports provisional. Exporting does not save inputs or change payroll or ERP records.

Bonus Payable, EPF Employee Contribution A/C and ESIC Employee Contribution A/C apply only to employees classified **Regular** in their effective Salary setup. For **Contract** employees all three are zero. Unclassified employees must be classified before these Regular-only amounts apply. Regular bonus and ESIC retain the gross salary threshold of strictly below INR 21,000; EPF remains 12% of Actual Pay (EPF). Staff Advance & Deduction still applies to both categories. IDS, Salary Distribution, Phase 2 gross and Excel downloads recalculate from the same category-aware calculation.

Paid CL is fixed to Yes in Salary setup: CL is always paid and L is always unpaid, including for profiles previously saved with paid leave enabled. Weekly-off payment remains configurable. Published salary snapshots remain unchanged.

Salary setup no longer displays Paid weekly offs or Paid CL controls. WO and CL are automatically paid; L remains unpaid. Attendance counts and unused weekoff credit pay continue to work.

## Overall attendance for manual employees
In Attendance Record, manually added employees have editable P, A, CL, WO and L monthly totals at the right of their row. Enter whole days and use Save now or automatic saving. The sum cannot exceed elapsed days in the selected month. Unentered days remain incomplete and are treated as unpaid provisionally; publication requires complete attendance. Once monthly totals are used, daily cells are blank and locked because totals do not assign statuses to specific dates. The declaration applies to the selected salary month, including manual employees entered later; no ERP joining date or daily source records are rewritten. Registered employees retain daily attendance totals. Monthly totals update Salary Distribution, IDS, W/O & Incentive and Excel. Restart/deploy the server once to create the new EMS-only monthly attendance table.

Employee lists and salary downloads are ordered by outlet, then employee name using case-insensitive natural alphanumeric sorting (for example, Employee 2 before Employee 10). Employee ID breaks ties. Both Excel sheets use identical employee order for All, Regular and Contract downloads, while preserving the selected group and search filters. IDs and employee records are not renamed.
