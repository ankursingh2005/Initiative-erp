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

CATEGORIES = {"HA": "Home Appliances", "HE": "Home Entertainment", "MH": "Mobile", "IT": "Computer",
              "DC": "Digital Camera", "ACC": "Accessories", "PAYOUT": "Payouts"}
ALIASES = {"MOB": "MH", "COM": "IT", "MOBILE": "MH", "COMPUTER": "IT", "COMPUTER/IT": "IT",
           "HOME APPLIANCE": "HA", "HOME APPLIANCES": "HA", "HOME ENTERTAINMENT": "HE",
           "ACCESSORIES": "ACC", "ACCESSORY": "ACC", "OTHER": "UNCATEGORIZED",
           "PAYOUTS": "PAYOUT", "PAY OUT": "PAYOUT", "PAY OUTS": "PAYOUT"}
SUMMARY = re.compile(r"^(?:grand\s*total|sub\s*total|total|opening\s*balance|closing\s*balance|balance\s*[bc]/f|page\s*total)(?:\s*[:\-].*)?$", re.I)
ACCESSORY = re.compile(r"\b(?:accessor(?:y|ies)|cable|charger|adapter|adaptor|earbuds?|earphones?|headphones?|mouse|keyboard|remote|tempered\s*glass|phone\s*case|mobile\s*cover|memory\s*card|pen\s*drive|usb\s*hub)\b", re.I)

def category_code(value):
    code = str(value or "").strip().upper()
    return ALIASES.get(code, code)


def outlet_from_voucher(value):
    """Expose a voucher series code, never guess a physical branch name."""
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]{1,11})/\d+/\d{2,4}-\d{2,4}", str(value or "").strip())
    return match.group(1).upper() if match else None

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
    if re.search(r"back\s*pack|\b(?:airpods|airdopes|antivirus|ssd|hdd|caddy)\b|smart\s*watch", text, re.I):
        return "ACC"
    if re.search(r"\bref\b|\bw/?m\b|\bmw\b|\baquaguard\b", text, re.I):
        return "HA"
    if re.search(r"\bsamsung\s+[AFMSZ]\d{1,3}\b", text, re.I) and re.search(r"\d+\s*\+\s*\d+", text):
        return "MH"
    if re.search(r"\bprojector\b", text, re.I):
        return "HE"
    if re.search(r"\b(?:dell|hp|lenovo|acer|asus)\b", text, re.I) and re.search(r"\bi[3579][-/]|\b(?:82|83)[A-Z0-9]{8}\b", text, re.I):
        return "IT"
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


def decision_stats(rows):
    """Full-population decision support, always using amounts before GST.

    Bill keys include outlet, date and voucher. Missing vouchers are not bills.
    Returns remain in net totals but do not masquerade as selling-price losses.
    """
    groups = defaultdict(list)
    bills = defaultdict(lambda: Decimal(0))
    positive_sales = Decimal(0)
    return_value = Decimal(0)
    loss_value = Decimal(0)
    missing_cost = missing_bill = 0
    missing_outlet = 0
    losses = []
    seen = Counter()
    for r in rows:
        sales = money(getattr(r, "sales_before_gst", r.sales_amt))
        cost = money(getattr(r, "cost_before_gst", r.cost_amt))
        profit = sales - cost
        store = r.store or "Unknown"
        groups[(store, r.division)].append((r, sales, cost))
        if not r.vch_no:
            missing_bill += 1
        else:
            bills[(store, r.sale_date, r.vch_no)] += sales
        missing_outlet += store == "Unknown"
        positive_sales += max(sales, Decimal(0))
        return_value += max(-sales, Decimal(0))
        missing_cost += sales > 0 and cost == 0
        seen[(store, r.sale_date, r.vch_no, r.item, sales, cost, r.qty)] += 1
        if sales > 0 and profit < 0:
            loss_value -= profit
            losses.append({"store": store, "category": r.division, "item": r.item,
                           "voucher": r.vch_no, "date": r.sale_date.isoformat(),
                           "sales": float(sales), "loss": float(-profit)})
    total_sales = sum((s for values in groups.values() for _, s, _ in values), Decimal(0))
    total_cost = sum((c for values in groups.values() for _, _, c in values), Decimal(0))
    matrix = []
    for (store, category), values in groups.items():
        sales = sum((s for _, s, _ in values), Decimal(0))
        cost = sum((c for _, _, c in values), Decimal(0))
        matrix.append({"store": store, "category": category, "category_name": CATEGORIES.get(category, category),
                       "sales": float(sales), "cost": float(cost), "profit": float(sales-cost),
                       "margin": round(float((sales-cost)/sales*100), 2) if sales > 0 else None,
                       "rows": len(values), "bills": len({(r.sale_date, r.vch_no) for r, _, _ in values if r.vch_no})})
    matrix.sort(key=lambda x: x["profit"], reverse=True)
    positive_bills = [value for value in bills.values() if value > 0]
    duplicate_candidates = sum(n-1 for n in seen.values() if n > 1)
    actions = []
    if missing_cost:
        actions.append({"priority": "high", "title": "Verify zero-cost sales", "detail": f"{missing_cost:,} positive-sales lines have zero cost. Confirm purchase cost and payout treatment before relying on their profit."})
    if losses:
        actions.append({"priority": "high", "title": "Review below-cost selling", "detail": f"{len(losses):,} positive-sales lines lost INR {loss_value:,.2f} before GST. Check the largest lines below for pricing, cost and scheme support. Returns are separate."})
    if duplicate_candidates:
        actions.append({"priority": "medium", "title": "Check repeated records", "detail": f"{duplicate_candidates:,} extra lines repeat outlet, date, bill, item, amounts and quantity. They remain included: repeated lines can be legitimate."})
    if missing_outlet:
        actions.append({"priority": "medium", "title": "Complete outlet information", "detail": f"{missing_outlet:,} lines have no outlet or recognizable voucher series. Supply an Outlet column for reliable branch comparisons."})
    if matrix and matrix[0]["profit"] > 0:
        leader = matrix[0]
        actions.append({"priority": "low", "title": "Protect the largest profit contribution", "detail": f"{leader['store']} / {leader['category_name']} contributes INR {leader['profit']:,.2f} before GST. Review availability and demand before allocating more stock."})
    return {"basis": "Before GST; product gross profit before operating expenses",
            "sales": float(total_sales), "cost": float(total_cost), "profit": float(total_sales-total_cost),
            "margin": round(float((total_sales-total_cost)/total_sales*100), 2) if total_sales > 0 else None,
            "markup": round(float((total_sales-total_cost)/total_cost*100), 2) if total_cost > 0 else None,
            "bill_count": len(bills), "positive_bill_count": len(positive_bills),
            "average_bill": float(money(sum(positive_bills)/len(positive_bills))) if positive_bills else None,
            "missing_bill_rows": missing_bill, "positive_sales": float(positive_sales),
            "returns": float(return_value), "selling_loss": float(loss_value),
            "duplicate_candidates": duplicate_candidates, "zero_cost_rows": missing_cost,
            "matrix": matrix, "loss_lines": sorted(losses, key=lambda x: x["loss"], reverse=True)[:25],
            "loss_line_count": len(losses), "actions": actions}
