"""Role-based employee categories shared by dashboards and exports."""
from fastapi import HTTPException
import models

PROJECT_ROLES = ('Service Manager A', 'AC Technician A', 'AC Helper A')
RETAIL_ROLES = ('Service Manager B', 'AC Technician B', 'AC Helper B', 'ServiceCoordinator')
AC_ROLES = PROJECT_ROLES + RETAIL_ROLES


def employee_category(user):
    if user.role in PROJECT_ROLES:
        return 'ac_projects'
    if user.role in RETAIL_ROLES:
        return 'ac_retails'
    return 'brand_pro' if user.role == 'BrandPartner' else 'ids_emp'


def filter_employee_category(query, category):
    if not category:
        return query
    if category == 'ids_emp':
        return query.filter(~models.User.role.in_(AC_ROLES + ('BrandPartner',)))
    roles = {'brand_pro': ('BrandPartner',), 'ac_projects': PROJECT_ROLES, 'ac_retails': RETAIL_ROLES}
    if category not in roles:
        raise HTTPException(400, 'Unknown employee category')
    return query.filter(models.User.role.in_(roles[category]))


def manager_employee_visible(user):
    return user.role not in AC_ROLES


def filter_manager_employees(query, category=None):
    if category not in (None, '', 'ids_emp', 'brand_pro'):
        raise HTTPException(403, 'Manager attendance is limited to IDS EMP and BRAND PRO')
    return query.filter(~models.User.role.in_(AC_ROLES))
