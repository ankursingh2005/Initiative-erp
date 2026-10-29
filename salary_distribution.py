"""Salary Distribution arithmetic. Amounts are integer paise; no ERP writes."""
from decimal import Decimal, ROUND_HALF_UP


def calculate_distribution(expected_basic, absent, other_allowances=0, staff_advance=0, weekoff_availed=4, employment_category='Regular'):
    regular = employment_category == 'Regular'
    absent = min(30, max(0, int(absent)))
    working_days = 30 - absent
    def ratio(value, numerator, denominator):
        return int((Decimal(value) * Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
    actual_basic = ratio(expected_basic, working_days, 30)
    actual_vda = ratio(actual_basic, 625, 10000)
    actual_pay_epf = actual_basic + actual_vda
    actual_oa = ratio(other_allowances, working_days, 30)
    total_earning = actual_pay_epf + actual_oa
    proposed_bonus = ratio(actual_pay_epf, 833, 10000)
    # Gross includes bonus: award it only if gross including that bonus stays below 21,000.
    bonus_payable = proposed_bonus if regular and total_earning + proposed_bonus < 2100000 else 0
    actual_gross_earning = total_earning + bonus_payable
    weekoff_credit = max(0, 4 - weekoff_availed)
    weekoff_pay = ratio(actual_gross_earning, weekoff_credit, 30)
    epf_employee = ratio(actual_pay_epf, 12, 100) if regular else 0
    esic_employee = ratio(actual_gross_earning, 75, 10000) if regular and actual_gross_earning < 2100000 else 0
    total_deductions = epf_employee + esic_employee + staff_advance
    return dict(absent=absent, no_of_days=30, working_days=working_days,
        expected_basic=expected_basic, actual_basic=actual_basic, other_allowances=other_allowances,
        actual_vda=actual_vda, actual_pay_epf=actual_pay_epf, actual_oa=actual_oa,
        total_earning=total_earning, bonus_payable=bonus_payable,
        actual_gross_earning=actual_gross_earning, epf_employee=epf_employee,
        esic_employee=esic_employee, staff_advance=staff_advance,
        weekoff_availed=weekoff_availed, weekoff_credit=weekoff_credit, weekoff_pay=weekoff_pay,
        total_deductions=total_deductions, net_amount=actual_gross_earning-total_deductions)
