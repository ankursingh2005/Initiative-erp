"""Outlet-scoped read access for the attendance manager dashboard."""
from fastapi import HTTPException
import auth
from attendance_categories import manager_employee_visible


def dashboard_outlet(actor, requested=None):
    if auth.has_admin_access(actor):
        return requested
    if actor.role != 'CategoryManager':
        raise HTTPException(403, 'Attendance dashboard access is not allowed')
    if actor.store_id is None:
        raise HTTPException(403, 'An outlet must be assigned before using the manager dashboard')
    if requested is not None and requested != actor.store_id:
        raise HTTPException(403, 'You can only view attendance for your assigned outlet')
    return actor.store_id


def can_view_attendance(actor, user):
    return user is not None and (actor.id == user.id or auth.has_admin_access(actor) or
        (actor.role == 'CategoryManager' and actor.store_id is not None and actor.store_id == user.store_id and manager_employee_visible(user)))
