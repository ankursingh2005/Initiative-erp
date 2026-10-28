"""EMS records use the ERP database and existing users."""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, ForeignKey, Text, UniqueConstraint
from database import Base


class EMSSalaryProfile(Base):
    __tablename__ = 'ems_salary_profiles'
    __table_args__ = (UniqueConstraint('user_id', 'effective_month', name='uq_ems_salary_effective'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    effective_month = Column(String(7), nullable=False)
    basic = Column(BigInteger, nullable=False)
    allowances = Column(BigInteger, nullable=False)
    deductions = Column(BigInteger, nullable=False)
    divisor = Column(String(10), nullable=False)
    paid_weekoff = Column(Integer, nullable=False)
    paid_leave = Column(Integer, nullable=False)
    weekoff_availed = Column(Integer, nullable=False, default=0, server_default="0")
    weekoff_credit = Column(Integer, nullable=False, default=0, server_default="0")
    weekoff_pay = Column(BigInteger, nullable=False, default=0, server_default="0")
    setup_incentive = Column(BigInteger, nullable=False, default=0, server_default="0")
    employment_category = Column(String(10), nullable=True)
    account_no = Column(String(40), nullable=True)
    ifsc_code = Column(String(11), nullable=True)
    created_by = Column(Integer, nullable=False)


class EMSPayrollSnapshot(Base):
    __tablename__ = 'ems_payroll_snapshots'
    id = Column(Integer, primary_key=True)
    payroll_id = Column(Integer, ForeignKey('ems_payroll.id'), nullable=False, unique=True)
    details = Column(Text, nullable=False)


class EMSLeaveRequest(Base):
    __tablename__ = 'ems_leave_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    kind = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    reviewer_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EMSEarning(Base):
    __tablename__ = 'ems_earnings'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    amount = Column(BigInteger, nullable=False)
    note = Column(String(300), nullable=False)
    status = Column(String(20), nullable=False, default='approved')
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EMSPayroll(Base):
    __tablename__ = 'ems_payroll'
    __table_args__ = (UniqueConstraint('user_id', 'month', name='uq_ems_payroll_user_month'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    basic = Column(BigInteger, nullable=False)
    allowances = Column(BigInteger, nullable=False)
    deductions = Column(BigInteger, nullable=False)
    incentives = Column(BigInteger, nullable=False)
    bonuses = Column(BigInteger, nullable=False)
    net = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default='published')
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EMSAudit(Base):
    __tablename__ = 'ems_audit'
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, nullable=False)
    name = Column(String(150), nullable=False)
    action = Column(String(60), nullable=False)
    target = Column(String(100), nullable=False)
    details = Column(Text, nullable=False, default='')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EMSExcludedEmployee(Base):
    __tablename__ = 'ems_excluded_employees'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class EMSManualAttendance(Base):
    __tablename__ = 'ems_manual_attendance'
    __table_args__ = (UniqueConstraint('user_id', 'day', name='uq_ems_manual_attendance_day'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    day = Column(Date, nullable=False)
    status = Column(String(12), nullable=False)
    note = Column(String(300), nullable=False, default='')
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class EMSDistributionInput(Base):
    __tablename__ = 'ems_distribution_inputs'
    __table_args__ = (UniqueConstraint('user_id', 'month', name='uq_ems_distribution_month'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    other_allowances = Column(BigInteger, nullable=False, default=0)
    staff_advance = Column(BigInteger, nullable=False, default=0)
    updated_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EMSWeekoffIncentive(Base):
    __tablename__ = 'ems_weekoff_incentives'
    __table_args__ = (UniqueConstraint('user_id', 'month', name='uq_ems_weekoff_incentive_month'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    incentive = Column(BigInteger, nullable=False, default=0)
    updated_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EMSAttendanceTotals(Base):
    __tablename__ = 'ems_attendance_totals'
    __table_args__ = (UniqueConstraint('user_id', 'month', name='uq_ems_attendance_totals'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    present = Column(Integer, nullable=False)
    absent = Column(Integer, nullable=False)
    weekoff = Column(Integer, nullable=False)
    leave = Column(Integer, nullable=False)
    updated_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
