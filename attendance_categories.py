"""Employee category filtering shared by attendance dashboards and exports."""
from fastapi import HTTPException
import models


def filter_employee_category(query, category):
    if not category:
        return query
    if category == 'ids_emp':
        return query.filter(~models.User.role.in_(['BrandPartner', 'ACTechnicianA', 'ACTechnicianB']))
    roles = {'brand_pro': 'BrandPartner', 'ac_retails': 'ACTechnicianA',
             'ac_projects': 'ACTechnicianB'}
    if category not in roles:
        raise HTTPException(400, 'Unknown employee category')
    return query.filter(models.User.role == roles[category])
