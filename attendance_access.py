"""Outlet-scoped read access for the attendance manager dashboard."""
from fastapi import HTTPException
import auth
from attendance_categories import manager_employee_visible, employee_category


ALL_ATTENDANCE_VIEW_ROLES = {'CEO', 'Director', 'AccountsManager'}


def can_view_all_attendance(actor):
    return auth.has_admin_access(actor) or actor.role in ALL_ATTENDANCE_VIEW_ROLES


def service_dashboard_category(actor):
    return {'Service Manager A': 'ac_projects', 'Service Manager B': 'ac_retails'}.get(actor.role)


def is_ac_project_manager(actor):
    return actor.role == 'Service Manager A'


def ac_project_employee_visible(user):
    return employee_category(user) == 'ac_projects'


def dashboard_category(actor, requested=None):
    category = service_dashboard_category(actor)
    if category:
        if requested not in (None, '', category):
            raise HTTPException(403, 'Service manager attendance is limited to their employee category')
        return category
    return requested


def dashboard_outlet(actor, requested=None):
    if can_view_all_attendance(actor) or service_dashboard_category(actor):
        return requested
    if actor.role != 'CategoryManager':
        raise HTTPException(403, 'Attendance dashboard access is not allowed')
    if actor.store_id is None:
        raise HTTPException(403, 'An outlet must be assigned before using the manager dashboard')
    if requested is not None and requested != actor.store_id:
        raise HTTPException(403, 'You can only view attendance for your assigned outlet')
    return actor.store_id


def can_view_attendance(actor, user):
    return user is not None and (actor.id == user.id or can_view_all_attendance(actor) or
        (service_dashboard_category(actor) is not None and employee_category(user) == service_dashboard_category(actor)) or
        (actor.role == 'CategoryManager' and actor.store_id is not None and actor.store_id == user.store_id and manager_employee_visible(user)))
