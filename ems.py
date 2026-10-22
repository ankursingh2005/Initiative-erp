"""ERP EMS API: existing authentication, employees, identity and attendance."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, defer
from sqlalchemy.exc import IntegrityError
import calendar
import json
from decimal import ROUND_HALF_UP
from typing import Literal
from attendance_history import weekoff_on
from attendance_categories import employee_category

import auth
import models
import ems_models as M
from database import get_db

router = APIRouter(prefix='/api/ems', tags=['EMS'])
pages = APIRouter()
ROOT = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))


def member(response: Response, user=Depends(auth.get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    if user.role not in {'Admin', 'HR'}:
        raise HTTPException(403, 'EMS is available only to Admin and HR')
    return user


def manager(user=Depends(member)):
    if not auth.has_admin_access(user):
        raise HTTPException(403, 'Admin, Owner or HR access required')
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
            'role': 'admin' if user.role == 'Admin' else 'hr' if user.role in ('Owner', 'HR') else 'employee',
            'erp_role': user.role, 'can_manage_users': user.role in ('Admin', 'HR'),
            'status': (user.status or '').lower(), 'employee_id': card.employee_id if card else '',
            'department': user.category_code or '', 'designation': card.designation if card else user.role,
            'outlet': store.name if store else '', 'phone': card.mobile if card else '',
            'joining_date': card.joining_date if card else None, 'photo': card.photo if card else None}


def employee_rows(db):
    return (db.query(models.User, models.IdentityCard, models.Store)
            .outerjoin(models.IdentityCard, models.IdentityCard.user_id == models.User.id)
            .outerjoin(models.Store, models.User.store_id == models.Store.id)
            .filter(models.User.role != 'BrandPartner'))


def lock_employee(db, user_id):
    user = db.get(models.User, user_id)
    if not user or user.status != 'Active' or user.role == 'BrandPartner':
        raise HTTPException(404, 'Active ERP employee not found')
    # Serialize earning/payroll and leave changes per employee on SQLite and PostgreSQL.
    db.query(models.User).filter(models.User.id == user_id).update({models.User.id: user_id})
    return user


def scoped_rows(db, model, user):
    query = db.query(model, models.User.full_name, models.User.username).join(models.User, model.user_id == models.User.id)
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
    return user_data(*employee_rows(db).filter(models.User.id == user.id).one())


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
    rows = []
    for offset in range((end - start).days + 1):
        current = start + timedelta(days=offset)
        for employee, card, store in staff:
            record = punches.get((employee.id, current))
            status = ('Present' if record and record.checkin_at else 'Leave' if (employee.id, current) in leave_days
                      else 'Week Off' if weekoff_on(employee, current) == current.strftime('%A') else 'Absent')
            if current > datetime.now(IST).date():
                status = 'Upcoming'
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
    lock_employee(db, user.id)
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
    lock_employee(db, row.user_id)
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
def earnings(db: Session = Depends(get_db), user=Depends(member)):
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
def payroll(db: Session = Depends(get_db), user=Depends(member)):
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
    return [serialize(row) for row in db.query(M.EMSSalaryProfile).order_by(
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
    for key in ('basic', 'allowances', 'deductions'):
        setattr(row, key, int(getattr(payload, key) * 100))
    row.divisor = payload.divisor
    row.paid_weekoff = int(payload.paid_weekoff)
    row.paid_leave = int(payload.paid_leave)
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
    published = {r.user_id: r for r in db.query(M.EMSPayroll).filter_by(month=month).all()}
    earnings = {}
    for uid, kind, amount in db.query(M.EMSEarning.user_id, M.EMSEarning.kind, func.sum(M.EMSEarning.amount)).filter(
            M.EMSEarning.month == month, M.EMSEarning.status == 'approved').group_by(
                M.EMSEarning.user_id, M.EMSEarning.kind).all():
        earnings.setdefault(uid, {})[kind] = amount
    for employee, card, store in employee_rows(db).filter(models.User.status == 'Active').order_by(models.User.full_name).all():
        joining = card.joining_date if card and card.joining_date else employee.created_date.date() if employee.created_date else start
        counts = dict(present=0, absent=0, weekoff=0, leave=0, upcoming=0, before_joining=0)
        days = []
        for offset in range((end-start).days+1):
            day = start + timedelta(days=offset)
            state = ('before_joining' if day < joining else 'upcoming' if day > today else
                     'present' if (employee.id, day) in punches else
                     'leave' if (employee.id, day) in leaves else
                     'weekoff' if weekoff_on(employee, day) == day.strftime('%A') else 'absent')
            counts[state] += 1
            days.append({'day': day.isoformat(), 'status': state})
        profile = latest.get(employee.id)
        saved = published.get(employee.id)
        row = dict(user_id=employee.id, name=employee.full_name or employee.username,
                   employee_id=card.employee_id if card else '', category=employee_category(employee),
                   outlet=store.name if store else 'Unassigned', department=employee.category_code or '',
                   joining_date=joining.isoformat(),
                   joining_source='Joining date' if card and card.joining_date else 'ERP registration date',
                   counts=counts, days=days, profile_id=profile.id if profile else None,
                   published_id=saved.id if saved else None, status=saved.status if saved else 'draft',
                   incentive_status='Automatic allocation pending rules',
                   incentive=earnings.get(employee.id, {}).get('incentive', 0),
                   bonus=earnings.get(employee.id, {}).get('bonus', 0))
        if profile:
            payable = counts['present'] + (counts['weekoff'] if profile.paid_weekoff else 0) + (counts['leave'] if profile.paid_leave else 0)
            unpaid = counts['absent'] + counts['before_joining'] + (0 if profile.paid_weekoff else counts['weekoff']) + (0 if profile.paid_leave else counts['leave'])
            divisor = 30 if profile.divisor == '30' else (end-start).days+1
            # Deduct unpaid days; a fully paid month receives the full monthly salary.
            factor = max(Decimal(0), Decimal(1) - Decimal(unpaid)/Decimal(divisor))
            if unpaid == (end-start).days+1:
                factor = Decimal(0)
            prorate = lambda value: int((Decimal(value)*factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            basic, allowance = prorate(profile.basic), prorate(profile.allowances)
            row.update(basic=basic, allowances=allowance, deductions=profile.deductions,
                       monthly_basic=profile.basic, monthly_allowances=profile.allowances,
                       divisor=profile.divisor, paid_weekoff=bool(profile.paid_weekoff), paid_leave=bool(profile.paid_leave),
                       payable_days=payable, unpaid_days=unpaid,
                       net=basic+allowance+row['incentive']+row['bonus']-profile.deductions)
        row['can_publish'] = bool(profile and end < today and not saved and row.get('net', -1) >= 0 and joining <= end)
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
