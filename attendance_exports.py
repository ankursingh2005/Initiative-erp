"""Attendance downloads built from saved user IDs and attendance records."""
from attendance_history import weekoff_on
from attendance_access import dashboard_outlet, dashboard_category, can_view_attendance
import calendar
from datetime import date, timedelta
from io import BytesIO
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
import auth
import models
from database import get_db
from attendance_categories import filter_employee_category, filter_manager_employees

router = APIRouter(prefix='/api/attendance')
HEADERS = ['Emp ID', 'Employee', 'Date', 'Status', 'Punch in', 'Punch out', 'Hours']
DETAIL_HEADERS = ['Emp ID', 'Employee', 'Date', 'Day', 'Status', 'Punch In', 'Punch Out',
                  'Punch In Distance (m)', 'Punch Out Distance (m)', 'Punch In Photo', 'Punch Out Photo']


def render_export(rows, format, filename):
    if format not in {'xlsx', 'pdf'}:
        raise HTTPException(400, 'Choose Excel or PDF')
    output = BytesIO()
    if format == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Attendance'
        sheet.append(HEADERS)
        for row in rows:
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = 's'  # Names must remain text, never spreadsheet formulas.
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='155EEF')
        for index, width in enumerate([18, 30, 15, 14, 15, 15, 12], 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(output)
        media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        styles = getSampleStyleSheet()
        body = styles['BodyText']
        body.fontSize = 8
        body.leading = 10
        data = [[Paragraph(escape(str(value)), body) for value in row] for row in [HEADERS] + rows]
        table = Table(data, colWidths=[85, 180, 70, 65, 65, 65, 50], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAF1FF')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), .3, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=30, rightMargin=30,
            topMargin=25, bottomMargin=25).build([Paragraph('Attendance report', styles['Title']), Spacer(1, 12), table])
        media = 'application/pdf'
    return Response(output.getvalue(), media_type=media,
                    headers={'Content-Disposition': f'attachment; filename="{filename}.{format}"'})


def _safe_text(value):
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@')) else text


def _display_name(user, identity_cards):
    card = identity_cards.get(user.id)
    return _safe_text((card.employee_name if card and card.employee_name else None) or user.full_name or user.username)


def _employee_id(user, identity_cards):
    card = identity_cards.get(user.id)
    return _safe_text(card.employee_id if card and card.employee_id else '')


def _short_status(state):
    return {'Present': 'P', 'Leave': 'L', 'Week Off': 'WO', 'Absent': 'A'}.get(state, state or '-')


def _photo_status(value):
    return 'Yes' if value else 'No'


def _build_monthly_workbook(db, start, end, store_id=None, weekoff_day=None, status=None,
                            emp_category=None, assigned_store_id=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    users = db.query(models.User)
    users = users.filter(models.User.status == 'Active')
    if assigned_store_id is not None:
        users = filter_manager_employees(users.filter(models.User.store_id == assigned_store_id), emp_category)
    if weekoff_day:
        users = users.filter(models.User.weekoff_day == weekoff_day)
    users = filter_employee_category(users, emp_category)
    users = users.order_by(models.User.username, models.User.id).all()
    ids = [user.id for user in users]
    stores = {s.id: s.name for s in db.query(models.Store).all()}
    identity_cards = {card.user_id: card for card in db.query(models.IdentityCard).filter(models.IdentityCard.user_id.in_(ids)).all()} if ids else {}

    records = db.query(models.AttendanceRecord).filter(models.AttendanceRecord.user_id.in_(ids),
        models.AttendanceRecord.attendance_date >= start, models.AttendanceRecord.attendance_date <= end)
    leaves = db.query(models.AttendanceLeave).filter(models.AttendanceLeave.user_id.in_(ids),
        models.AttendanceLeave.leave_date >= start, models.AttendanceLeave.leave_date <= end)
    by_day = {(record.user_id, record.attendance_date): record for record in records.order_by(models.AttendanceRecord.id).all()}
    leave_days = {(leave.user_id, leave.leave_date) for leave in leaves.all()}
    days = [start + timedelta(days=index) for index in range((end - start).days + 1)]
    today = date.today()

    workbook = Workbook()
    summary = workbook.active
    summary.title = 'Monthly Summary'
    detail = workbook.create_sheet('Attendance Detail')

    navy_fill = PatternFill('solid', fgColor='17365D')
    month_fill = PatternFill('solid', fgColor='DDEBF7')
    header_fill = PatternFill('solid', fgColor='4472C4')
    present_fill = PatternFill('solid', fgColor='D9EAD3')
    absent_fill = PatternFill('solid', fgColor='F4CCCC')
    weekoff_fill = PatternFill('solid', fgColor='F4B183')
    blank_fill = PatternFill('solid', fgColor='E7E6E6')
    white_font = Font(bold=True, color='FFFFFF')
    navy_font = Font(bold=True, color='002060')
    thin = Side(style='thin', color='D9E2F3')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    total_columns = 2 + len(days) + 4
    summary.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
    summary.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_columns)
    summary['A1'] = 'MONTHLY ATTENDANCE SUMMARY'
    summary['A2'] = start.strftime('%B %Y')
    summary['A1'].font = Font(bold=True, size=14, color='FFFFFF')
    summary['A2'].font = navy_font
    summary['A1'].alignment = summary['A2'].alignment = Alignment(horizontal='center')
    summary['A1'].fill = navy_fill
    summary['A2'].fill = month_fill
    summary.append([])
    summary.append(['Emp ID', 'Employee'] + [str(day.day) for day in days] + ['Present', 'Absent', 'Week Off', 'Total'])

    detail.append(DETAIL_HEADERS)
    summary_rows = []
    detail_rows = []
    users_by_id = {user.id: user for user in users}
    for user in users:
        present = absent = weekoff = 0
        marks = []
        include_user = store_id is None
        for day in days:
            record = by_day.get((user.id, day))
            outlet_id = record.store_id if record and record.store_id is not None else user.store_id
            if store_id is not None and outlet_id != store_id:
                marks.append('-')
                continue
            include_user = True
            if day > today:
                mark = '-'
            else:
                state = ('Present' if record and record.checkin_at else 'Leave' if (user.id, day) in leave_days
                         else 'Week Off' if day.strftime('%A') == weekoff_on(user, day) else 'Absent')
                if status and state != status:
                    mark = '-'
                else:
                    mark = _short_status(state)
                    if state == 'Present':
                        present += 1
                    elif state == 'Absent':
                        absent += 1
                    elif state == 'Week Off':
                        weekoff += 1
            marks.append(mark)
        if include_user and (not status or any(mark == _short_status(status) for mark in marks)):
            summary_rows.append([_employee_id(user, identity_cards), _display_name(user, identity_cards)] + marks +
                                [present, absent, weekoff, f'{present}/{len(days)}'])

    for record in sorted(by_day.values(), key=lambda item: (stores.get(item.store_id, ''), item.user_id, item.attendance_date, item.id)):
        user = users_by_id.get(record.user_id)
        if not user:
            continue
        outlet_id = record.store_id if record.store_id is not None else user.store_id
        if store_id is not None and outlet_id != store_id:
            continue
        state = 'Present' if record.checkin_at else 'Absent'
        if status and state != status:
            continue
        detail_rows.append([_employee_id(user, identity_cards), _display_name(user, identity_cards), record.attendance_date,
                            record.attendance_date.strftime('%A'), _short_status(state),
                            record.checkin_at, record.checkout_at, record.checkin_distance_m or 0,
                            record.checkout_distance_m or 0, _photo_status(record.checkin_selfie),
                            _photo_status(record.checkout_selfie)])

    for row in sorted(summary_rows, key=lambda item: (str(item[0]).lower(), str(item[1]).lower())):
        summary.append(row)
    for row in detail_rows:
        detail.append(row)

    for sheet in (summary, detail):
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                cell.border = border
                cell.font = Font(name='Calibri', size=11)
                cell.alignment = Alignment(vertical='center', horizontal='center' if sheet is summary and cell.column >= 3 else 'left')
        header_row = 4 if sheet is summary else 1
        for cell in sheet[header_row]:
            cell.font = white_font
            cell.fill = header_fill if sheet is summary else navy_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
        sheet.auto_filter.ref = f'A{header_row}:{get_column_letter(sheet.max_column)}{sheet.max_row}'

    for cell in summary[1]:
        cell.fill = navy_fill
        cell.font = Font(name='Calibri', bold=True, size=14, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for cell in summary[2]:
        cell.fill = month_fill
        cell.font = Font(name='Calibri', bold=True, color='002060')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for cell in summary[3]:
        cell.fill = month_fill
    summary.row_dimensions[1].height = 26
    summary.row_dimensions[2].height = 24
    summary.row_dimensions[3].height = 8
    summary.row_dimensions[4].height = 30

    summary_day_start = 3
    summary_day_end = 2 + len(days)
    for row in range(5, summary.max_row + 1):
        for column in range(summary_day_start, summary_day_end + 1):
            cell = summary.cell(row, column)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if cell.value == 'P':
                cell.fill = present_fill
            elif cell.value == 'A':
                cell.fill = absent_fill
            elif cell.value == 'WO':
                cell.fill = weekoff_fill
            else:
                cell.fill = blank_fill
        for column in range(summary_day_end + 1, total_columns + 1):
            summary.cell(row, column).alignment = Alignment(horizontal='center', vertical='center')

    detail.row_dimensions[1].height = 24
    for row in range(2, detail.max_row + 1):
        status_cell = detail.cell(row, 5)
        status_cell.alignment = Alignment(horizontal='center', vertical='center')
        if status_cell.value == 'P':
            status_cell.fill = present_fill
        elif status_cell.value == 'A':
            status_cell.fill = absent_fill
        elif status_cell.value == 'WO':
            status_cell.fill = weekoff_fill
        detail.cell(row, 8).number_format = '0.0'
        detail.cell(row, 9).number_format = '0.0'

    summary.freeze_panes = 'A5'
    detail.freeze_panes = 'A2'
    for column, width in [(1, 20), (2, 25)]:
        summary.column_dimensions[get_column_letter(column)].width = width
    for column in range(3, 3 + len(days)):
        summary.column_dimensions[get_column_letter(column)].width = 6
    for column in range(3 + len(days), total_columns + 1):
        summary.column_dimensions[get_column_letter(column)].width = 12
    for index, width in enumerate([18, 25, 14, 14, 11, 18, 18, 22, 23, 17, 18], 1):
        detail.column_dimensions[get_column_letter(index)].width = width
    for row in range(2, detail.max_row + 1):
        detail.cell(row, 3).number_format = 'dd-mmm-yyyy'
        detail.cell(row, 6).number_format = 'hh:mm AM/PM'
        detail.cell(row, 7).number_format = 'hh:mm AM/PM'

    output = BytesIO()
    workbook.save(output)
    return Response(output.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="all-outlets-attendance-{start:%Y-%m} monthly.xlsx"'})


def export_rows(db, start=None, end=None, user_id=None, store_id=None, weekoff_day=None, status=None, emp_category=None, assigned_store_id=None):
    users = db.query(models.User)
    if user_id is not None:
        users = users.filter(models.User.id == user_id)
    else:
        users = users.filter(models.User.status == 'Active')
    if assigned_store_id is not None:
        users = filter_manager_employees(users.filter(models.User.store_id == assigned_store_id), emp_category)
    if weekoff_day:
        users = users.filter(models.User.weekoff_day == weekoff_day)
    users = filter_employee_category(users, emp_category)
    users = users.order_by(models.User.username, models.User.id).all()
    ids = [user.id for user in users]
    identity_cards = {card.user_id: card for card in db.query(models.IdentityCard).filter(models.IdentityCard.user_id.in_(ids)).all()} if ids else {}
    records = db.query(models.AttendanceRecord).filter(models.AttendanceRecord.user_id.in_(ids))
    leaves = db.query(models.AttendanceLeave).filter(models.AttendanceLeave.user_id.in_(ids))
    if start:
        records = records.filter(models.AttendanceRecord.attendance_date >= start, models.AttendanceRecord.attendance_date <= end)
        leaves = leaves.filter(models.AttendanceLeave.leave_date >= start, models.AttendanceLeave.leave_date <= end)
    by_day = {(r.user_id, r.attendance_date): r for r in records.order_by(models.AttendanceRecord.id).all()}
    leave_days = {(r.user_id, r.leave_date) for r in leaves.all()}
    rows = []
    for user in users:
        days = ([start + timedelta(days=i) for i in range((end-start).days+1)] if start else
                sorted({day for uid, day in set(by_day) | leave_days if uid == user.id}))
        for day in days:
            record = by_day.get((user.id, day))
            outlet_id = record.store_id if record else user.store_id
            if store_id is not None and outlet_id != store_id:
                continue
            state = ('Present' if record and record.checkin_at else 'Leave' if (user.id, day) in leave_days
                     else 'Week Off' if day.strftime('%A') == weekoff_on(user, day) else 'Absent')
            if status and state != status:
                continue
            checkin, checkout = (record.checkin_at, record.checkout_at) if record else (None, None)
            hours = round((checkout-checkin).total_seconds()/3600, 2) if checkin and checkout else ''
            rows.append([_employee_id(user, identity_cards), _display_name(user, identity_cards), day.isoformat(), state,
                         checkin.strftime('%H:%M') if checkin else '', checkout.strftime('%H:%M') if checkout else '', hours])
    return rows


@router.get('/admin-export')
def daily_export(date: date, format: str = 'xlsx', store_id: int | None = None,
                 weekoff_day: str | None = None, status: str | None = None, emp_category: str | None = None,
                 db: Session = Depends(get_db), actor=Depends(auth.require_roles('Admin', 'CategoryManager', 'Service Manager A', 'Service Manager B', 'CEO', 'Director', 'AccountsManager'))):
    store_id = dashboard_outlet(actor, store_id)
    emp_category = dashboard_category(actor, emp_category)
    rows = export_rows(db, date, date, assigned_store_id=actor.store_id if actor.role == "CategoryManager" else None, store_id=store_id, weekoff_day=weekoff_day, status=status, emp_category=emp_category)
    return render_export(rows, format, f'attendance-{date}')


@router.get('/monthly-export')
def monthly_export(month: str, store_id: int | None = None, weekoff_day: str | None = None,
                   status: str | None = None, emp_category: str | None = None,
                   db: Session = Depends(get_db), actor=Depends(auth.require_roles('Admin', 'CategoryManager', 'Service Manager A', 'Service Manager B', 'CEO', 'Director', 'AccountsManager'))):
    store_id = dashboard_outlet(actor, store_id)
    emp_category = dashboard_category(actor, emp_category)
    try:
        start = date.fromisoformat(month + '-01')
    except ValueError:
        raise HTTPException(400, 'Month must be YYYY-MM')
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return _build_monthly_workbook(db, start, end, assigned_store_id=actor.store_id if actor.role == "CategoryManager" else None,
                                   store_id=store_id, weekoff_day=weekoff_day, status=status, emp_category=emp_category)


@router.get('/admin-user-export')
def user_export(user_id: int, format: str = 'xlsx', db: Session = Depends(get_db),
                actor=Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, 'User not found')
    if not can_view_attendance(actor, user):
        raise HTTPException(403, "You cannot download another user's attendance")
    outlet = actor.store_id if actor.role == 'CategoryManager' and actor.id != user_id else None
    card = db.get(models.IdentityCard, user_id)
    filename_id = card.employee_id if card and card.employee_id else user.username
    return render_export(export_rows(db, user_id=user_id, store_id=outlet), format, f'attendance-{filename_id}')
