"""Synthetic IDS formula cases; no real employee details."""
import unittest
from decimal import Decimal
from ems import regular_pay


class IDSCalculationTests(unittest.TestCase):
    def test_full_month(self):
        row = regular_pay(2000000, 500000, 100000, Decimal(1), {})
        self.assertEqual(row['actual_vda'], 125000)
        self.assertEqual(row['actual_pay_epf'], 2125000)
        self.assertEqual(row['epf_employee'], 255000)
        self.assertEqual(row['actual_gross_earning'], 2625000)
        self.assertEqual(row['deductions'], 355000)
        self.assertEqual(row['basic']+row['allowances']-row['deductions'], 2270000)

    def test_proration_bonus_and_esic(self):
        row = regular_pay(2000000, 500000, 0, Decimal('0.5'),
                          dict(bonus_enabled=True, esic_enabled=True))
        self.assertEqual(row['basic'], 1000000)
        self.assertEqual(row['actual_vda'], 62500)
        self.assertEqual(row['actual_oa'], 250000)
        self.assertEqual(row['bonus_payable'], 88500)
        self.assertEqual(row['actual_gross_earning'], 1401000)
        self.assertEqual(row['esic_employee'], 10500)

    def test_zero_days_and_disabled_contributions(self):
        row = regular_pay(2000000, 500000, 0, Decimal(0),
                          dict(bonus_enabled=True, esic_enabled=True))
        self.assertEqual(row['actual_gross_earning'], 0)
        self.assertEqual(row['deductions'], 0)
        row = regular_pay(2000000, 0, 0, Decimal(1), dict(epf_enabled=False))
        self.assertEqual(row['epf_employee'], 0)


if __name__ == '__main__':
    unittest.main()
