"""ERP EMS API: existing authentication, employees, identity and attendance."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import func
from sqlalchemy.orm import Session, defer
from sqlalchemy.exc import IntegrityError
import calendar
import json
from decimal import ROUND_HALF_UP
from typing import Literal
from attendance_history import weekoff_on, daily_attendance_status
from attendance_categories import employee_category, AC_ROLES

import auth
import models
import ems_models as M
from database import get_db

router = APIRouter(prefix='/api/ems', tags=['EMS'])
pages = APIRouter()
ROOT = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
EMS_EXCLUDED_ROLES = tuple(role for role in AC_ROLES if role not in {
    'Service Manager A', 'Service Manager B', 'ServiceCoordinator'
}) + ('BrandPartner',)


def member(response: Response, user=Depends(auth.get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    if user.role not in {'Admin', 'HR'}:
        raise HTTPException(403, 'EMS is available only to Admin and HR')
    return user


def manager(user=Depends(member)):
    if user.role not in {'Admin', 'HR'}:
        raise HTTPException(403, 'EMS salary is available only to Admin and HR')
    return user


def record(db, actor, action, target, details=''):
    db.add(M.EMSAudit(actor_id=actor.id, name=actor.full_name or actor.username,
                      action=action, target=str(target), details=details))


def serialize(row, name=None):
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    if name is not None:
        data['name'] = name
    return data


def user_data(user, card, store):
    return {'id': user.id, 'name': user.full_name or user.username, 'email': user.email,
            'role': 'admin' if user.role == 'Admin' else 'hr' if user.role == 'HR' else 'employee',
            'erp_role': user.role, 'can_manage_users': user.role in ('Admin', 'HR'),
            'status': (user.status or '').lower(), 'employee_id': card.employee_id if card else '',
            'department': user.category_code or '', 'designation': card.designation if card else user.role,
            'outlet': store.name if store else '', 'phone': card.mobile if card else '',
            'joining_date': card.joining_date if card else None, 'photo': card.photo if card else None}


def employee_rows(db, include_excluded=True):
    query = (db.query(models.User, models.IdentityCard, models.Store)
            .outerjoin(models.IdentityCard, models.IdentityCard.user_id == models.User.id)
            .outerjoin(models.Store, models.User.store_id == models.Store.id)
            .filter(~models.User.role.in_(EMS_EXCLUDED_ROLES), models.User.ems_deleted.is_(False)))
    if not include_excluded:
        query = query.filter(~models.User.id.in_(db.query(M.EMSExcludedEmployee.user_id)))
    return query


def lock_employee(db, user_id, salary_only=True):
    user = db.get(models.User, user_id)
    if not user or user.ems_deleted or user.status != 'Active' or user.role in EMS_EXCLUDED_ROLES or (salary_only and db.get(M.EMSExcludedEmployee, user_id)):
        raise HTTPException(404, 'Active ERP employee not found')
    # Serialize earning/payroll and leave changes per employee on SQLite and PostgreSQL.
    db.query(models.User).filter(models.User.id == user_id).update({models.User.id: user_id})
    return user


def scoped_rows(db, model, user):
    query = db.query(model, models.User.full_name, models.User.username).join(models.User, model.user_id == models.User.id)
    query = query.filter(~models.User.role.in_(EMS_EXCLUDED_ROLES), models.User.ems_deleted.is_(False))
    if not auth.has_admin_access(user):
        query = query.filter(model.user_id == user.id)
    query = query.order_by(model.month.desc(), model.id.desc()) if hasattr(model, 'month') else query.order_by(model.id.desc())
    result = [serialize(row, name or username) for row, name, username in query.all()]
    if model is M.EMSPayroll and result:
        ids = {row['user_id'] for row in result}
        cards = dict(db.query(models.IdentityCard.user_id, models.IdentityCard.employee_id).filter(models.IdentityCard.user_id.in_(ids)).all())
        for row in result:
            row['employee_id'] = cards.get(row['user_id'], '')
    return result


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
                           

class Leave(Input):
    start_date: date
    end_date: date
    kind: str
    reason: str = Field(min_length=3, max_length=500)


class Decision(Input):
    status: str


class Earning(Input):
    user_id: int
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    kind: str
    amount: Decimal = Field(gt=0, le=10000000, decimal_places=2)
    note: str = Field(min_length=3, max_length=300)


class Payroll(Input):
    user_id: int
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    basic: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    allowances: Decimal = Field(default=0, ge=0, le=10000000, decimal_places=2)
    deductions: Decimal = Field(default=0, ge=0, le=10000000, decimal_places=2)


@pages.get('/ems', response_class=HTMLResponse)
@pages.get('/ems.html', response_class=HTMLResponse)
def ems_page():
    html = (ROOT / 'static' / 'ems.html').read_text(encoding='utf-8')
    html = html.replace('<html lang="en">', '<html lang="en" data-erp="true">')
    html = html.replace('"/static/', '"ems-assets/')
    return HTMLResponse(html, headers={'Cache-Control': 'no-cache'})


@router.get('/me')
def me(db: Session = Depends(get_db), user=Depends(member)):
    return user_data(user, db.get(models.IdentityCard, user.id),
                     db.get(models.Store, user.store_id) if user.store_id else None)


@router.get('/employees')
def employees(db: Session = Depends(get_db), user=Depends(manager)):
    return [user_data(*row) for row in employee_rows(db).order_by(models.User.full_name).all()]


@router.get('/attendance')
def attendance(db: Session = Depends(get_db), user=Depends(member)):
    query = (db.query(models.AttendanceRecord, models.User.full_name, models.User.username)
             .join(models.User, models.User.id == models.AttendanceRecord.user_id)
             .filter(models.User.role != 'BrandPartner')
             .options(defer(models.AttendanceRecord.checkin_selfie), defer(models.AttendanceRecord.second_punch_selfie), defer(models.AttendanceRecord.checkout_selfie)))
    if not auth.has_admin_access(user):
        query = query.filter(models.AttendanceRecord.user_id == user.id)
    def stamp(value):
        return value.replace(tzinfo=IST).isoformat() if value else None
    return [{'id': row.id, 'user_id': row.user_id, 'name': name or username,
             'day': row.attendance_date, 'check_in': stamp(row.checkin_at), 'check_out': stamp(row.checkout_at)}
            for row, name, username in query.order_by(models.AttendanceRecord.attendance_date.desc()).limit(500).all()]


@router.get('/attendance-summary')
def attendance_summary(day: date | None = None, month: str | None = None,
                       db: Session = Depends(get_db), user=Depends(manager)):
    selected = day or datetime.now(IST).date()
    start = end = selected
    if month:
        try:
            start = datetime.strptime(month, '%Y-%m').date().replace(day=1)
        except ValueError:
            raise HTTPException(400, 'Month must be YYYY-MM')
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    staff = employee_rows(db).filter(models.User.status == 'Active').order_by(models.User.full_name).all()
    ids = [employee.id for employee, _, _ in staff]
    records = db.query(models.AttendanceRecord).options(
        defer(models.AttendanceRecord.checkin_selfie), defer(models.AttendanceRecord.second_punch_selfie),
        defer(models.AttendanceRecord.checkout_selfie)).filter(
        models.AttendanceRecord.user_id.in_(ids), models.AttendanceRecord.attendance_date.between(start, end)).all()
    punches = {(record.user_id, record.attendance_date): record for record in records}
    leave_days = {(item.user_id, item.leave_date) for item in db.query(models.AttendanceLeave).filter(
        models.AttendanceLeave.user_id.in_(ids), models.AttendanceLeave.leave_date.between(start, end)).all()}
    manual = {(r.user_id, r.day): r.status for r in db.query(M.EMSManualAttendance).filter(M.EMSManualAttendance.day.between(start, end)).all()}
    rows = []
    for offset in range((end - start).days + 1):
        current = start + timedelta(days=offset)
        for employee, card, store in staff:
            record = punches.get((employee.id, current))
            state = daily_attendance_status(employee, current, datetime.now(IST).date(),
                                            bool(record and record.checkin_at), (employee.id, current) in leave_days)
            if current <= datetime.now(IST).date():
                state = manual.get((employee.id, current), 'unrecorded' if employee.role == 'EMSManual' else state)
            status = {'unrecorded': 'Not entered', 'present': 'Present', 'absent': 'Absent', 'weekoff': 'Week Off',
                      'leave': 'Leave', 'upcoming': 'Upcoming'}[state]
            rows.append({'user_id': employee.id, 'name': employee.full_name or employee.username,
                         'employee_id': card.employee_id if card else '', 'day': current.isoformat(),
                         'outlet': store.name if store else 'Unassigned', 'department': employee.category_code or 'Unassigned',
                         'weekoff_day': employee.weekoff_day or '', 'status': status,
                         'check_in': record.checkin_at.replace(tzinfo=IST).isoformat() if record and record.checkin_at else None,
                         'check_out': record.checkout_at.replace(tzinfo=IST).isoformat() if record and record.checkout_at else None})
    return {'day': selected.isoformat(), 'rows': rows}


@router.get('/leave')
def leaves(db: Session = Depends(get_db), user=Depends(member)):
    return scoped_rows(db, M.EMSLeaveRequest, user)


@router.post('/leave', status_code=201)
def request_leave(payload: Leave, db: Session = Depends(get_db), user=Depends(member)):
    if payload.end_date < payload.start_date or (payload.end_date-payload.start_date).days > 365:
        raise HTTPException(422, 'Choose a valid date range of up to one year')
    if payload.kind not in ('Casual', 'Sick', 'Earned', 'Unpaid'):
        raise HTTPException(422, 'Invalid leave type')
    lock_employee(db, user.id, salary_only=False)
    if db.query(M.EMSLeaveRequest).filter(M.EMSLeaveRequest.user_id == user.id,
            M.EMSLeaveRequest.status != 'rejected', M.EMSLeaveRequest.start_date <= payload.end_date,
            M.EMSLeaveRequest.end_date >= payload.start_date).first():
        raise HTTPException(409, 'These dates overlap an existing leave request')
    row = M.EMSLeaveRequest(user_id=user.id, **payload.model_dump())
    db.add(row); db.flush()
    record(db, user, 'leave_requested', row.id)
    db.commit()
    return {'message': 'Leave request sent to HR'}


@router.put('/leave/{leave_id}')
def decide_leave(leave_id: int, payload: Decision, db: Session = Depends(get_db), user=Depends(manager)):
    if payload.status not in ('approved', 'rejected'):
        raise HTTPException(422, 'Choose approved or rejected')
    row = db.get(M.EMSLeaveRequest, leave_id)
    if not row:
        raise HTTPException(404, 'Leave request not found')
    if row.user_id == user.id:
        raise HTTPException(403, 'Another manager must review your leave')
    lock_employee(db, row.user_id, salary_only=False)
    db.refresh(row)
    if row.status != 'pending':
        raise HTTPException(409, 'This request has already been reviewed')
    if payload.status == 'approved':
        if db.query(models.AttendanceRecord).filter(models.AttendanceRecord.user_id == row.user_id,
                models.AttendanceRecord.attendance_date.between(row.start_date, row.end_date),
                models.AttendanceRecord.checkin_at.isnot(None)).first():
            raise HTTPException(409, 'Attendance is already recorded within these dates')
        day = row.start_date
        while day <= row.end_date:
            if not db.query(models.AttendanceLeave).filter_by(user_id=row.user_id, leave_date=day).first():
                db.add(models.AttendanceLeave(user_id=row.user_id, leave_date=day, created_by=user.id))
            day += timedelta(days=1)
    row.status = payload.status; row.reviewer_id = user.id
    record(db, user, 'leave_' + payload.status, row.id)
    db.commit()
    return {'message': 'Leave decision saved'}


@router.get('/earnings')
def earnings(db: Session = Depends(get_db), user=Depends(manager)):
    return scoped_rows(db, M.EMSEarning, user)


@router.post('/earnings', status_code=201)
def add_earning(payload: Earning, db: Session = Depends(get_db), user=Depends(manager)):
    if payload.kind not in ('incentive', 'bonus'):
        raise HTTPException(422, 'Choose incentive or bonus')
    lock_employee(db, payload.user_id)
    if db.query(M.EMSPayroll).filter_by(user_id=payload.user_id, month=payload.month).first():
        raise HTTPException(409, 'Payroll is already published for this month. Use a later month for adjustments.')
    row = M.EMSEarning(**{**payload.model_dump(), 'amount': int(payload.amount*100)}, created_by=user.id)
    db.add(row); db.flush()
    record(db, user, 'earning_approved', row.id, payload.model_dump_json())
    db.commit()
    return {'message': 'Earning approved and recorded'}


@router.get('/payroll')
def payroll(db: Session = Depends(get_db), user=Depends(manager)):
    return scoped_rows(db, M.EMSPayroll, user)


@router.put('/earnings/{earning_id}/void')
def void_earning(earning_id: int, db: Session = Depends(get_db), user=Depends(manager)):
    row = db.get(M.EMSEarning, earning_id)
    if not row:
        raise HTTPException(404, 'Earning not found')
    lock_employee(db, row.user_id)
    db.refresh(row)
    if db.query(M.EMSPayroll).filter_by(user_id=row.user_id, month=row.month).first():
        raise HTTPException(409, 'Published salary earnings cannot be changed')
    if row.status != 'approved':
        raise HTTPException(409, 'Earning is no longer approved')
    row.status = 'voided'
    record(db, user, 'earning_voided', row.id)
    db.commit()
    return {'message': 'Earning voided; draft salary will be recalculated'}


@router.post('/payroll', status_code=201)
def publish_payroll(payload: Payroll, db: Session = Depends(get_db), user=Depends(manager)):
    lock_employee(db, payload.user_id)
    values = dict(db.query(M.EMSEarning.kind, func.sum(M.EMSEarning.amount)).filter_by(
        user_id=payload.user_id, month=payload.month, status='approved').group_by(M.EMSEarning.kind).all())
    incentive, bonus = values.get('incentive', 0), values.get('bonus', 0)
    basic, allowances, deductions = (int(value*100) for value in (payload.basic, payload.allowances, payload.deductions))
    net = basic + allowances + incentive + bonus - deductions
    if net < 0:
        raise HTTPException(422, 'Deductions cannot exceed gross earnings')
    row = M.EMSPayroll(user_id=payload.user_id, month=payload.month, basic=basic, allowances=allowances,
                      deductions=deductions, incentives=incentive, bonuses=bonus, net=net, created_by=user.id)
    try:
        db.add(row); db.flush()
        record(db, user, 'payroll_published', row.id, payload.model_dump_json())
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Payroll is already published for this employee and month')
    return {'message': 'Payslip published to the employee dashboard'}


@router.put('/payroll/{payroll_id}/paid')
def mark_paid(payroll_id: int, db: Session = Depends(get_db), user=Depends(manager)):
    count = db.query(M.EMSPayroll).filter_by(id=payroll_id, status='published').update({'status': 'paid'})
    if count != 1:
        raise HTTPException(409, 'Payslip is missing or already marked paid')
    record(db, user, 'payroll_marked_paid', payroll_id)
    db.commit()
    return {'message': 'External salary payment recorded as paid. No funds are transferred by EMS.'}


@router.get('/audit')
def audit(db: Session = Depends(get_db), user=Depends(manager)):
    return [serialize(row) for row in db.query(M.EMSAudit).order_by(M.EMSAudit.id.desc()).limit(300).all()]


class SalarySetup(Input):
    user_id: int
    effective_month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    basic: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    allowances: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    deductions: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    divisor: Literal['calendar', '30']
    paid_weekoff: bool
    paid_leave: bool
    weekoff_availed: int = Field(default=0, ge=0, le=31, strict=True)
    weekoff_credit: int = Field(default=4, ge=0, le=4, strict=True)
    weekoff_pay: Decimal = Field(default=Decimal(0), ge=0, le=10000000, decimal_places=2)
    setup_incentive: Decimal = Field(default=Decimal(0), ge=0, le=10000000, decimal_places=2)
    employment_category: Literal['Regular', 'Contract'] | None = None
    account_no: str = Field(default='', max_length=40, pattern=r'^[0-9]*$')
    ifsc_code: str = Field(default='', max_length=11, pattern=r'^(?:[A-Za-z]{4}0[A-Za-z0-9]{6})?$')


class SalaryRun(Input):
    user_id: int
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    acknowledge_pending_incentive: bool = False
    preview: dict


def month_bounds(value):
    try:
        start = datetime.strptime(value, '%Y-%m').date().replace(day=1)
        if start.strftime('%Y-%m') != value:
            raise ValueError()
        return start, start.replace(day=calendar.monthrange(start.year, start.month)[1])
    except (ValueError, TypeError):
        raise HTTPException(422, 'Month must be YYYY-MM with a valid year')


@router.get('/salary-profiles')
def salary_profiles(db: Session = Depends(get_db), user=Depends(manager)):
    return [serialize(row) for row in db.query(M.EMSSalaryProfile).join(
        models.User, models.User.id == M.EMSSalaryProfile.user_id).filter(
        ~models.User.role.in_(EMS_EXCLUDED_ROLES), models.User.ems_deleted.is_(False)).order_by(
        M.EMSSalaryProfile.effective_month.desc()).all()]


@router.post('/salary-profiles')
def save_salary_profile(payload: SalarySetup, db: Session = Depends(get_db), user=Depends(manager)):
    month_bounds(payload.effective_month)
    lock_employee(db, payload.user_id)
    # Retrospective edits would change the basis of an already published salary.
    if db.query(M.EMSPayroll).filter(M.EMSPayroll.user_id == payload.user_id,
                                   M.EMSPayroll.month >= payload.effective_month).first():
        raise HTTPException(409, 'Choose an effective month after the latest published payroll')
    row = db.query(M.EMSSalaryProfile).filter_by(user_id=payload.user_id,
                                               effective_month=payload.effective_month).first()
    if row is None:
        row = M.EMSSalaryProfile(user_id=payload.user_id, effective_month=payload.effective_month)
        db.add(row)
    for key in ('basic', 'allowances', 'deductions', 'weekoff_pay', 'setup_incentive'):
        setattr(row, key, int(getattr(payload, key) * 100))
    row.divisor = '30'
    row.paid_weekoff = int(payload.paid_weekoff)
    row.paid_leave = int(payload.paid_leave)
    daily_rows = attendance_summary(day=None, month=payload.effective_month, db=db, user=user)['rows']
    row.weekoff_availed = sum(1 for day in daily_rows
                             if day['user_id'] == payload.user_id and day['status'] == 'Week Off')
    row.weekoff_credit = max(0, 4 - row.weekoff_availed)
    row.weekoff_pay = int((Decimal(row.basic + row.allowances) * row.weekoff_credit / Decimal(30)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if payload.employment_category is not None:
        row.employment_category = payload.employment_category
    row.account_no = payload.account_no
    row.ifsc_code = payload.ifsc_code.upper()
    row.created_by = user.id
    record(db, user, 'salary_profile_saved', payload.user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'Salary setup saved'}


def salary_preview(db, month):
    start, end = month_bounds(month)
    today = datetime.now(IST).date()
    rows = []
    profiles = db.query(M.EMSSalaryProfile).filter(M.EMSSalaryProfile.effective_month <= month).order_by(
        M.EMSSalaryProfile.effective_month.desc()).all()
    latest = {}
    for profile in profiles:
        latest.setdefault(profile.user_id, profile)
    punches = {(r.user_id, r.attendance_date) for r in db.query(
        models.AttendanceRecord.user_id, models.AttendanceRecord.attendance_date).filter(
        models.AttendanceRecord.attendance_date.between(start, end),
        models.AttendanceRecord.checkin_at.isnot(None)).all()}
    leaves = {(r.user_id, r.leave_date) for r in db.query(models.AttendanceLeave).filter(
        models.AttendanceLeave.leave_date.between(start, end)).all()}
    manual = {(r.user_id, r.day): r for r in db.query(M.EMSManualAttendance).filter(M.EMSManualAttendance.day.between(start, end)).all()}
    totals = {r.user_id: r for r in db.query(M.EMSAttendanceTotals).filter_by(month=month).all()}
    published = {r.user_id: r for r in db.query(M.EMSPayroll).filter_by(month=month).all()}
    earnings = {}
    for uid, kind, amount in db.query(M.EMSEarning.user_id, M.EMSEarning.kind, func.sum(M.EMSEarning.amount)).filter(
            M.EMSEarning.month == month, M.EMSEarning.status == 'approved').group_by(
                M.EMSEarning.user_id, M.EMSEarning.kind).all():
        earnings.setdefault(uid, {})[kind] = amount
    for employee, card, store in employee_rows(db, include_excluded=False).filter(models.User.status == 'Active').order_by(models.User.full_name).all():
        joining = card.joining_date if card and card.joining_date else employee.created_date.date() if employee.created_date else start
        counts = dict(present=0, absent=0, weekoff=0, leave=0, upcoming=0, before_joining=0)
        pay_counts = dict(counts)
        days = []
        missing_attendance = 0
        for offset in range((end-start).days+1):
            day = start + timedelta(days=offset)
            state = daily_attendance_status(employee, day, today,
                                            (employee.id, day) in punches, (employee.id, day) in leaves)
            manual_day = manual.get((employee.id, day))
            if employee.role == 'EMSManual' and joining <= day <= today:
                state = manual_day.status if manual_day else 'absent'
                missing_attendance += int(manual_day is None)
            if manual_day and joining <= day <= today:
                state = manual_day.status
            counts[state] += 1
            before_joining = day < joining
            counts['before_joining'] += int(before_joining)
            pay_counts['before_joining' if before_joining else state] += 1
            days.append({'day': day.isoformat(), 'status': state,
                         'entered': bool(manual_day) if employee.role == 'EMSManual' else True,
                         'overridden': bool(manual_day),
                         'note': manual_day.note if manual_day else ''})
        totals_override = totals.get(employee.id)
        if totals_override:
            for key in ('present', 'absent', 'weekoff', 'leave'):
                counts[key] = getattr(totals_override, key)
                pay_counts[key] = counts[key]
        profile = latest.get(employee.id)
        saved = published.get(employee.id)
        row = dict(user_id=employee.id, name=employee.full_name or employee.username,
                   employee_id=card.employee_id if card else '',
                   category=employee.category_code if employee.role == 'EMSManual' else employee_category(employee),
                   outlet=store.name if store else 'Unassigned', department=employee.category_code or '',
                   erp_account_deleted=bool(employee.erp_deleted),
                   manual_employee=employee.role == 'EMSManual', missing_attendance=missing_attendance,
                   joining_date=joining.isoformat(),
                   joining_source='Joining date' if card and card.joining_date else 'ERP registration date',
                   weekoff_availed=counts['weekoff'], weekoff_credit=max(0, 4-counts['weekoff']),
                   employment_category=profile.employment_category if profile else None,
                   totals_overridden=bool(totals_override), counts=counts, days=days, profile_id=profile.id if profile else None,
                   published_id=saved.id if saved else None, status=saved.status if saved else 'draft',
                   incentive_status='Automatic allocation pending rules',
                   incentive=earnings.get(employee.id, {}).get('incentive', 0),
                   bonus=earnings.get(employee.id, {}).get('bonus', 0))
        if profile:
            payable = pay_counts['present'] + (pay_counts['weekoff'] if profile.paid_weekoff else 0) + (pay_counts['leave'] if profile.paid_leave else 0)
            unpaid = pay_counts['absent'] + pay_counts['before_joining'] + (0 if profile.paid_weekoff else pay_counts['weekoff']) + (0 if profile.paid_leave else pay_counts['leave'])
            divisor = 30
            # Deduct unpaid days; a fully paid month receives the full monthly salary.
            factor = max(Decimal(0), Decimal(1) - Decimal(unpaid)/Decimal(divisor))
            if unpaid == (end-start).days+1:
                factor = Decimal(0)
            prorate = lambda value: int((Decimal(value)*factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            basic, allowance = prorate(profile.basic), prorate(profile.allowances)
            row.update(basic=basic, allowances=allowance, deductions=profile.deductions,
                       monthly_basic=profile.basic, monthly_allowances=profile.allowances,
                       divisor='30', paid_weekoff=bool(profile.paid_weekoff), paid_leave=bool(profile.paid_leave),
                       payable_days=payable, unpaid_days=unpaid,
                       net=basic+allowance+row['incentive']+row['bonus']-profile.deductions)
        row['can_publish'] = bool(profile and end < today and not saved and row.get('net', -1) >= 0 and joining <= end and not missing_attendance)
        rows.append(row)
    return {'month': month, 'closed_month': end < today, 'rows': rows}


@router.get('/salary-preview')
def preview_salary(month: str, db: Session = Depends(get_db), user=Depends(manager)):
    month_bounds(month)
    return salary_preview(db, month)


@router.post('/salary-publish', status_code=201)
def publish_salary(payload: SalaryRun, db: Session = Depends(get_db), user=Depends(manager)):
    lock_employee(db, payload.user_id)
    row = next((r for r in salary_preview(db, payload.month)['rows'] if r['user_id'] == payload.user_id), None)
    if not row or not row['can_publish']:
        raise HTTPException(409, 'Publication requires a closed month, salary setup and no existing payroll')
    if not payload.acknowledge_pending_incentive:
        raise HTTPException(422, 'Acknowledge that automatic incentive allocation is pending')
    if payload.preview != row:
        raise HTTPException(409, 'Attendance or salary values changed. Refresh and review the preview again.')
    payroll = M.EMSPayroll(user_id=payload.user_id, month=payload.month, basic=row['basic'],
        allowances=row['allowances'], deductions=row['deductions'], incentives=row['incentive'],
        bonuses=row['bonus'], net=row['net'], created_by=user.id)
    try:
        db.add(payroll); db.flush()
        db.add(M.EMSPayrollSnapshot(payroll_id=payroll.id, details=json.dumps(row)))
        record(db, user, 'salary_published_from_attendance', payroll.id, json.dumps(row))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Payroll already exists for this employee and month')
    return {'message': 'Salary published', 'id': payroll.id}


@router.get('/salary-slips/{payroll_id}')
def salary_slip(payroll_id: int, db: Session = Depends(get_db), user=Depends(manager)):
    payroll = db.get(M.EMSPayroll, payroll_id)
    if not payroll:
        raise HTTPException(404, 'Salary record not found')
    snapshot = db.query(M.EMSPayrollSnapshot).filter_by(payroll_id=payroll_id).first()
    return {'payroll': serialize(payroll), 'snapshot': json.loads(snapshot.details) if snapshot else None}


@router.get('/excluded-employees')
def excluded_salary_employees(db: Session = Depends(get_db), user=Depends(manager)):
    return [dict(user_id=employee.id, name=employee.full_name or employee.username,
                 employee_id=card.employee_id if card else '')
            for employee, card, store in employee_rows(db, include_excluded=True).filter(
                models.User.id.in_(db.query(M.EMSExcludedEmployee.user_id))).all()]


class RemovalPassword(Input):
    password: SecretStr = Field(min_length=1, max_length=1024)


class SalaryRemoval(RemovalPassword):
    confirmation: Literal['REMOVE']


def verify_removal_password(payload, user):
    try:
        valid = auth.verify_password(payload.password.get_secret_value(), user.password_hash)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(403, 'Incorrect password. Enter your own login password.')


@router.post('/employees/{user_id}/removal-password')
def check_removal_password(user_id: int, payload: RemovalPassword,
                           db: Session = Depends(get_db), user=Depends(manager)):
    employee = db.get(models.User, user_id)
    if not employee or employee.ems_deleted or employee.role in EMS_EXCLUDED_ROLES:
        raise HTTPException(404, 'ERP employee not found')
    verify_removal_password(payload, user)
    return {'message': 'Password verified. Type REMOVE to confirm.'}


@router.put('/employees/{user_id}/exclude')
def exclude_salary_employee(user_id: int, payload: SalaryRemoval,
                            db: Session = Depends(get_db), user=Depends(manager)):
    verify_removal_password(payload, user)
    employee = db.get(models.User, user_id)
    if not employee or employee.ems_deleted or employee.role in EMS_EXCLUDED_ROLES:
        raise HTTPException(404, 'ERP employee not found')
    db.query(models.User).filter(models.User.id == user_id).update({models.User.id: user_id})
    if not db.get(M.EMSExcludedEmployee, user_id):
        db.add(M.EMSExcludedEmployee(user_id=user_id, created_by=user.id))
        record(db, user, 'employee_excluded_from_salary', user_id)
    db.commit()
    return {'message': 'Employee removed from EMS salary list. ERP records are preserved.'}


@router.delete('/employees/{user_id}/exclude')
def restore_salary_employee(user_id: int, db: Session = Depends(get_db), user=Depends(manager)):
    employee = db.get(models.User, user_id)
    if not employee or employee.ems_deleted:
        raise HTTPException(404, 'EMS employee not found')
    row = db.get(M.EMSExcludedEmployee, user_id)
    if row:
        db.delete(row)
        record(db, user, 'employee_restored_to_salary', user_id)
        db.commit()
    return {'message': 'Employee restored to EMS salary list'}

class ManualEmployee(Input):
    full_name: str = Field(min_length=2, max_length=150)
    joining_date: date
    phone: str = Field(default='', max_length=25)
    designation: str = Field(default='Employee', min_length=2, max_length=100)
    employee_group: Literal['ids_emp', 'ac_retails', 'ac_projects'] = 'ids_emp'
    store_id: int | None = None
    weekoff_day: Literal['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] | None = None


class ManualDay(Input):
    day: date
    status: Literal['present', 'absent', 'weekoff', 'leave']
    note: str = Field(default='', max_length=300)


class ManualAttendanceInput(Input):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    days: list[ManualDay] = Field(min_length=1, max_length=31)


@router.get('/manual-employee-options')
def manual_employee_options(db: Session = Depends(get_db), user=Depends(manager)):
    return {'stores': [{'id': row.id, 'name': row.name} for row in db.query(models.Store).filter(
        models.Store.status == 'Active').order_by(models.Store.name).all()]}


@router.get('/manual-employee-id')
def manual_employee_id(store_id: int | None = None, db: Session = Depends(get_db), user=Depends(manager)):
    from identity_cards import outlet_abbreviation, preview_employee_id
    store = db.get(models.Store, store_id) if store_id is not None else None
    if store_id is not None and (not store or store.status != 'Active'):
        raise HTTPException(422, 'Choose an active outlet')
    return {'employee_id': preview_employee_id(db, outlet_abbreviation(store))}


@router.post('/manual-employees', status_code=201)
def add_manual_employee(payload: ManualEmployee, db: Session = Depends(get_db), user=Depends(manager)):
    from uuid import uuid4
    import secrets
    from identity_cards import outlet_abbreviation, next_employee_id
    store = None
    if payload.joining_date > datetime.now(IST).date():
        raise HTTPException(422, 'Joining date cannot be in the future')
    if payload.store_id is not None:
        store = db.get(models.Store, payload.store_id)
        if not store or store.status != 'Active':
            raise HTTPException(422, 'Choose an active outlet')
    employee = models.User(username='manual_' + uuid4().hex[:24], full_name=payload.full_name,
        email=uuid4().hex+'@manual.invalid', password_hash=auth.hash_password(secrets.token_urlsafe(48)),
        role='EMSManual', status='Active', category_code=payload.employee_group,
        store_id=payload.store_id, weekoff_day=payload.weekoff_day)
    try:
        db.add(employee); db.flush()
        assigned_id = next_employee_id(db, outlet_abbreviation(store))
        db.add(models.IdentityCard(user_id=employee.id, employee_id=assigned_id,
            employee_name=payload.full_name, designation=payload.designation,
            mobile=payload.phone, joining_date=payload.joining_date))
        record(db, user, 'manual_employee_created', employee.id, payload.model_dump_json())
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Employee ID already exists')
    return {'message': f'Manual employee {assigned_id} added. Set up salary and enter attendance.',
            'user_id': employee.id, 'employee_id': assigned_id}


@router.put('/manual-employees/{user_id}/attendance')
def save_manual_attendance(user_id: int, payload: ManualAttendanceInput,
                           db: Session = Depends(get_db), user=Depends(manager)):
    employee = lock_employee(db, user_id)
    if employee.role != 'EMSManual':
        raise HTTPException(422, 'Manual attendance is for manually added employees')
    start, end = month_bounds(payload.month)
    if db.query(M.EMSPayroll).filter_by(user_id=user_id, month=payload.month).first():
        raise HTTPException(409, 'Published salary attendance cannot be changed')
    card = db.get(models.IdentityCard, user_id)
    if len({entry.day for entry in payload.days}) != len(payload.days):
        raise HTTPException(422, 'Each attendance date must be unique')
    for entry in payload.days:
        if not start <= entry.day <= end or entry.day > datetime.now(IST).date() or (card and card.joining_date and entry.day < card.joining_date):
            raise HTTPException(422, 'Attendance dates must be within this month, on or after joining, and not in the future')
    for entry in payload.days:
        row = db.query(M.EMSManualAttendance).filter_by(user_id=user_id, day=entry.day).first()
        if row is None:
            row = M.EMSManualAttendance(user_id=user_id, day=entry.day)
            db.add(row)
        row.status = entry.status; row.note = entry.note; row.updated_by = user.id
        row.updated_at = datetime.utcnow()
    record(db, user, 'manual_attendance_saved', user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'Manual attendance saved and draft salary recalculated'}

class AttendanceCorrectionDay(ManualDay):
    status: Literal['present', 'absent', 'weekoff', 'leave', 'auto']


class AttendanceCorrectionInput(ManualAttendanceInput):
    days: list[AttendanceCorrectionDay] = Field(min_length=1, max_length=31)


@router.put('/attendance-records/{user_id}')
def save_attendance_corrections(user_id: int, payload: AttendanceCorrectionInput,
                               db: Session = Depends(get_db), user=Depends(manager)):
    # EMS-only overrides: never update source punches, leave records or weekly schedules.
    employee = lock_employee(db, user_id)
    start, end = month_bounds(payload.month)
    if db.query(M.EMSPayroll).filter_by(user_id=user_id, month=payload.month).first():
        raise HTTPException(409, 'Published salary attendance cannot be changed')
    card = db.get(models.IdentityCard, user_id)
    joining = card.joining_date if card and card.joining_date else employee.created_date.date() if employee.created_date else start
    if len({entry.day for entry in payload.days}) != len(payload.days):
        raise HTTPException(422, 'Each attendance date must be unique')
    for entry in payload.days:
        if not start <= entry.day <= end or entry.day > datetime.now(IST).date() or entry.day < joining:
            raise HTTPException(422, 'Attendance dates must be within this month, on or after joining, and not in the future')
    for entry in payload.days:
        row = db.query(M.EMSManualAttendance).filter_by(user_id=user_id, day=entry.day).first()
        if entry.status == 'auto':
            if row is not None:
                db.delete(row)
            continue
        if row is None:
            row = M.EMSManualAttendance(user_id=user_id, day=entry.day)
            db.add(row)
        row.status = entry.status
        row.note = entry.note
        row.updated_by = user.id
        row.updated_at = datetime.utcnow()
    record(db, user, 'attendance_corrections_saved', user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'Attendance saved and draft salary recalculated'}


class EMSPermanentDeletion(RemovalPassword):
    confirmation: Literal['DELETE']


@router.delete('/employees/{user_id}')
def permanently_delete_ems_employee(user_id: int, payload: EMSPermanentDeletion,
                                    db: Session = Depends(get_db), user=Depends(manager)):
    verify_removal_password(payload, user)
    employee = db.get(models.User, user_id)
    if not employee or employee.ems_deleted or employee.role in EMS_EXCLUDED_ROLES:
        raise HTTPException(404, 'EMS employee not found')
    db.query(models.User).filter_by(id=user_id).update({models.User.id: user_id})
    payroll_ids = [row.id for row in db.query(M.EMSPayroll.id).filter_by(user_id=user_id).all()]
    earning_ids = [row.id for row in db.query(M.EMSEarning.id).filter_by(user_id=user_id).all()]
    leave_ids = [row.id for row in db.query(M.EMSLeaveRequest.id).filter_by(user_id=user_id).all()]
    db.query(M.EMSPayrollSnapshot).filter(M.EMSPayrollSnapshot.payroll_id.in_(payroll_ids)).delete(synchronize_session=False)
    # Remove employee-specific audit payloads which duplicate salary/profile details.
    audit_groups = [
        (['salary_profile_saved', 'employee_excluded_from_salary', 'employee_restored_to_salary',
          'manual_employee_created', 'manual_attendance_saved', 'salary_distribution_inputs_saved'], [user_id]),
        (['payroll_published', 'payroll_marked_paid', 'salary_published_from_attendance'], payroll_ids),
        (['earning_approved', 'earning_voided'], earning_ids),
        (['leave_requested', 'leave_approved', 'leave_rejected'], leave_ids),
    ]
    for actions, targets in audit_groups:
        db.query(M.EMSAudit).filter(M.EMSAudit.action.in_(actions),
            M.EMSAudit.target.in_([str(value) for value in targets])).delete(synchronize_session=False)
    for model in (M.EMSAttendanceTotals, M.EMSWeekoffIncentive, M.EMSDistributionInput, M.EMSManualAttendance, M.EMSExcludedEmployee, M.EMSLeaveRequest,
                  M.EMSEarning, M.EMSSalaryProfile, M.EMSPayroll):
        db.query(model).filter_by(user_id=user_id).delete(synchronize_session=False)
    # Tombstone prevents an ERP account from automatically reappearing in EMS.
    # Shared ERP identity and attendance remain owned by that account.
    employee.ems_deleted = True
    record(db, user, 'employee_permanently_deleted_from_ems', user_id)
    db.commit()
    return {'message': 'Employee permanently deleted from EMS. Salary history and manual attendance were deleted. ERP account records are preserved.'}

# Retired IDS NEW fields are removed from legacy storage without rewriting
# published payroll amounts or touching shared ERP/attendance tables.
def remove_retired_ids_data(connection):
    from sqlalchemy import inspect, text
    tables = set(inspect(connection).get_table_names())
    if 'ems_salary_profiles' in tables:
        columns = {column['name'] for column in inspect(connection).get_columns('ems_salary_profiles')}
        if 'ids_attributes' in columns:
            connection.execute(text('UPDATE ems_salary_profiles SET ids_attributes = NULL WHERE ids_attributes IS NOT NULL'))
    retired = {'ids_attributes', 'actual_vda', 'actual_pay_epf', 'actual_oa',
               'total_earning', 'bonus_payable', 'actual_gross_earning',
               'epf_employee', 'esic_employee', 'staff_advance', 'working_days'}
    parameters = {f'key_{index}': f'%"{key}"%' for index, key in enumerate(sorted(retired))}
    condition = ' OR '.join(f'details LIKE :{key}' for key in parameters)
    for table in ('ems_payroll_snapshots', 'ems_audit'):
        if table not in tables:
            continue
        scope = " AND action IN ('salary_profile_saved', 'salary_published_from_attendance')" if table == 'ems_audit' else ''
        rows = connection.execute(text(f'SELECT id, details FROM {table} WHERE ({condition}){scope}'), parameters).all()
        for row in rows:
            try:
                details = json.loads(row.details)
            except (ValueError, TypeError):
                continue
            if not isinstance(details, dict) or not retired.intersection(details):
                continue
            cleaned = {key: value for key, value in details.items() if key not in retired}
            connection.execute(text(f'UPDATE {table} SET details = :details WHERE id = :id'),
                               {'id': row.id, 'details': json.dumps(cleaned)})

class DistributionInput(Input):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    other_allowances: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    staff_advance: Decimal = Field(ge=0, le=10000000, decimal_places=2)


@router.get('/salary-distribution')
def salary_distribution(month: str, db: Session = Depends(get_db), user=Depends(manager)):
    from salary_distribution import calculate_distribution
    preview = salary_preview(db, month)
    inputs = {row.user_id: row for row in db.query(M.EMSDistributionInput).filter_by(month=month).all()}
    profiles = {row.id: row for row in db.query(M.EMSSalaryProfile).all()}
    rows = []
    for employee in preview['rows']:
        profile = profiles.get(employee['profile_id'])
        saved = inputs.get(employee['user_id'])
        attendance_absent = employee['counts']['absent']
        calculated = calculate_distribution(profile.basic + profile.allowances if profile else 0,
            attendance_absent, saved.other_allowances if saved else 0, saved.staff_advance if saved else 0)
        rows.append(dict(**calculated, user_id=employee['user_id'], name=employee['name'],
            employee_id=employee['employee_id'], profile_id=employee['profile_id'],
            attendance_absent=attendance_absent, missing_attendance=employee['missing_attendance'],
            account_no=profile.account_no or '' if profile else '',
            ifsc_code=profile.ifsc_code or '' if profile else ''))
    return {'month': month, 'closed_month': preview['closed_month'], 'rows': rows}


@router.put('/salary-distribution/{user_id}')
def save_distribution_inputs(user_id: int, payload: DistributionInput,
                             db: Session = Depends(get_db), user=Depends(manager)):
    month_bounds(payload.month)
    lock_employee(db, user_id)
    if not db.query(M.EMSSalaryProfile).filter(M.EMSSalaryProfile.user_id == user_id,
            M.EMSSalaryProfile.effective_month <= payload.month).first():
        raise HTTPException(409, 'Save salary setup for this employee and month first')
    row = db.query(M.EMSDistributionInput).filter_by(user_id=user_id, month=payload.month).first()
    if row is None:
        row = M.EMSDistributionInput(user_id=user_id, month=payload.month)
        db.add(row)
    row.other_allowances = int(payload.other_allowances * 100)
    row.staff_advance = int(payload.staff_advance * 100)
    row.updated_by = user.id
    row.updated_at = datetime.utcnow()
    record(db, user, 'salary_distribution_inputs_saved', user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'Salary distribution inputs saved'}


class WeekoffIncentiveInput(Input):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    incentive: Decimal = Field(ge=0, le=10000000, decimal_places=2)


@router.get('/weekoff-incentives')
def weekoff_incentives(month: str, db: Session = Depends(get_db), user=Depends(manager)):
    month_bounds(month)
    ids = [row.id for row, _, _ in employee_rows(db, include_excluded=False).all()]
    return [serialize(row) for row in db.query(M.EMSWeekoffIncentive).filter(
        M.EMSWeekoffIncentive.month == month, M.EMSWeekoffIncentive.user_id.in_(ids)).all()]


@router.put('/weekoff-incentives/{user_id}')
def save_weekoff_incentive(user_id: int, payload: WeekoffIncentiveInput,
                          db: Session = Depends(get_db), user=Depends(manager)):
    month_bounds(payload.month)
    lock_employee(db, user_id)
    row = db.query(M.EMSWeekoffIncentive).filter_by(user_id=user_id, month=payload.month).first()
    if row is None:
        row = M.EMSWeekoffIncentive(user_id=user_id, month=payload.month)
        db.add(row)
    row.incentive = int(payload.incentive * 100)
    row.updated_by = user.id
    row.updated_at = datetime.utcnow()
    record(db, user, 'weekoff_incentive_saved', user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'Weekoff incentive saved'}


class AttendanceTotalsInput(Input):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    present: int = Field(ge=0, le=31, strict=True)
    absent: int = Field(ge=0, le=31, strict=True)
    weekoff: int = Field(ge=0, le=31, strict=True)
    leave: int = Field(ge=0, le=31, strict=True)


@router.put('/attendance-totals/{user_id}')
def save_attendance_totals(user_id: int, payload: AttendanceTotalsInput,
                           db: Session = Depends(get_db), user=Depends(manager)):
    start, end = month_bounds(payload.month)
    lock_employee(db, user_id)
    if db.query(M.EMSPayroll).filter_by(user_id=user_id, month=payload.month).first():
        raise HTTPException(409, 'Published salary attendance cannot be changed')
    elapsed = max(0, (min(end, datetime.now(IST).date()) - start).days + 1)
    if sum(getattr(payload, k) for k in ('present', 'absent', 'weekoff', 'leave')) > elapsed:
        raise HTTPException(422, f'Attendance totals cannot exceed {elapsed} elapsed days in this month')
    row = db.query(M.EMSAttendanceTotals).filter_by(user_id=user_id, month=payload.month).first()
    if row is None:
        row = M.EMSAttendanceTotals(user_id=user_id, month=payload.month)
        db.add(row)
    for key in ('present', 'absent', 'weekoff', 'leave'):
        setattr(row, key, getattr(payload, key))
    row.updated_by = user.id
    row.updated_at = datetime.utcnow()
    record(db, user, 'attendance_totals_saved', user_id, payload.model_dump_json())
    db.commit()
    return {'message': 'EMS totals saved; daily attendance unchanged'}
