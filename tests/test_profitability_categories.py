"""Exercise the report classifier without importing main's database startup."""
import ast
from pathlib import Path
import re
from typing import Optional
import unittest


source = Path(__file__).resolve().parents[1] / 'main.py'
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
nodes = [node for node in tree.body
         if (isinstance(node, ast.FunctionDef) and node.name == 'dp_categorize')
         or (isinstance(node, ast.Assign) and any(
             isinstance(target, ast.Name) and target.id == 'DP_ACCESSORY_KEYWORDS'
             for target in node.targets))]
namespace = {'re': re, 'Optional': Optional}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
categorize = namespace['dp_categorize']


class ProfitabilityCategoryTests(unittest.TestCase):
    def test_requested_appliances(self):
        for name in [
            'Faber Air Fryer OTG FAO 25L Black',
            'Faber Hood Zeal BLDC IND HC SC FL BK 90',
            'Havells Geoslim Jumbo 3 Burner',
            'Voltas Water D. Minimagic Spring RV+ Blk',
            'Bajaj OFR Vienna 11F 260095',
        ]:
            with self.subTest(name=name):
                self.assertEqual(categorize(name), 'HA')
                self.assertEqual(categorize(name.lower()), 'HA')

    def test_similar_appliances_and_previous_models(self):
        for name in [
            'Faber Hood Everest 3D IN HCSCFLLG60',
            'Faber Hob Cooktop Superia HT904 BR AI N',
            'Bajaj OTG 60 RCSS', 'Morphy Richards OTG 28L Black',
            'Philips Air-Fryer 6L', 'Elica Hood 60 LED',
            'Sunflame 4 Burner Stove', 'Glen Cook-top 3 Burner',
            'Voltas Water D Minimagic Pearl', 'Blue Star Water Dispensor',
            'Havells OFR 13 Fin', 'Morphy Richards Oil-Filled Radiator 11F',
        ]:
            with self.subTest(name=name):
                self.assertEqual(categorize(name), 'HA')

    def test_accessories_and_other_categories_do_not_move_to_ha(self):
        expected = {
            'USB OTG Adapter': 'Accessories',
            'Samsung OTG Cable': 'Accessories',
            'Faber Air Fryer OTG Replacement Tray': 'Accessories',
            'Faber Hood Replacement Filter': 'Accessories',
            'Havells OFR Spare Knob': 'Accessories',
            'HP Keyboard': 'Accessories',
            'Canon Camera Lens Hood': 'Digital Camera',
            'Samsung OLED TV': 'HE',
            'Dell Laptop': 'Computer',
            'Samsung Galaxy 8+128': 'Mobile',
            'Payout Faber Hood': 'Accessories',
        }
        for name, category in expected.items():
            with self.subTest(name=name):
                self.assertEqual(categorize(name), category)


if __name__ == '__main__':
    unittest.main()
