import unittest
from salary_distribution import calculate_distribution as calc


class DistributionCalculationTests(unittest.TestCase):
    def test_only_regular_employees_have_bonus_epf_and_esic(self):
        for category in ('Contract', None):
            for basic in (1600000, 3000000):
                row = calc(basic, 0, 0, 10000, 2, category)
                for key in ('bonus_payable', 'epf_employee', 'esic_employee'):
                    self.assertEqual(row[key], 0)
                self.assertEqual(row['total_deductions'], 10000)
                self.assertEqual(row['net_amount'], row['actual_gross_earning'] - 10000)
        regular = calc(1600000, 0, 0, 10000, 2, 'Regular')
        self.assertEqual(regular['bonus_payable'], 141610)
        self.assertEqual(regular['epf_employee'], 204000)
        self.assertEqual(regular['esic_employee'], 13812)

    def test_esic_is_zero_at_and_above_gross_21000(self):
        below = calc(1600000, 0, 399999)
        self.assertEqual(below['actual_gross_earning'], 2099999)
        self.assertEqual(below['esic_employee'], 15750)
        for allowances in (400000, 400001):
            row = calc(1600000, 0, allowances)
            self.assertEqual(row['esic_employee'], 0)
            self.assertEqual(row['total_deductions'], row['epf_employee'] + row['staff_advance'])

    def test_unused_weekoffs_are_paid_on_gross(self):
        base = calc(2000000, 0, 500000, 100000, 4)
        result = calc(2000000, 0, 500000, 100000, 2)
        self.assertEqual(result['weekoff_credit'], 2)
        self.assertEqual(result['weekoff_pay'], 175000)
        self.assertEqual(result['net_amount'], base['net_amount'])
        self.assertEqual(calc(2000000, 0, 0, 0, 5)['weekoff_pay'], 0)

    def test_above_threshold(self):
        r = calc(2000000, 0, 500000, 100000)
        self.assertEqual(r['total_earning'], 2625000)
        self.assertEqual(r['bonus_payable'], 0)
        self.assertEqual(r['epf_employee'], 255000)
        self.assertEqual(r['esic_employee'], 0)
        self.assertEqual(r['net_amount'], 2270000)

    def test_below_threshold(self):
        r = calc(1600000, 0, 0, 10000)
        self.assertEqual(r['bonus_payable'], 141610)
        self.assertEqual(r['actual_gross_earning'], 1841610)
        self.assertEqual(r['esic_employee'], 13812)
        self.assertEqual(r['net_amount'], 1613798)

    def test_threshold_is_strict(self):
        r = calc(1600000, 0, 400000)
        self.assertEqual(r['total_earning'], 2100000)
        self.assertEqual(r['bonus_payable'], 0)
        self.assertEqual(r['esic_employee'], 0)
        r = calc(1600000, 0, 399999)
        self.assertEqual(r['bonus_payable'], 0)
        self.assertEqual(r['esic_employee'], 15750)
        self.assertEqual(calc(1600000, 0, 258390)['bonus_payable'], 0)
        self.assertEqual(calc(1600000, 0, 258389)['bonus_payable'], 141610)

    def test_absence_and_rounding(self):
        r = calc(2000000, 15, 400000)
        self.assertEqual(r['working_days'], 15)
        self.assertEqual(r['actual_basic'], 1000000)
        self.assertEqual(r['actual_oa'], 200000)
        self.assertEqual(calc(2000000, 31)['working_days'], 0)
        self.assertEqual(calc(100, 15)['actual_vda'], 3)


if __name__ == '__main__':
    unittest.main()
