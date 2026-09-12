"""Deterministic analytics: keep stored amounts before GST, project at display time.

No database writes or optional scientific dependencies. Money is rounded per row
with Decimal; charts, item listings and exports all use the same projection.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
import math
import re
import statistics

CATEGORIES = {"HA": "HA", "HE": "HE", "MH": "Mobile", "IT": "Computer",
              "ACC": "Accessories", "PAYOUT": "Payouts"}
ALIASES = {"MOBILE": "MH", "COMPUTER": "IT", "COMPUTER/IT": "IT",
           "HOME APPLIANCE": "HA", "HOME APPLIANCES": "HA", "HOME ENTERTAINMENT": "HE",
           "ACCESSORIES": "ACC", "ACCESSORY": "ACC", "OTHER": "UNCATEGORIZED",
           "PAYOUTS": "PAYOUT", "PAY OUT": "PAYOUT", "PAY OUTS": "PAYOUT"}
SUMMARY = re.compile(r"^(?:grand\s*total|sub\s*total|total|opening\s*balance|closing\s*balance|balance\s*[bc]/f|page\s*total)(?:\s*[:\-].*)?$", re.I)
ACCESSORY = re.compile(r"\b(?:accessor(?:y|ies)|cable|charger|adapter|adaptor|earbuds?|earphones?|headphones?|mouse|keyboard|remote|tempered\s*glass|phone\s*case|mobile\s*cover|memory\s*card|pen\s*drive|usb\s*hub)\b", re.I)

def category_code(value):
    code = str(value or "").strip().upper()
    return ALIASES.get(code, code)

def classify(item, supplied=None, detector=None):
    text = str(item or "").strip()
    supplied = category_code(supplied)
    if supplied == "EXCLUDED":
        return "EXCLUDED"
    if not text or text.lower() in {"unknown item", "item", "description"} or SUMMARY.fullmatch(text):
        return "EXCLUDED"
    if supplied in CATEGORIES:
        return supplied
    if re.search(r"\bpay[\s-]*outs?\b", text, re.I):
        return "PAYOUT"
    if ACCESSORY.search(text):
        return "ACC"
    if re.search(r"\b(?:macbook|imac|monitor|notebook)\b", text, re.I):
        return "IT"
    if re.search(r"\b(?:mobile|smartphone|handset|oneplus|poco|tecno|infinix|itel|honor)\b", text, re.I):
        return "MH"
    code = detector(text) if detector else "UNCATEGORIZED"
    # A multi-category brand alone is insufficient evidence of a mobile sale.
    if code == "MH" and re.search(r"\b(?:samsung|apple)\b", text, re.I) and not re.search(r"\b(?:iphone|galaxy|mobile|smartphone|handset)\b", text, re.I):
        return "UNCATEGORIZED"
    return code if code in CATEGORIES else "UNCATEGORIZED"

def money(value):
    number = Decimal(str(value or 0))
    if not number.is_finite():
        raise ValueError("Amounts must be finite numbers")
    return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def normalize_upload(rows, amount_basis="exclusive"):
    if amount_basis not in {"exclusive", "inclusive"}:
        raise ValueError("Choose exclusive or inclusive source amounts")
    factor = Decimal("1.18") if amount_basis == "inclusive" else Decimal(1)
    for row in rows:
        for field in ("sales_amt", "cost_amt"):
            # Preserve precision until display rounding, including inclusive inputs.
            row[field] = float(Decimal(str(row.get(field) or 0)) / factor)
            if not math.isfinite(row[field]):
                raise ValueError("Amounts must be finite numbers")
        row["profit_loss"] = row["sales_amt"] - row["cost_amt"]
    return rows


def display_amounts(row, gst=False):
    factor = Decimal("1.18") if gst else Decimal(1)
    sales = money(Decimal(str(row.get("sales_amt") or 0)) * factor)
    cost = money(Decimal(str(row.get("cost_amt") or 0)) * factor)
    return {"sales_amt": float(sales), "cost_amt": float(cost), "profit_loss": float(sales-cost)}

def project(rows, detector=None, division=None, store=None, search=None, view="included", gst=True):
    if view not in {"included", "review", "excluded", "all"}:
        raise ValueError("Invalid data view")
    selected = []
    quality = Counter()
    requested = category_code(division)
    for row in rows:
        values = {key: getattr(row, key, None) for key in
                  ("id", "sale_date", "item", "division", "brand", "store", "vch_no", "qty", "sales_amt", "cost_amt", "profit_loss", "source_file", "source_sheet")}
        code = classify(values["item"], values["division"], detector)
        if category_code(values["division"]) == "UNCATEGORIZED" and code != "EXCLUDED":
            # A deliberate review assignment must not be undone by auto-detection.
            code = "UNCATEGORIZED"
        reason = "Unclassified item: assign a category in upload review" if code == "UNCATEGORIZED" else "Summary, blank description, or manually excluded row" if code == "EXCLUDED" else ""
        try:
            sale_base, cost_base = money(values["sales_amt"]), money(values["cost_amt"])
            # Multiplication uses raw normalized precision to avoid adding GST twice.
            factor = Decimal("1.18") if gst else Decimal(1)
            sale = money(Decimal(str(values["sales_amt"] or 0)) * factor)
            cost = money(Decimal(str(values["cost_amt"] or 0)) * factor)
            if not isinstance(values["sale_date"], date) or (values["qty"] is not None and not math.isfinite(values["qty"])):
                raise ValueError("Invalid date or quantity")
        except (ValueError, ArithmeticError):
            code, reason = "EXCLUDED", "Invalid date or non-finite numeric value"
            sale_base = cost_base = sale = cost = Decimal(0)
        status = "included" if code in CATEGORIES else "review" if code == "UNCATEGORIZED" else "excluded"
        if store and store != "ALL" and str(values["store"] or "Unknown").casefold() != store.casefold():
            continue
        if search and search.casefold() not in " ".join(str(values.get(k) or "") for k in ("item", "brand", "vch_no")).casefold():
            continue
        if requested and requested != "ALL" and code != requested:
            continue
        quality[status] += 1
        if view != "all" and status != view:
            continue
        values.update(division=code, store=values["store"] or "Unknown",
                      sales_amt=float(sale), cost_amt=float(cost), profit_loss=float(sale-cost),
                      sales_before_gst=float(sale_base), cost_before_gst=float(cost_base),
                      sales_gst=float(sale-sale_base), cost_gst=float(cost-cost_base),
                      status=status, exclusion_reason=reason)
        selected.append(SimpleNamespace(**values))
    return selected, dict(quality)

def advanced_stats(rows):
    by_day = defaultdict(lambda: {"sales": Decimal(0), "profit": Decimal(0)})
    for row in rows:
        by_day[row.sale_date]["sales"] += money(row.sales_amt)
        by_day[row.sale_date]["profit"] += money(row.profit_loss)
    daily = []
    for day, values in sorted(by_day.items()):
        # Missing dates count as zero. This is a trailing calendar-day average.
        rolling = sum((by_day.get(day-timedelta(days=i), {}).get("sales", Decimal(0)) for i in range(7)), Decimal(0))/7
        daily.append({"date": day.isoformat(), "sales": float(values["sales"]), "profit": float(values["profit"]), "rolling_7_sales": float(money(rolling))})
    sales = [r.sales_amt for r in rows]
    profits = [r.profit_loss for r in rows]
    store_stats = defaultdict(lambda: {"sales": 0.0, "profit": 0.0, "rows": 0})
    for row in rows:
        s = store_stats[row.store]
        s["sales"] += row.sales_amt
        s["profit"] += row.profit_loss
        s["rows"] += 1
    median = statistics.median(sales) if sales else 0
    mad = statistics.median([abs(s-median) for s in sales]) if sales else 0
    outliers = sum(abs(s-median) > 3*1.4826*mad for s in sales) if mad else 0
    return {"daily_trend": daily, "store_breakdown": [{"store": k, **{f: round(v, 2) for f,v in s.items()}} for k,s in sorted(store_stats.items())],
            "distribution": {"median_sale": round(median, 2), "sale_stddev": round(statistics.pstdev(sales), 2) if sales else 0,
                             "loss_rows": sum(p < 0 for p in profits), "outlier_rows": outliers, "outliers_evaluable": bool(mad)},
            "scatter": [{"x": r.sales_amt, "y": r.profit_loss, "item": r.item, "division": r.division} for r in rows[:1000]],
            "scatter_total": len(rows)}
