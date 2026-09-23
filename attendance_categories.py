"""Employee category filtering shared by attendance dashboards and exports."""
from fastapi import HTTPException
from sqlalchemy import func, or_
import models


# Explicit account assignments are independent of permission roles. Match the
# supplied account emails so another employee with the same name is unaffected.
CATEGORY_ACCOUNTS = {
    'ac_projects': ('akhtarnoor3112@gmail.com',),
    'ac_retails': ('cdsood@gmail.com', 'jagritiawasthi123@gmail.com'),
}


def filter_employee_category(query, category):
    if not category:
        return query
    email = func.lower(func.trim(func.coalesce(models.User.email, '')))
    assigned = email.in_([address for addresses in CATEGORY_ACCOUNTS.values() for address in addresses])
    if category == 'ids_emp':
        return query.filter(~models.User.role.in_(['BrandPartner', 'ACTechnicianA', 'ACTechnicianB']), ~assigned)
    roles = {'brand_pro': 'BrandPartner', 'ac_retails': 'ACTechnicianB',
             'ac_projects': 'ACTechnicianA'}
    if category not in roles:
        raise HTTPException(400, 'Unknown employee category')
    return query.filter(or_(
        email.in_(CATEGORY_ACCOUNTS.get(category, ())),
        (models.User.role == roles[category]) & ~assigned,
    ))


def manager_employee_visible(user):
    """Managers see IDS employees and brand promoters, excluding AC assignments."""
    excluded_emails = {email for emails in CATEGORY_ACCOUNTS.values() for email in emails}
    return user.role not in {'ACTechnicianA', 'ACTechnicianB'} and (user.email or '').strip().lower() not in excluded_emails


def filter_manager_employees(query, category=None):
    if category not in (None, '', 'ids_emp', 'brand_pro'):
        raise HTTPException(403, 'Manager attendance is limited to IDS EMP and BRAND PRO')
    email = func.lower(func.trim(func.coalesce(models.User.email, '')))
    excluded = [address for addresses in CATEGORY_ACCOUNTS.values() for address in addresses]
    return query.filter(~models.User.role.in_(['ACTechnicianA', 'ACTechnicianB']), ~email.in_(excluded))
