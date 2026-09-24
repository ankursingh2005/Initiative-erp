"""Outlet-scoped read access for the attendance manager dashboard."""
from fastapi import HTTPException
import auth
from attendance_categories import manager_employee_visible, CATEGORY_ACCOUNTS


def is_ac_project_manager(actor):
    return actor.role == "ServiceManager" and (actor.email or "").strip().lower() == "akhtarnoor3112@gmail.com"


def ac_project_employee_visible(user):
    email = (user.email or "").strip().lower()
    assigned = {address for addresses in CATEGORY_ACCOUNTS.values() for address in addresses}
    return email in CATEGORY_ACCOUNTS["ac_projects"] or (user.role in {"ACTechnicianA", "AC Helper"} and email not in assigned)


def dashboard_category(actor, requested=None):
    if is_ac_project_manager(actor):
        if requested not in (None, "", "ac_projects"):
            raise HTTPException(403, "Service manager attendance is limited to AC PROJECTS")
        return "ac_projects"
    return requested


def dashboard_outlet(actor, requested=None):
    if auth.has_admin_access(actor) or is_ac_project_manager(actor):
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
        (is_ac_project_manager(actor) and ac_project_employee_visible(user)) or
        (actor.role == 'CategoryManager' and actor.store_id is not None and actor.store_id == user.store_id and manager_employee_visible(user)))
