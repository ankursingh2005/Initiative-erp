"""Independent EMS application. Run from the EMS directory."""
import argparse
import base64
import getpass
import hashlib
import hmac
import io
import os
from pathlib import Path
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv('EMS_DATABASE', str(ROOT / 'data' / 'ems.sqlite3')))
IST = timezone(timedelta(hours=5, minutes=30))
SECURE_COOKIE = os.getenv('EMS_SECURE_COOKIE', '0') == '1'


def now():
    return datetime.now(IST).isoformat(timespec='seconds')


def today():
    return datetime.now(IST).date().isoformat()


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize():
    with db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee',
            status TEXT NOT NULL DEFAULT 'pending', department TEXT NOT NULL DEFAULT '',
            designation TEXT NOT NULL DEFAULT '', outlet TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '', joining_date TEXT, photo TEXT,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            csrf TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (
            email TEXT PRIMARY KEY, failures INTEGER NOT NULL, last_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            day TEXT NOT NULL, check_in TEXT NOT NULL, check_out TEXT,
            UNIQUE(user_id, day));
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, kind TEXT NOT NULL,
            reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            reviewer_id INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS earnings (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            month TEXT NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL,
            note TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'approved',
            created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            month TEXT NOT NULL, basic INTEGER NOT NULL, allowances INTEGER NOT NULL,
            deductions INTEGER NOT NULL, incentives INTEGER NOT NULL, bonuses INTEGER NOT NULL,
            net INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'published',
            created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
            UNIQUE(user_id, month));
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL, target TEXT NOT NULL, details TEXT NOT NULL,
            created_at TEXT NOT NULL);
        ''')


def audit(conn, actor, action, target, details=''):
    conn.execute('INSERT INTO audit(actor_id,action,target,details,created_at) VALUES(?,?,?,?,?)',
                 (actor, action, str(target), details, now()))


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def password_matches(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Credentials(Input):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=10, max_length=128)

    @field_validator('email')
    @classmethod
    def email_address(cls, value):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value.lower()


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default='', max_length=25)


class Profile(Input):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default='', max_length=25)
    photo: str | None = Field(default=None, max_length=3_000_000)


class EmployeeUpdate(Input):
    status: str
    role: str
    department: str = Field(default='', max_length=80)
    designation: str = Field(default='', max_length=100)
    outlet: str = Field(default='', max_length=80)
    joining_date: date | None = None


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


def public_user(row):
    result = dict(row)
    result.pop('password_hash', None)
    result['employee_id'] = f'EMS-{result["id"]:05d}'
    return result


def current_user(request: Request):
    token = request.cookies.get('ems_session', '')
    with db() as conn:
        session = conn.execute('SELECT * FROM sessions WHERE token_hash=? AND expires_at>?',
                               (hashlib.sha256(token.encode()).hexdigest(), now())).fetchone()
        if not session:
            raise HTTPException(401, 'Please sign in')
        user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if not user or user['status'] != 'active':
        raise HTTPException(403, 'Your account is awaiting approval or has been deactivated')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), session['csrf']):
            raise HTTPException(403, 'Session verification failed. Refresh and retry.')
    result = public_user(user)
    result['csrf'] = session['csrf']
    return result


def management(user=Depends(current_user)):
    if user['role'] not in ('admin', 'hr'):
        raise HTTPException(403, 'HR access required')
    return user


def require_employee(conn, user_id):
    row = conn.execute('SELECT * FROM users WHERE id=? AND status=?', (user_id, 'active')).fetchone()
    if not row:
        raise HTTPException(404, 'Active employee not found')
    return row


def money(value):
    return int(Decimal(value) * 100)


initialize()
app = FastAPI(title='EMS — Employee Management System', docs_url=None, redoc_url=None)


@app.middleware('http')
async def security_headers(request, call_next):
    # Same-origin application. Authenticated mutations also require a CSRF token.
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return Response('Cross-origin requests are not allowed', status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/api/register', status_code=201)
def register(payload: Registration):
    with db() as conn:
        try:
            result = conn.execute('INSERT INTO users(name,email,password_hash,phone,created_at) VALUES(?,?,?,?,?)',
                                  (payload.name, payload.email, password_hash(payload.password), payload.phone, now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'This email is already registered')
        audit(conn, result.lastrowid, 'registration', result.lastrowid)
    return {'message': 'Registration received. HR must approve your account before you can sign in.'}


@app.post('/api/login')
def login(payload: Credentials, response: Response):
    with db() as conn:
        attempt = conn.execute('SELECT * FROM login_attempts WHERE email=?', (payload.email,)).fetchone()
        cutoff = (datetime.now(IST) - timedelta(minutes=15)).isoformat(timespec='seconds')
        if attempt and attempt['failures'] >= 8 and attempt['last_at'] > cutoff:
            raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
        user = conn.execute('SELECT * FROM users WHERE email=?', (payload.email,)).fetchone()
        if not user or not password_matches(payload.password, user['password_hash']):
            failures = attempt['failures'] + 1 if attempt and attempt['last_at'] > cutoff else 1
            conn.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)', (payload.email, failures, now()))
            conn.commit()
            raise HTTPException(401, 'Email or password is incorrect')
        if user['status'] != 'active':
            raise HTTPException(403, 'Your account is awaiting HR approval or has been deactivated')
        conn.execute('DELETE FROM login_attempts WHERE email=?', (payload.email,))
        conn.execute('DELETE FROM sessions WHERE expires_at<=?', (now(),))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = (datetime.now(IST) + timedelta(hours=12)).isoformat(timespec='seconds')
        conn.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                     (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, expires))
        audit(conn, user['id'], 'login', user['id'])
    response.set_cookie('ems_session', token, httponly=True, secure=SECURE_COOKIE, samesite='lax', max_age=43200)
    return {'user': public_user(user), 'csrf': csrf}


@app.post('/api/logout')
def logout(request: Request, response: Response, user=Depends(current_user)):
    with db() as conn:
        conn.execute('DELETE FROM sessions WHERE token_hash=?',
                     (hashlib.sha256(request.cookies['ems_session'].encode()).hexdigest(),))
    response.delete_cookie('ems_session')
    return {'message': 'Signed out'}


@app.get('/api/me')
def me(user=Depends(current_user)):
    return user


@app.put('/api/me')
def update_profile(payload: Profile, user=Depends(current_user)):
    photo = payload.photo
    if photo:
        try:
            header, data = photo.split(',', 1)
            if header not in ('data:image/jpeg;base64', 'data:image/png;base64', 'data:image/webp;base64'):
                raise ValueError()
            raw = base64.b64decode(data, validate=True)
            if len(raw) > 2_000_000:
                raise ValueError()
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > 16_000_000:
                    raise ValueError()
                img = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (400, 400))
                output = io.BytesIO()
                img.save(output, 'JPEG', quality=85)
                photo = 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode()
        except Exception:
            raise HTTPException(422, 'Choose a JPG, PNG or WebP photo under 2 MB and 16 megapixels')
    with db() as conn:
        conn.execute('UPDATE users SET name=?,phone=?,photo=? WHERE id=?', (payload.name, payload.phone, photo, user['id']))
        audit(conn, user['id'], 'profile_updated', user['id'])
    return {'message': 'Profile saved'}


@app.get('/api/employees')
def employees(user=Depends(management)):
    with db() as conn:
        return [public_user(row) for row in conn.execute('SELECT * FROM users ORDER BY name')]


@app.put('/api/employees/{employee_id}')
def update_employee(employee_id: int, payload: EmployeeUpdate, user=Depends(management)):
    if payload.status not in ('pending', 'active', 'inactive') or payload.role not in ('employee', 'hr', 'admin'):
        raise HTTPException(422, 'Invalid status or role')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM users WHERE id=?', (employee_id,)).fetchone()
        if not old:
            raise HTTPException(404, 'Employee not found')
        if user['role'] != 'admin' and (old['role'] != 'employee' or payload.role != 'employee'):
            raise HTTPException(403, 'Only an administrator can manage HR and administrator roles')
        if old['role'] == 'admin' and old['status'] == 'active' and (payload.role != 'admin' or payload.status != 'active'):
            count = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND status='active'").fetchone()[0]
            if count <= 1:
                raise HTTPException(409, 'Keep at least one active administrator')
        conn.execute('UPDATE users SET status=?,role=?,department=?,designation=?,outlet=?,joining_date=? WHERE id=?',
                     (payload.status, payload.role, payload.department, payload.designation, payload.outlet,
                      payload.joining_date.isoformat() if payload.joining_date else None, employee_id))
        if payload.status != 'active' or payload.role != old['role']:
            conn.execute('DELETE FROM sessions WHERE user_id=?', (employee_id,))
        audit(conn, user['id'], 'employee_updated', employee_id, payload.model_dump_json())
    return {'message': 'Employee updated'}


@app.get('/api/attendance')
def attendance(user=Depends(current_user)):
    where, args = ('', ()) if user['role'] in ('hr', 'admin') else ('WHERE a.user_id=?', (user['id'],))
    with db() as conn:
        return [dict(row) for row in conn.execute(f'SELECT a.*,u.name FROM attendance a JOIN users u ON u.id=a.user_id {where} ORDER BY day DESC,a.id DESC LIMIT 500', args)]


@app.post('/api/attendance/{action}')
def punch(action: str, user=Depends(current_user)):
    if action not in ('check-in', 'check-out'):
        raise HTTPException(404, 'Unknown action')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM attendance WHERE user_id=? AND day=?', (user['id'], today())).fetchone()
        if action == 'check-in':
            if row:
                raise HTTPException(409, 'You have already checked in today')
            conn.execute('INSERT INTO attendance(user_id,day,check_in) VALUES(?,?,?)', (user['id'], today(), now()))
        else:
            if not row or row['check_out']:
                raise HTTPException(409, 'Check in first, or you have already checked out')
            conn.execute('UPDATE attendance SET check_out=? WHERE id=?', (now(), row['id']))
        audit(conn, user['id'], action, user['id'])
    return {'message': 'Attendance recorded'}


@app.get('/api/leave')
def leaves(user=Depends(current_user)):
    where, args = ('', ()) if user['role'] in ('hr', 'admin') else ('WHERE l.user_id=?', (user['id'],))
    with db() as conn:
        return [dict(row) for row in conn.execute(f'SELECT l.*,u.name FROM leave_requests l JOIN users u ON u.id=l.user_id {where} ORDER BY l.id DESC', args)]


@app.post('/api/leave', status_code=201)
def request_leave(payload: Leave, user=Depends(current_user)):
    if payload.end_date < payload.start_date or (payload.end_date-payload.start_date).days > 365:
        raise HTTPException(422, 'Choose a valid date range of up to one year')
    if payload.kind not in ('Casual', 'Sick', 'Earned', 'Unpaid'):
        raise HTTPException(422, 'Invalid leave type')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute("SELECT id FROM leave_requests WHERE user_id=? AND status!='rejected' AND start_date<=? AND end_date>=?",
                                (user['id'], str(payload.end_date), str(payload.start_date))).fetchone()
        if existing:
            raise HTTPException(409, 'These dates overlap an existing leave request')
        result = conn.execute('INSERT INTO leave_requests(user_id,start_date,end_date,kind,reason,created_at) VALUES(?,?,?,?,?,?)',
                              (user['id'], str(payload.start_date), str(payload.end_date), payload.kind, payload.reason, now()))
        audit(conn, user['id'], 'leave_requested', result.lastrowid)
    return {'message': 'Leave request sent to HR'}


@app.put('/api/leave/{leave_id}')
def decide_leave(leave_id: int, payload: Decision, user=Depends(management)):
    if payload.status not in ('approved', 'rejected'):
        raise HTTPException(422, 'Choose approved or rejected')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM leave_requests WHERE id=?', (leave_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Request not found')
        if row['user_id'] == user['id']:
            raise HTTPException(403, 'Another HR user or administrator must review your leave')
        if row['status'] != 'pending':
            raise HTTPException(409, 'This request has already been reviewed')
        conn.execute('UPDATE leave_requests SET status=?,reviewer_id=? WHERE id=?', (payload.status, user['id'], leave_id))
        audit(conn, user['id'], 'leave_' + payload.status, leave_id)
    return {'message': 'Leave decision saved'}


@app.get('/api/earnings')
def earnings(user=Depends(current_user)):
    where, args = ('', ()) if user['role'] in ('hr', 'admin') else ('WHERE e.user_id=?', (user['id'],))
    with db() as conn:
        return [dict(row) for row in conn.execute(f'SELECT e.*,u.name FROM earnings e JOIN users u ON u.id=e.user_id {where} ORDER BY month DESC,e.id DESC', args)]


@app.post('/api/earnings', status_code=201)
def add_earning(payload: Earning, user=Depends(management)):
    if payload.kind not in ('incentive', 'bonus'):
        raise HTTPException(422, 'Choose incentive or bonus')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_employee(conn, payload.user_id)
        if conn.execute('SELECT id FROM payroll WHERE user_id=? AND month=?', (payload.user_id, payload.month)).fetchone():
            raise HTTPException(409, 'Payroll is already published for this month. Record adjustments in a later month.')
        result = conn.execute('INSERT INTO earnings(user_id,month,kind,amount,note,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                              (payload.user_id, payload.month, payload.kind, money(payload.amount), payload.note, user['id'], now()))
        audit(conn, user['id'], 'earning_approved', result.lastrowid, payload.model_dump_json())
    return {'message': 'Earning approved and recorded'}


@app.get('/api/payroll')
def payroll(user=Depends(current_user)):
    where, args = ('', ()) if user['role'] in ('hr', 'admin') else ('WHERE p.user_id=?', (user['id'],))
    with db() as conn:
        return [dict(row) for row in conn.execute(f'SELECT p.*,u.name FROM payroll p JOIN users u ON u.id=p.user_id {where} ORDER BY month DESC,p.id DESC', args)]


@app.post('/api/payroll', status_code=201)
def publish_payroll(payload: Payroll, user=Depends(management)):
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_employee(conn, payload.user_id)
        values = {row['kind']: row['total'] for row in conn.execute('SELECT kind,SUM(amount) total FROM earnings WHERE user_id=? AND month=? GROUP BY kind', (payload.user_id, payload.month))}
        incentive, bonus = values.get('incentive', 0), values.get('bonus', 0)
        basic, allowances, deductions = money(payload.basic), money(payload.allowances), money(payload.deductions)
        net = basic + allowances + incentive + bonus - deductions
        if net < 0:
            raise HTTPException(422, 'Deductions cannot exceed gross earnings')
        try:
            result = conn.execute('INSERT INTO payroll(user_id,month,basic,allowances,deductions,incentives,bonuses,net,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                  (payload.user_id, payload.month, basic, allowances, deductions, incentive, bonus, net, user['id'], now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Payroll is already published for this employee and month')
        audit(conn, user['id'], 'payroll_published', result.lastrowid, payload.model_dump_json())
    return {'message': 'Payslip published to the employee dashboard'}


@app.put('/api/payroll/{payroll_id}/paid')
def mark_paid(payroll_id: int, user=Depends(management)):
    with db() as conn:
        result = conn.execute("UPDATE payroll SET status='paid' WHERE id=? AND status='published'", (payroll_id,))
        if result.rowcount != 1:
            raise HTTPException(409, 'Payslip is missing or already marked paid')
        audit(conn, user['id'], 'payroll_marked_paid', payroll_id)
    return {'message': 'Payment marked as paid. This records an external payment; it does not transfer funds.'}


@app.get('/api/audit')
def audit_log(user=Depends(management)):
    with db() as conn:
        return [dict(row) for row in conn.execute('SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 300')]


app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.get('/')
def index():
    return FileResponse(ROOT / 'static' / 'index.html')


def create_admin():
    parser = argparse.ArgumentParser(description='Create the initial EMS administrator')
    parser.add_argument('command', choices=['create-admin'])
    parser.parse_args()
    name = input('Administrator name: ').strip()
    email = input('Email: ').strip()
    password = getpass.getpass('Password (at least 10 characters): ')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match')
    payload = Registration(name=name, email=email, password=password)
    with db() as conn:
        try:
            result = conn.execute("INSERT INTO users(name,email,password_hash,role,status,designation,created_at) VALUES(?,?,?,'admin','active','Administrator',?)",
                                  (payload.name, payload.email, password_hash(payload.password), now()))
            audit(conn, result.lastrowid, 'admin_created', result.lastrowid)
        except sqlite3.IntegrityError:
            raise SystemExit('This email already exists. No account was changed.')
    print('Administrator created. Start EMS and sign in.')


if __name__ == '__main__':
    create_admin()
