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

import auth
import models
import ems_models as M
from database import get_db
from identity_cards import ensure_employee_ids

router = APIRouter(prefix='/api/ems', tags=['EMS'])
pages = APIRouter()
ROOT = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))


def member(response: Response, user=Depends(auth.get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    if user.role == 'BrandPartner':
        raise HTTPException(403, 'Brand Promotor access remains limited to Home and Attendance')
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
    html = (ROOT / 'EMS' / 'static' / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<html lang="en">', '<html lang="en" data-erp="true">')
    html = html.replace('"/static/', '"ems-assets/')
    return HTMLResponse(html, headers={'Cache-Control': 'no-cache'})


@router.get('/me')
def me(db: Session = Depends(get_db), user=Depends(member)):
    ensure_employee_ids(db)
    return user_data(*employee_rows(db).filter(models.User.id == user.id).one())


@router.get('/employees')
def employees(db: Session = Depends(get_db), user=Depends(manager)):
    ensure_employee_ids(db)
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


@router.post('/payroll', status_code=201)
def publish_payroll(payload: Payroll, db: Session = Depends(get_db), user=Depends(manager)):
    lock_employee(db, payload.user_id)
    values = dict(db.query(M.EMSEarning.kind, func.sum(M.EMSEarning.amount)).filter_by(
        user_id=payload.user_id, month=payload.month).group_by(M.EMSEarning.kind).all())
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
