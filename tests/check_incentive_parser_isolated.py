"""Verify incentive parsing without importing the full app/database stack."""
import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

source = Path("main.py").read_text(encoding="utf-8")
tree = ast.parse(source)

needed_names = {
    "INCENTIVE_CATEGORIES",
    "INCENTIVE_OUTLETS",
    "IDS_FUND_SHARES",
    "INCENTIVE_APPLIED_RATE_HEADERS",
    "INCENTIVE_EXACT_AMOUNT_HEADERS",
    "SALES_INCENTIVE_RULES",
    "_incentive_header",
    "_incentive_outlet_short_name",
    "_incentive_category",
    "_incentive_number",
    "_incentive_rate",
    "_is_incentive_summary_row",
    "_is_incentive_outlet",
    "_prefer_incentive_detail_rows",
    "_parse_incentive_sheet",
    "_incentive_calc",
    "build_sales_incentive_summary",
    "ids_fund_amounts",
    "_ids_incentive_rate",
    "build_ids_fund_report",
    "build_non_sales_report",
    "calculate_incentive_report",
}

nodes = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in needed_names for target in node.targets):
        nodes.append(node)
    if isinstance(node, ast.FunctionDef) and node.name in needed_names:
        nodes.append(node)

namespace = {
    "re": re,
    "Optional": Optional,
    "defaultdict": defaultdict,
    "UploadFile": object,
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "main.py", "exec"), namespace)

sheet_rows = [
    ["Outlet", "Category", "Total Sales", "Apply %"],
    ["SUM ALL BRAN", "ALL", 42544283, 100],
    ["ALM"],
    ["ACC COM", "ACC", 100000, 85],
    ["COM", "COM", 200000, 0.5],
    ["COM", "COM", 100000, ""],
    ["MOB", "MOB", 300000, 100],
    ["ASH"],
    ["ACC COM", "ACC", 400000, 75],
    ["COM", "COM", 500000, 100],
    ["MOB", "MOB", 600000, 100],
]

rows = namespace["_prefer_incentive_detail_rows"](namespace["_parse_incentive_sheet"](sheet_rows, "JULY"))
assert not any(row["outlet"] == "ACC COM" for row in rows), rows
assert {"outlet": "ALM", "category": "ACC", "total_sales": 100000.0, "month": "", "applied_rate": 85.0} in rows
assert {"outlet": "ALM", "category": "COM", "total_sales": 200000.0, "month": "", "applied_rate": 50.0} in rows
assert {"outlet": "ASH", "category": "MOB", "total_sales": 600000.0, "month": "", "applied_rate": 100.0} in rows
assert not any(row["category"] == "ALL" for row in rows), rows

namespace["parse_incentive_upload"] = lambda file: rows
report = namespace["calculate_incentive_report"](None, 7, 2.5)
assert report["report_version"] == 7
assert report["summary"], report
assert all(row["exact_incentive"] is not None for row in report["exact_summary"]), report["exact_summary"]
alm_acc = next(row for row in report["exact_summary"] if row["outlet"] == "ALM" and row["group"] == "MOB + DC + ACC")
alm_com = next(row for row in report["exact_summary"] if row["outlet"] == "ALM" and row["group"] == "COM")
assert alm_acc["applied_rate"] == 13, alm_acc
assert alm_acc["exact_incentive"] == round(alm_acc["total_incentive"] * .13, 2), alm_acc
assert alm_com["applied_rate"] == 78, alm_com

nested_rows = namespace["_prefer_incentive_detail_rows"](namespace["_parse_incentive_sheet"]([
    ["Outlets", "Category", "Sale"],
    ["Alambagh", "", ""],
    ["", "MOB", 8791295],
    ["", "COM", 2574447],
    ["", "HA", 6915810],
    ["", "HE", 1841169],
    ["", "ACC COM", 32712],
    ["", "ACC", 189752],
    ["", "TOTAL", 20345185],
    ["Ashiyana", "", ""],
    ["", "MOB", 1203127],
    ["", "ACC", 12407],
], "JULY"))
assert {"outlet": "ALM", "category": "ACC COM", "total_sales": 32712.0, "month": ""} in nested_rows, nested_rows
assert {"outlet": "ALM", "category": "ACC", "total_sales": 189752.0, "month": ""} in nested_rows, nested_rows
assert {"outlet": "ASH", "category": "MOB", "total_sales": 1203127.0, "month": ""} in nested_rows, nested_rows
assert not any(row["outlet"] in {"ACC COM", "MOB", "COM", "DC", "HA", "HE", "ACC"} for row in nested_rows), nested_rows

namespace["parse_incentive_upload"] = lambda file: nested_rows
nested_report = namespace["calculate_incentive_report"](None, 7, 2.5)
expected_groups = [
    ("ALM", "HA + HE", 85),
    ("ALM", "MOB + DC + ACC", 13),
    ("ALM", "COM", 78),
    ("ASH", "ALL", 100),
]
for outlet, group, rate in expected_groups:
    row = next(item for item in nested_report["exact_summary"] if item["outlet"] == outlet and item["group"] == group)
    assert row["applied_rate"] == rate, row
assert not any(row["group"] == "ACC COM" for row in nested_report["exact_summary"]), nested_report["exact_summary"]
bad_outlets = {"ACC COM", "MOB", "COM", "DC", "HA", "HE", "ACC"}
assert not any(row["outlet"] in bad_outlets for row in nested_report["summary"]), nested_report["summary"]
assert not any(row["outlet"] in bad_outlets for row in nested_report["grouped_summary"]), nested_report["grouped_summary"]
assert not any(row["outlet"] in bad_outlets for row in nested_report["ids_fund_report"]["summary"]), nested_report["ids_fund_report"]["summary"]

fallback = namespace["build_ids_fund_report"]([
    {"outlet": "ACC COM", "category": "ACC", "total_sales": 100000},
    {"outlet": "DC", "category": "ACC", "total_sales": 200000},
    {"outlet": "ALM", "category": "ACC", "total_sales": 300000},
])
assert fallback["pending_rows"] == 0, fallback
assert fallback["totals"]["ids_fund"] is not None, fallback
assert fallback["non_sales_report"]["totals"][1] is not None, fallback
assert [row["outlet"] for row in fallback["summary"]] == ["ALM"], fallback
print("Incentive grouped parser and exact incentive fallback passed.")
