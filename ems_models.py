"""EMS records use the ERP database and existing users."""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, ForeignKey, Text, UniqueConstraint
from database import Base


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
