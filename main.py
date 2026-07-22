from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, func
from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from io import BytesIO
from collections import defaultdict
import csv
import json
import os
import re
import importlib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
import base64
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()  # reads a local .env file (if present) into os.environ before
                # anything below calls os.getenv() - e.g. SMTP_*, SECRET_KEY.

import models
import schemas
import scheme_engine
import auth
from database import engine, get_db, Base, SessionLocal

# Creates all tables in the database if they don't already exist
Base.metadata.create_all(bind=engine)


def ensure_column(table_name: str, column_name: str, column_def: str):
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))


def ensure_database_schema():
    ensure_column("stores", "code", "VARCHAR(20)")
    ensure_column("stores", "city", "VARCHAR(100)")
    ensure_column("stores", "status", "VARCHAR(20)")

    ensure_column("categories", "code", "VARCHAR(10)")
    ensure_column("sub_categories", "category_id", "INTEGER")
    ensure_column("sub_categories", "name", "VARCHAR(100)")
    ensure_column("brands", "subcategory_id", "INTEGER")
    ensure_column("products", "brand_id", "INTEGER")
    ensure_column("products", "name", "VARCHAR(150)")
    ensure_column("variants", "product_id", "INTEGER")
    ensure_column("variants", "name", "VARCHAR(150)")

    ensure_column("sales", "invoice_date", "DATE")
    ensure_column("sales", "subcategory_id", "INTEGER")
    ensure_column("sales", "product_id", "INTEGER")
    ensure_column("sales", "variant_id", "INTEGER")
    ensure_column("sales", "imei", "VARCHAR(100)")
    ensure_column("sales", "serial_no", "VARCHAR(100)")
    ensure_column("sales", "model_no", "VARCHAR(100)")
    ensure_column("sales", "customer_name", "VARCHAR(150)")
    ensure_column("sales", "gst", "FLOAT")
    ensure_column("sales", "sale_value_exact", "VARCHAR(40)")
    ensure_column("sales", "schemes", "VARCHAR(50)")
    ensure_column("sales", "schemes_other", "VARCHAR(255)")
    ensure_column("sales", "scheme_match", "VARCHAR(20)")
    ensure_column("sales", "scheme_match_other", "VARCHAR(255)")
    ensure_column("sales", "scheme_amount", "FLOAT")
    ensure_column("sales", "scheme_amount_exact", "VARCHAR(40)")
    ensure_column("sales", "claim_status", "VARCHAR(50)")
    ensure_column("sales", "claim_status_other", "VARCHAR(255)")
    ensure_column("sales", "claim_overall_status", "VARCHAR(50)")
    ensure_column("sales", "settled_date", "DATE")
    ensure_column("sales", "sales_executive", "VARCHAR(150)")
    ensure_column("sales", "upi_scheme_amount", "FLOAT")
    ensure_column("sales", "upi_scheme_amount_exact", "VARCHAR(40)")
    ensure_column("sales", "upi_claim_status", "VARCHAR(20)")
    ensure_column("sales", "backend_scheme_amount", "FLOAT")
    ensure_column("sales", "backend_scheme_amount_exact", "VARCHAR(40)")
    ensure_column("sales", "backend_claim_type", "VARCHAR(30)")
    ensure_column("sales", "backend_claim_status", "VARCHAR(20)")

    ensure_column("schemes", "brand_id", "INTEGER")
    ensure_column("schemes", "category_id", "INTEGER")
    ensure_column("schemes", "subcategory_id", "INTEGER")
    ensure_column("schemes", "product_id", "INTEGER")
    ensure_column("schemes", "variant_id", "INTEGER")
    ensure_column("schemes", "offer_type", "VARCHAR(50)")

    ensure_column("purchase_orders", "supplier_address", "VARCHAR(500)")
    ensure_column("purchase_orders", "supplier_gstin", "VARCHAR(30)")
    ensure_column("purchase_orders", "exported_to_busy", "BOOLEAN DEFAULT FALSE")
    ensure_column("purchase_orders", "exported_to_busy_at", "TIMESTAMP")
    ensure_column("purchase_orders", "approved_by_user_id", "INTEGER")
    ensure_column("purchase_orders", "approved_date", "TIMESTAMP")
    ensure_column("schemes", "offer_value", "FLOAT")
    ensure_column("schemes", "calculation_method", "VARCHAR(50)")
    ensure_column("schemes", "min_qty", "INTEGER")
    ensure_column("schemes", "max_qty", "INTEGER")
    ensure_column("schemes", "applicable_branch_id", "INTEGER")
    ensure_column("schemes", "applicable_customer", "VARCHAR(100)")
    ensure_column("schemes", "applicable_dealer", "VARCHAR(100)")
    ensure_column("schemes", "circular_number", "VARCHAR(50)")
    ensure_column("schemes", "remarks", "VARCHAR(255)")
    ensure_column("schemes", "reward_type_other", "VARCHAR(100)")

    ensure_column("users", "store_id", "INTEGER")
    ensure_column("users", "category_code", "VARCHAR(20)")
    ensure_column("users", "status", "VARCHAR(20)")
    ensure_column("users", "created_date", "TIMESTAMP")
    ensure_column("users", "reset_token", "VARCHAR(100)")
    ensure_column("users", "reset_token_expires", "TIMESTAMP")

    ensure_column("claim_headers", "claim_no", "VARCHAR(50)")
    ensure_column("claim_headers", "brand_id", "INTEGER")
    ensure_column("claim_headers", "invoice_no", "VARCHAR(50)")
    ensure_column("claim_headers", "branch_id", "INTEGER")
    ensure_column("claim_headers", "remarks", "VARCHAR(255)")
    ensure_column("claim_headers", "payment_amount", "FLOAT")
    ensure_column("claim_headers", "balance", "FLOAT")
    ensure_column("claim_headers", "created_date", "TIMESTAMP")


ensure_database_schema()


def ensure_default_branches():
    with SessionLocal() as db:
        if db.query(models.Store).count() == 0:
            default_branches = [
                {"name": "Alambagh", "code": "BR001", "city": "Lucknow", "status": "Active"},
                {"name": "Gomtinagar", "code": "BR002", "city": "Lucknow", "status": "Active"},
                {"name": "Ashiyana", "code": "BR003", "city": "Lucknow", "status": "Active"},
                {"name": "Hazratganj", "code": "BR004", "city": "Lucknow", "status": "Active"},
                {"name": "Vikas Nagar", "code": "BR005", "city": "Lucknow", "status": "Active"},
            ]
            for branch in default_branches:
                db.add(models.Store(**branch))
            db.commit()


def ensure_default_master_data():
    with SessionLocal() as db:
        default_categories = [
            {"code": "HA", "name": "Home Appliances"},
            {"code": "HE", "name": "Home Entertainment"},
            {"code": "MH", "name": "Mobiles / Handset"},
            {"code": "IT", "name": "Information Technology"},
            {"code": "ASC", "name": "Accessories"},
            {"code": "OTH", "name": "Others"},
        ]
        allowed_codes = {item["code"] for item in default_categories}
        desired_names = {item["code"]: item["name"] for item in default_categories}

        existing_categories = db.query(models.Category).all()
        for category in existing_categories:
            category_code = (category.code or "").upper()
            if category_code in allowed_codes:
                if category.name != desired_names[category_code]:
                    category.name = desired_names[category_code]
            else:
                db.delete(category)

        for item in default_categories:
            existing = db.query(models.Category).filter(models.Category.code == item["code"]).first()
            if existing:
                existing.name = item["name"]
            else:
                db.add(models.Category(**item))

        db.commit()

        categories_by_code = {
            c.code: c
            for c in db.query(models.Category).filter(models.Category.code.in_(allowed_codes)).all()
        }

        category_subcategories = {
            "HA": [
                "Air Conditioner",
                "Air Purifier",
                "Cooler",
                "Dish Washer",
                "Geyser",
                "Fan",
                "Heat Convector",
                "Oil Filled Radiator (OFR)",
                "Refrigerator",
                "Vacuum Cleaner",
                "Washing Machine",
                "Water Heater",
                "Water Purifier",
                "Microwave Oven",
                "Kitchen Chimney",
                "Cooktop",
                "Induction Cooker",
                "Mixer Grinder",
                "Juicer",
                "Electric Kettle",
                "Rice Cooker",
                "Room Heater",
                "Deep Freezer",
            ],
            "HE": [
                "LED TV",
                "Projector",
                "Home Theatre",
                "Soundbar",
                "Speaker",
            ],
            "IT": [
                "Laptop",
                "Desktop",
            ],
            "ASC": [
                "Mobile Charger",
                "USB Cable",
                "Power Bank",
                "Earbuds",
                "Earphones",
                "Headphones",
                "Neckband",
                "Bluetooth Speaker",
                "Laptop Bag",
                "Laptop Adapter",
                "HDMI Cable",
                "USB Drive",
                "Memory Card",
                "Mouse",
                "Keyboard",
                "Extension Board",
                "TV Wall Mount",
                "AC Stabilizer",
                "Remote",
                "Battery",
            ],
            "OTH": [
                "Digital Camera",
                "DSLR",
                "Mirrorless Camera",
                "Camera Lens",
                "Drone",
                "Gaming Console",
                "Fire TV Stick",
                "Google Chromecast",
                "Amazon Echo",
            ],
            "MH": [
                "Apple",
                "Samsung",
                "Vivo",
                "iQOO",
                "Realme",
                "Oppo",
                "Motorola",
                "Nothing",
                "Google Pixel",
            ],
        }

        for category_code, names in category_subcategories.items():
            category = categories_by_code.get(category_code)
            if not category:
                continue
            existing_subcategories = (
                db.query(models.SubCategory)
                .filter(models.SubCategory.category_id == category.id)
                .all()
            )
            expected_names = set(names)
            existing_names = {sub.name for sub in existing_subcategories}

            for sub in existing_subcategories:
                if sub.name not in expected_names:
                    db.delete(sub)

            for name in names:
                if name not in existing_names:
                    db.add(models.SubCategory(category_id=category.id, name=name))

        db.commit()

        def get_or_create_brand(name: str, fallback_subcategory_id):
            """Brand names are unique in this database, so never insert a
            second row for a name that already exists — reuse the existing
            brand instead. Its subcategory_id (used elsewhere for schemes/
            products) is only set on first creation and never overwritten,
            so seeding one category never silently reassigns a brand that
            already belongs to a different one."""
            existing = db.query(models.Brand).filter(models.Brand.name.ilike(name)).first()
            if existing:
                return existing
            brand = models.Brand(name=name, subcategory_id=fallback_subcategory_id)
            db.add(brand)
            db.flush()
            return brand

        def make_brand_visible_in_category(brand: "models.Brand", category: "models.Category"):
            exists = (
                db.query(models.BrandCategoryVisibility)
                .filter(
                    models.BrandCategoryVisibility.brand_id == brand.id,
                    models.BrandCategoryVisibility.category_id == category.id,
                )
                .first()
            )
            if not exists:
                db.add(models.BrandCategoryVisibility(brand_id=brand.id, category_id=category.id))

        mh_category = categories_by_code.get("MH")
        if mh_category:
            mobile_brand_names = [
                "Apple",
                "Samsung",
                "Vivo",
                "iQOO",
                "Realme",
                "Oppo",
                "Motorola",
                "Nothing",
                "Google Pixel",
                "Mi",
                "Redmi",
            ]
            mobile_subcategories = (
                db.query(models.SubCategory)
                .filter(models.SubCategory.category_id == mh_category.id)
                .all()
            )
            if mobile_subcategories:
                for index, brand_name in enumerate(mobile_brand_names):
                    target_subcategory = mobile_subcategories[index % len(mobile_subcategories)]
                    brand = get_or_create_brand(brand_name, target_subcategory.id)
                    make_brand_visible_in_category(brand, mh_category)
                db.commit()

        he_category = categories_by_code.get("HE")
        if he_category:
            led_tv_subcategory = (
                db.query(models.SubCategory)
                .filter(models.SubCategory.category_id == he_category.id, models.SubCategory.name == "LED TV")
                .first()
            )
            if led_tv_subcategory:
                led_tv_brands = ["Sony", "Samsung", "LG", "Haier", "TCL", "Hisense", "Mi"]
                for brand_name in led_tv_brands:
                    brand = get_or_create_brand(brand_name, led_tv_subcategory.id)
                    make_brand_visible_in_category(brand, he_category)
                db.commit()

        it_category = categories_by_code.get("IT")
        if it_category:
            laptop_subcategory = (
                db.query(models.SubCategory)
                .filter(models.SubCategory.category_id == it_category.id, models.SubCategory.name == "Laptop")
                .first()
            )
            if laptop_subcategory:
                laptop_brands = ["HP", "Dell", "Lenovo"]
                for brand_name in laptop_brands:
                    brand = get_or_create_brand(brand_name, laptop_subcategory.id)
                    make_brand_visible_in_category(brand, it_category)
                db.commit()


ensure_default_branches()
ensure_default_master_data()

app = FastAPI(title="IDSPL Scheme Management ERP")


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    """Any error we didn't explicitly raise as an HTTPException still comes
    back as JSON (with a real message) instead of a raw text/HTML 500 page.
    A non-JSON error body is what makes the frontend show a generic
    'Request failed' / 'Failed to fetch' with no useful detail."""
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


# Serves the login.html / signup.html / dashboard.html pages from the
# "static" folder sitting next to this file.
app.mount("/static", StaticFiles(directory="static"), name="static")

VALID_ROLES = ["Admin", "CategoryManager", "BrandManager", "BrandPartner", "Accounts", "MISExecutive"]


def normalize_category_code(raw_value: Optional[str]) -> Optional[str]:
    value = (raw_value or "").strip().upper()
    if not value:
      return None
    mapping = {
        "HA": "HA",
        "HE": "HE",
        "IT": "IT",
        "MOBILE": "MH",
        "MH": "MH",
        "OTHER": "OTH",
        "OTH": "OTH",
    }
    if value in mapping:
        return mapping[value]
    raise HTTPException(status_code=400, detail="category_code must be one of: HA, HE, IT, MOBILE, OTHER")


def normalize_reward_type(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    if value in {"fixed", "fixed amount", "amount"}:
        return "Fixed"
    if value in {"%", "percentage", "percent"}:
        return "Percentage"
    if value in {"target based", "target", "slab"}:
        return "Slab"
    if value in {"other"}:
        # Custom scheme types still need a concrete calculation behind them
        # for auto claim generation; treat "Other" as a flat/fixed amount.
        # The user's own label is kept separately in reward_type_other.
        return "Fixed"
    raise HTTPException(status_code=400, detail="reward_type must be one of: Fixed Amount, Target Based, %, Slab, Other")


def normalize_offer_type(raw_value: str) -> str:
    value = (raw_value or "").strip().upper()
    mapping = {
        "BACKEND": "Backend",
        "BACKEND SUPPORT": "Backend",
        "UPI": "UPI",
        "UPI OFFER": "UPI",
        "CARD": "CARD",
        "CARD OFFER": "CARD",
        "FESTIVAL OFFER": "FESTIVAL",
        "MONTHLY OFFER": "MONTHLY",
        "OTHER": "OTH",
        "OTH": "OTH",
    }
    if value in mapping:
        return mapping[value]
    raise HTTPException(status_code=400, detail="offer_type must be one of: Backend Support, UPI Offer, Card Offer, Festival Offer, Monthly Offer, Other")


def normalize_header_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


HEADER_ALIASES = {
    "sale_date": {"date", "invoicedate", "saledate", "billdate"},
    "vch_no": {"vchno", "voucher", "voucherno", "invoiceno", "billno"},
    "account": {"account", "customer", "accountname", "party"},
    "item": {"item", "product", "itemname", "description"},
    "qty": {"qty", "quantity"},
    "unit": {"unit", "uom"},
    "sales_amt": {"salesamt", "salesamount", "salevalue", "amount", "invoicevalue"},
    "cost_amt": {"costamt", "costamount", "cost"},
    "profit_loss": {"profitloss", "grossprofit"},
    "profit_percent": {"profit", "profitpercent", "profitpercentage", "marginpercent", "gppercent"},
}


def canonical_column(normalized_header: str) -> Optional[str]:
    if normalized_header == "profit":
        return "profit_percent"
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized_header in aliases:
            return canonical
    return None


def find_header_row_index(table_rows: List[List]) -> int:
    """Find the row that most likely contains expected sales headers."""
    scan_limit = min(len(table_rows), 15)
    best_index = 0
    best_score = -1

    for row_index in range(scan_limit):
        row = table_rows[row_index] or []
        normalized = [normalize_header_name(cell) for cell in row]
        canonicals = {canonical_column(name) for name in normalized if canonical_column(name)}
        canonicals.discard(None)

        # Weighted score: prefer rows that include core columns.
        score = len(canonicals)
        if "sale_date" in canonicals:
            score += 2
        if "sales_amt" in canonicals:
            score += 2
        if "qty" in canonicals:
            score += 1

        if score > best_score:
            best_score = score
            best_index = row_index

    return best_index


def parse_date_value(raw_value) -> date:
    if isinstance(raw_value, datetime):
        return raw_value.date()

    if isinstance(raw_value, date):
        return raw_value

    # Excel serial date numbers (common in xlsx uploads)
    if isinstance(raw_value, (int, float)):
        try:
            excel_datetime_utils = importlib.import_module("openpyxl.utils.datetime")
            excel_date = excel_datetime_utils.from_excel(raw_value)
            if isinstance(excel_date, datetime):
                return excel_date.date()
            if isinstance(excel_date, date):
                return excel_date
        except Exception:
            pass

    text_value = str(raw_value or "").strip()
    if not text_value:
        raise ValueError("Date is empty")

    for date_fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text_value, date_fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text_value).date()
    except ValueError as exc:
        raise ValueError(f"Unsupported date value: {text_value}") from exc


def parse_float_value(raw_value, fallback: float = 0.0) -> float:
    text_value = str(raw_value or "").strip()
    if not text_value:
        return fallback

    is_negative_bracket = text_value.startswith("(") and text_value.endswith(")")
    cleaned = text_value.strip("()")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    cleaned = cleaned.replace(",", "").replace("%", "").strip()
    if cleaned in {"-", "--"}:
        return fallback

    value = float(cleaned)
    if is_negative_bracket:
        value *= -1
    return value


def parse_tabular_rows(file_ext: str, content: bytes) -> List[dict]:
    parsed_rows: List[dict] = []

    if file_ext in {".xlsx", ".xls"}:
        try:
            openpyxl_module = importlib.import_module("openpyxl")
            load_workbook = openpyxl_module.load_workbook
        except ImportError as exc:
            raise HTTPException(status_code=400, detail="Excel upload requires openpyxl package. Install: pip install openpyxl") from exc

        workbook = load_workbook(filename=BytesIO(content), data_only=True, read_only=True)
        worksheet = workbook.active
        raw_rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
        if not raw_rows:
            return []

        header_index = find_header_row_index(raw_rows)
        headers = [normalize_header_name(cell) for cell in raw_rows[header_index]]

        for row in raw_rows[header_index + 1:]:
            row_dict = {}
            for idx, header in enumerate(headers):
                canonical = canonical_column(header)
                if canonical:
                    row_dict[canonical] = row[idx] if idx < len(row) else None
            if any(str(value or "").strip() for value in row_dict.values()):
                parsed_rows.append(row_dict)
        return parsed_rows

    if file_ext == ".csv":
        decoded = content.decode("utf-8-sig", errors="replace")
        raw_lines = [line for line in decoded.splitlines() if line.strip()]
        if not raw_lines:
            return []

        preview_rows = [next(csv.reader([line])) for line in raw_lines[:15]]
        header_index = find_header_row_index(preview_rows)

        data_lines = raw_lines[header_index:]
        reader = csv.DictReader(data_lines)
        for input_row in reader:
            row_dict = {}
            for key, value in input_row.items():
                canonical = canonical_column(normalize_header_name(key))
                if canonical:
                    row_dict[canonical] = value
            if any(str(value or "").strip() for value in row_dict.values()):
                parsed_rows.append(row_dict)
        return parsed_rows

    if file_ext == ".pdf":
        try:
            pypdf_module = importlib.import_module("pypdf")
            PdfReader = pypdf_module.PdfReader
        except ImportError as exc:
            raise HTTPException(status_code=400, detail="PDF upload requires pypdf package. Install: pip install pypdf") from exc

        reader = PdfReader(BytesIO(content))
        text_data = "\n".join((page.extract_text() or "") for page in reader.pages)
        lines = [line.strip() for line in text_data.splitlines() if line.strip()]
        if not lines:
            return []

        header_line = None
        for line in lines:
            normalized = normalize_header_name(line)
            if "date" in normalized and "vch" in normalized and ("salesamt" in normalized or "salesamount" in normalized):
                header_line = line
                break

        if not header_line:
            return []

        header_parts = [part.strip() for part in re.split(r"\t+|\s{2,}|,", header_line) if part.strip()]
        normalized_headers = [normalize_header_name(part) for part in header_parts]

        header_index = lines.index(header_line)
        for line in lines[header_index + 1:]:
            parts = [part.strip() for part in re.split(r"\t+|\s{2,}|,", line) if part.strip()]
            if len(parts) < 4:
                continue
            row_dict = {}
            for idx, header in enumerate(normalized_headers):
                canonical = canonical_column(header)
                if canonical and idx < len(parts):
                    row_dict[canonical] = parts[idx]
            if any(str(value or "").strip() for value in row_dict.values()):
                parsed_rows.append(row_dict)
        return parsed_rows

    if file_ext in {".jpg", ".jpeg", ".png"}:
        try:
            pil_module = importlib.import_module("PIL.Image")
            Image = pil_module
            pytesseract = importlib.import_module("pytesseract")
        except ImportError as exc:
            raise HTTPException(status_code=400, detail="Image upload requires pillow + pytesseract. Install: pip install pillow pytesseract") from exc

        image = Image.open(BytesIO(content))
        ocr_text = pytesseract.image_to_string(image)
        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        if not lines:
            return []

        header_line = lines[0]
        header_parts = [part.strip() for part in re.split(r"\t+|\s{2,}|,", header_line) if part.strip()]
        normalized_headers = [normalize_header_name(part) for part in header_parts]

        for line in lines[1:]:
            parts = [part.strip() for part in re.split(r"\t+|\s{2,}|,", line) if part.strip()]
            if len(parts) < 4:
                continue
            row_dict = {}
            for idx, header in enumerate(normalized_headers):
                canonical = canonical_column(header)
                if canonical and idx < len(parts):
                    row_dict[canonical] = parts[idx]
            if any(str(value or "").strip() for value in row_dict.values()):
                parsed_rows.append(row_dict)
        return parsed_rows

    raise HTTPException(status_code=400, detail="Unsupported file format. Upload Excel, CSV, PDF, JPG, JPEG, or PNG")


def build_interval_analytics(rows: List[models.IntervalSaleUpload], interval: str) -> dict:
    grouped = defaultdict(lambda: {"qty": 0.0, "sales_amt": 0.0, "cost_amt": 0.0, "profit_loss": 0.0})

    for row in rows:
        if interval == "weekly":
            iso_year, iso_week, _ = row.sale_date.isocalendar()
            group_key = f"{iso_year}-W{iso_week:02d}"
        elif interval == "monthly":
            group_key = row.sale_date.strftime("%Y-%m")
        else:
            group_key = row.sale_date.isoformat()

        bucket = grouped[group_key]
        bucket["qty"] += float(row.qty or 0)
        bucket["sales_amt"] += float(row.sales_amt or 0)
        bucket["cost_amt"] += float(row.cost_amt or 0)
        bucket["profit_loss"] += float(row.profit_loss or 0)

    points = []
    for key in sorted(grouped.keys()):
        data = grouped[key]
        sales_amt = data["sales_amt"]
        profit_percent = (data["profit_loss"] / sales_amt * 100.0) if sales_amt else 0.0
        points.append({
            "label": key,
            "qty": round(data["qty"], 2),
            "sales_amt": round(sales_amt, 2),
            "cost_amt": round(data["cost_amt"], 2),
            "profit_loss": round(data["profit_loss"], 2),
            "profit_percent": round(profit_percent, 2),
        })

    total_qty = sum(point["qty"] for point in points)
    total_sales = sum(point["sales_amt"] for point in points)
    total_cost = sum(point["cost_amt"] for point in points)
    total_profit = sum(point["profit_loss"] for point in points)
    total_profit_percent = (total_profit / total_sales * 100.0) if total_sales else 0.0

    top_items = defaultdict(lambda: {"qty": 0.0, "sales_amt": 0.0, "profit_loss": 0.0})
    for row in rows:
        item_name = (row.item or "Unknown").strip() or "Unknown"
        top_items[item_name]["qty"] += float(row.qty or 0)
        top_items[item_name]["sales_amt"] += float(row.sales_amt or 0)
        top_items[item_name]["profit_loss"] += float(row.profit_loss or 0)

    top_item_rows = sorted(
        [
            {
                "item": item,
                "qty": round(values["qty"], 2),
                "sales_amt": round(values["sales_amt"], 2),
                "profit_loss": round(values["profit_loss"], 2),
            }
            for item, values in top_items.items()
        ],
        key=lambda entry: entry["sales_amt"],
        reverse=True,
    )[:8]

    return {
        "interval": interval,
        "totals": {
            "records": len(rows),
            "qty": round(total_qty, 2),
            "sales_amt": round(total_sales, 2),
            "cost_amt": round(total_cost, 2),
            "profit_loss": round(total_profit, 2),
            "profit_percent": round(total_profit_percent, 2),
        },
        "series": points,
        "top_items": top_item_rows,
    }


# ============================================================
# SCHEME DOCUMENT -> LLM EXTRACTION
# A promoter/brand manager attaches a scheme circular (image, PDF, or
# Excel). Claude reads it and returns structured scheme fields, which are
# used to pre-fill a Draft scheme for Admin to review. Extraction never
# raises - if it fails or ANTHROPIC_API_KEY isn't set, the scheme is just
# left as a bare Draft for Admin to fill in by hand.
# ============================================================

SCHEME_EXTRACTION_MODEL = "claude-sonnet-5"


def _document_to_llm_content_block(filename: str, content_type: str, raw_bytes: bytes) -> Optional[dict]:
    """Turn an uploaded scheme document into a Claude API content block.
    Images and PDFs are sent as-is (base64) so Claude can read tables,
    stamps, and handwriting directly. Excel/CSV files are flattened to a
    plain-text cell dump first, since the Messages API has no spreadsheet
    input type."""
    ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
    b64 = base64.b64encode(raw_bytes).decode("ascii")

    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        media_type = content_type or ("image/png" if ext == ".png" else "image/jpeg")
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}

    if ext == ".pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}

    if ext in {".xlsx", ".xls", ".csv"}:
        try:
            if ext == ".csv":
                text_dump = raw_bytes.decode("utf-8-sig", errors="replace")
            else:
                openpyxl_module = importlib.import_module("openpyxl")
                workbook = openpyxl_module.load_workbook(filename=BytesIO(raw_bytes), data_only=True, read_only=True)
                lines = []
                for sheet in workbook.worksheets:
                    lines.append(f"--- Sheet: {sheet.title} ---")
                    for row in sheet.iter_rows(values_only=True):
                        cells = [str(cell) for cell in row if cell is not None]
                        if cells:
                            lines.append(" | ".join(cells))
                text_dump = "\n".join(lines)
        except Exception:
            return None
        return {"type": "text", "text": text_dump[:20000]}

    return None


def extract_scheme_from_document(db: Session, filename: str, content_type: str, raw_bytes: bytes) -> dict:
    """Calls the Claude API to read a scheme circular and return structured
    fields. Returns {"status": "Extracted"/"Failed"/"Skipped", "data": {...}, "error": str|None}."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "Skipped", "data": {}, "error": "ANTHROPIC_API_KEY is not configured on the server."}

    content_block = _document_to_llm_content_block(filename, content_type, raw_bytes)
    if not content_block:
        return {"status": "Failed", "data": {}, "error": "Unsupported file type for extraction."}

    brands = [{"id": b.id, "name": b.name} for b in db.query(models.Brand).all()]
    categories = [{"id": c.id, "code": c.code, "name": c.name} for c in db.query(models.Category).all()]

    instructions = (
        "You are reading a dealer/brand scheme circular (an incentive or backend "
        "scheme notice) for an electronics retail ERP. Extract the scheme terms "
        "and reply with ONLY a JSON object - no prose, no markdown fences. Schema:\n"
        "{\n"
        '  "scheme_name": string,\n'
        '  "brand_name": string or null (the brand this scheme is for),\n'
        '  "product_name": string or null (specific product/model if the scheme is product-specific),\n'
        '  "category_hint": string or null (e.g. HA, HE, IT, Mobile - only if clearly stated),\n'
        '  "start_date": "YYYY-MM-DD" or null,\n'
        '  "end_date": "YYYY-MM-DD" or null,\n'
        '  "reward_type": one of "Fixed", "Percentage", "Slab",\n'
        '  "reward_value": number (flat amount for Fixed, percent for Percentage, 0 for Slab),\n'
        '  "slabs": [{"min_quantity": number, "reward_per_unit": number}] (only for Slab, else []),\n'
        '  "min_qty": number or 0,\n'
        '  "max_qty": number or null,\n'
        '  "offer_type": one of "Backend", "UPI", "CARD", "FESTIVAL", "MONTHLY", "OTH",\n'
        '  "circular_number": string or null,\n'
        '  "remarks": string or null (any other important terms/conditions in the document)\n'
        "}\n\n"
        "If the document mentions only a month/quarter (e.g. \"August 2026 scheme\") without "
        "exact dates, set start_date to the first day and end_date to the last day of that "
        "period. If a field truly isn't in the document, use null (or 0/[] as shown above). "
        f"Known brands in this system: {json.dumps(brands)}. Known categories: {json.dumps(categories)}."
    )

    payload = json.dumps({
        "model": SCHEME_EXTRACTION_MODEL,
        "max_tokens": 1500,
        "messages": [
            {"role": "user", "content": [content_block, {"type": "text", "text": instructions}]}
        ],
    }).encode("utf-8")

    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"status": "Failed", "data": {}, "error": f"Claude API request failed: {exc}"}
    except Exception as exc:
        return {"status": "Failed", "data": {}, "error": f"Unexpected error calling Claude API: {exc}"}

    try:
        text_blocks = [block["text"] for block in response_data.get("content", []) if block.get("type") == "text"]
        raw_text = "\n".join(text_blocks).strip()
        raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
        extracted = json.loads(raw_text)
    except Exception as exc:
        return {"status": "Failed", "data": {}, "error": f"Could not parse Claude's response as JSON: {exc}"}

    return {"status": "Extracted", "data": extracted, "error": None}


def _calculate_reward_for_interval_row(scheme: models.Scheme, row: models.IntervalSaleUpload) -> float:
    """Same reward math as scheme_engine._calculate_reward, adapted for an
    IntervalSaleUpload row (Busy profitability report import) instead of a
    Sale row entered manually."""
    if scheme.reward_type == "Fixed":
        return float(scheme.reward_value)
    if scheme.reward_type == "Percentage":
        return round((row.sales_amt or 0) * (scheme.reward_value / 100), 2)
    if scheme.reward_type == "Slab":
        applicable_slabs = [s for s in scheme.slabs if (row.qty or 0) >= s.min_quantity]
        if not applicable_slabs:
            return 0
        best_slab = max(applicable_slabs, key=lambda s: s.min_quantity)
        return round(best_slab.reward_per_unit * (row.qty or 0), 2)
    return 0


def serve_html(path: str):
    return FileResponse(path)


@app.get("/")
@app.get("/login")
@app.get("/login.html")
def home():
    return serve_html("static/login.html")


@app.get("/signup")
@app.get("/signup.html")
def signup_page():
    return serve_html("static/signup.html")


@app.get("/forgot-password")
@app.get("/forgot-password.html")
def forgot_password_page():
    return serve_html("static/forgot_password.html")


@app.get("/reset-password")
@app.get("/reset-password.html")
def reset_password_page():
    return serve_html("static/reset_password.html")


@app.get("/dashboard")
@app.get("/dashboard.html")
def dashboard_page():
    return serve_html("static/dashboard.html")


@app.get("/home")
@app.get("/home.html")
def app_home_page():
    return serve_html("static/home.html")


@app.get("/purchase-orders")
@app.get("/purchase-orders.html")
def purchase_orders_page():
    return serve_html("static/purchase_orders.html")


@app.get("/manifest.webmanifest")
def manifest_file():
    return FileResponse("static/manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker_file():
    return FileResponse("static/sw.js", media_type="application/javascript")


# ============================================================
# AUTH: SIGNUP / LOGIN / CURRENT USER
# ============================================================

@app.post("/auth/signup", response_model=schemas.UserOut)
def signup(user: schemas.UserSignup, db: Session = Depends(get_db)):
    # --------------------------------------------------------------
    # Invite-code gate: the signup page is public (anyone can reach it
    # once this app is on the Play/App Store), so each role -- and each
    # Category Manager's category, and each Brand Manager/Partner's
    # brand -- requires its own separate code. This means a code that
    # leaks only exposes that one role/category/brand, not the whole
    # system, and you can rotate a single one without affecting others.
    #
    # Override any of these in your environment (Render dashboard ->
    # Environment, or a local .env file) without changing code:
    #   SIGNUP_CODE_ADMIN, SIGNUP_CODE_ACCOUNTS, SIGNUP_CODE_MIS,
    #   SIGNUP_CODE_CAT_HA, SIGNUP_CODE_CAT_HE, SIGNUP_CODE_CAT_IT,
    #   SIGNUP_CODE_CAT_MOBILE, SIGNUP_CODE_UNIVERSAL
    # Brand codes are not env vars -- they're always "INITIATIVE@<BRAND NAME>"
    # (uppercased, spaces removed), generated automatically per brand.
    # --------------------------------------------------------------
    ROLE_INVITE_CODES = {
        "Admin": os.getenv("SIGNUP_CODE_ADMIN", "Initiative@#%_-Admin"),
        "Accounts": os.getenv("SIGNUP_CODE_ACCOUNTS", "Initiative/AC"),
        "MISExecutive": os.getenv("SIGNUP_CODE_MIS", "Initiative%MS"),
    }
    CATEGORY_INVITE_CODES = {
        "HA": os.getenv("SIGNUP_CODE_CAT_HA", "Initiative@HA"),
        "HE": os.getenv("SIGNUP_CODE_CAT_HE", "Initiative#HE"),
        "IT": os.getenv("SIGNUP_CODE_CAT_IT", "Initiative-IT"),
        "MH": os.getenv("SIGNUP_CODE_CAT_MOBILE", "Initiative_MO"),
    }
    UNIVERSAL_INVITE_CODE = os.getenv("SIGNUP_CODE_UNIVERSAL", "Initiative@Universal")

    def brand_invite_code(brand_name: str) -> str:
        normalized = re.sub(r"\s+", "", brand_name or "").upper()
        return f"INITIATIVE@{normalized}"

    submitted_code = (user.invite_code or "").strip()

    if user.role in ROLE_INVITE_CODES:
        expected = ROLE_INVITE_CODES[user.role]
        if submitted_code != expected:
            raise HTTPException(status_code=403, detail="Invalid invite code for this role")

    elif user.role == "CategoryManager":
        category_code = normalize_category_code(user.category_code)
        expected = CATEGORY_INVITE_CODES.get(category_code)
        if expected is None:
            # No code configured for this category yet -- fall back to
            # the universal code rather than locking everyone out.
            expected = UNIVERSAL_INVITE_CODE
        if submitted_code != expected:
            raise HTTPException(status_code=403, detail="Invalid invite code for this category")

    elif user.role in ("BrandManager", "BrandPartner"):
        if not user.brand_ids:
            raise HTTPException(status_code=400, detail="Select at least one brand")
        brands = db.query(models.Brand).filter(models.Brand.id.in_(user.brand_ids)).all()
        matched = any(
            submitted_code.strip().upper() == brand_invite_code(b.name)
            for b in brands
        )
        if not matched:
            raise HTTPException(
                status_code=403,
                detail="Invalid invite code for the selected brand(s). "
                       "Code format: INITIATIVE@<BRAND NAME IN CAPITALS>",
            )

    else:
        if submitted_code != UNIVERSAL_INVITE_CODE:
            raise HTTPException(status_code=403, detail="Invalid invite code")

    existing = (
        db.query(models.User)
        .filter((models.User.username == user.username) | (models.User.email == user.email))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    if user.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {VALID_ROLES}")

    category_roles = {"CategoryManager"}
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=auth.hash_password(user.password),
        full_name=user.full_name,
        role=user.role,
        store_id=user.store_id if user.role == "StoreManager" else None,
        category_code=normalize_category_code(user.category_code) if user.role in category_roles else None,
        status="Active",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    if user.role in ("BrandManager", "BrandPartner", "CategoryManager"):
        for brand_id in user.brand_ids:
            db.add(models.UserBrand(user_id=db_user.id, brand_id=brand_id))
        db.commit()

    return db_user


@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    identifier = (form_data.username or "").strip()
    user = (
        db.query(models.User)
        .filter((models.User.username == identifier) | (models.User.email == identifier))
        .first()
    )
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password")
    if user.status != "Active":
        raise HTTPException(status_code=403, detail="This account is not active")

    token = auth.create_access_token({"user_id": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


def send_password_reset_email(user: models.User, token: str) -> str:
    """Reuses the same SMTP env vars as send_purchase_order_email
    (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM). Host, user,
    port, and from-address all default to the company Gmail mailbox
    (initiative.lucknow@gmail.com) so the only thing that has to be set as
    a secret on Render is SMTP_PASSWORD (a Gmail App Password)."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_user = os.getenv("SMTP_USER", "initiative.lucknow@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "initiative.lucknow@gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    app_base_url = os.getenv("APP_BASE_URL", "").rstrip("/")

    if not (smtp_host and smtp_user and smtp_password):
        return "Not sent: SMTP is not configured (set SMTP_PASSWORD on the host)."

    reset_link = f"{app_base_url}/reset-password?token={token}" if app_base_url else f"(reset code: {token})"
    body = (
        f"Hello {user.username},\n\n"
        f"Use this link to reset your Initiative ERP password:\n{reset_link}\n\n"
        f"This link expires in 30 minutes. If you didn't request this, you can ignore this email."
    )
    message = MIMEText(body)
    message["Subject"] = "Initiative ERP - Password Reset"
    message["From"] = smtp_from
    message["To"] = user.email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [user.email], message.as_string())
    except Exception as exc:  # noqa: BLE001
        return f"Not sent: email delivery failed ({exc})."

    return "Reset email sent."


@app.post("/auth/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Step 1: look up the account and, if found, email a one-time reset
    link. Always returns the same generic message either way, so this
    endpoint can't be used to check whether a username/email exists."""
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    generic_message = {
        "message": "If an account matches those details, a password reset email has been sent."
    }
    if not username and not email:
        raise HTTPException(status_code=400, detail="Enter username or email to reset the password")

    query = db.query(models.User)
    if username and email:
        user = query.filter((models.User.username == username) | (models.User.email == email)).first()
    elif username:
        user = query.filter(models.User.username == username).first()
    else:
        user = query.filter(models.User.email == email).first()

    if user:
        token = uuid4().hex
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=30)
        db.commit()
        result = send_password_reset_email(user, token)
        print(f"[forgot-password] {user.username}: {result}")

    return generic_message


@app.post("/auth/reset-password")
def reset_password(payload: schemas.ResetPasswordConfirm, db: Session = Depends(get_db)):
    """Step 2: person submits the token from their email plus a new
    password. Only succeeds if the token matches and hasn't expired."""
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")

    user = db.query(models.User).filter(models.User.reset_token == payload.token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired. Request a new one.")

    user.password_hash = auth.hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password updated successfully"}


@app.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ============================================================
# ROLE-SCOPED DATA (each role only sees what it's allowed to)
# ============================================================

def get_sales_for_user(db: Session, current_user: models.User):
    if current_user.role in ("Admin", "Accounts", "MISExecutive"):
        return db.query(models.Sale).all()
    if current_user.role == "StoreManager":
        return db.query(models.Sale).filter(models.Sale.store_id == current_user.store_id).all()
    if current_user.role == "CategoryManager":
        if not current_user.category_code:
            return []
        return (
            db.query(models.Sale)
            .join(models.Category, models.Sale.category_id == models.Category.id)
            .filter(models.Category.code == current_user.category_code)
            .all()
        )
    if current_user.role in ("BrandManager", "BrandPartner"):
        brand_ids = [ub.brand_id for ub in current_user.brands]
        return db.query(models.Sale).filter(models.Sale.brand_id.in_(brand_ids)).all()
    return []


def get_claims_for_user(db: Session, current_user: models.User):
    if current_user.role in ("Admin", "Accounts", "MISExecutive"):
        return db.query(models.ClaimHeader).all()

    if current_user.role in ("BrandManager", "BrandPartner"):
        brand_ids = [ub.brand_id for ub in current_user.brands]
        return (
            db.query(models.ClaimHeader)
            .join(models.Sale, models.ClaimHeader.sale_id == models.Sale.id)
            .filter(models.Sale.brand_id.in_(brand_ids))
            .all()
        )

    if current_user.role == "StoreManager":
        return (
            db.query(models.ClaimHeader)
            .join(models.Sale, models.ClaimHeader.sale_id == models.Sale.id)
            .filter(models.Sale.store_id == current_user.store_id)
            .all()
        )

    if current_user.role == "CategoryManager":
        if not current_user.category_code:
            return []
        return (
            db.query(models.ClaimHeader)
            .join(models.Sale, models.ClaimHeader.sale_id == models.Sale.id)
            .join(models.Category, models.Sale.category_id == models.Category.id)
            .filter(models.Category.code == current_user.category_code)
            .all()
        )

    return []


def can_user_access_sale(db: Session, current_user: models.User, sale: models.Sale) -> bool:
    if current_user.role in ("Admin", "Accounts", "MISExecutive"):
        return True

    if current_user.role == "StoreManager":
        return current_user.store_id is not None and sale.store_id == current_user.store_id

    if current_user.role == "CategoryManager":
        if not current_user.category_code:
            return False
        sale_category = db.query(models.Category).filter(models.Category.id == sale.category_id).first()
        return bool(sale_category and sale_category.code == current_user.category_code)

    if current_user.role in ("BrandManager", "BrandPartner"):
        brand_ids = [ub.brand_id for ub in current_user.brands]
        return sale.brand_id in brand_ids

    return False

@app.get("/my-scope/sales", response_model=List[schemas.SaleOut])
def my_scope_sales(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return get_sales_for_user(db, current_user)


@app.get("/my-scope/claims", response_model=List[schemas.ClaimOut])
def my_scope_claims(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return get_claims_for_user(db, current_user)


# ============================================================
# MASTERS (Branch / Category / Subcategory / Brand / Product / Variant)
# ============================================================

@app.post("/categories", response_model=schemas.CategoryOut)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    db_category = models.Category(code=category.code, name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@app.get("/categories", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    allowed_codes = ["HA", "HE", "MH", "IT", "ASC", "OTH"]
    categories = db.query(models.Category).filter(models.Category.code.in_(allowed_codes)).all()

    order_map = {"HA": 0, "HE": 1, "MH": 2, "IT": 3, "ASC": 4, "OTH": 5}

    def sort_key(item):
        code = (item.code or "").upper()
        return (order_map.get(code, 999), (item.name or "").lower())

    return sorted(categories, key=sort_key)


@app.post("/subcategories", response_model=schemas.SubCategoryOut)
def create_subcategory(subcategory: schemas.SubCategoryCreate, db: Session = Depends(get_db)):
    db_subcategory = models.SubCategory(category_id=subcategory.category_id, name=subcategory.name)
    db.add(db_subcategory)
    db.commit()
    db.refresh(db_subcategory)
    return db_subcategory


@app.get("/subcategories", response_model=List[schemas.SubCategoryOut])
def list_subcategories(category_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.SubCategory)
    if category_id is not None:
        query = query.filter(models.SubCategory.category_id == category_id)
    return query.order_by(models.SubCategory.name).all()


@app.post("/brands", response_model=schemas.BrandOut)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db)):
    db_brand = models.Brand(name=brand.name, subcategory_id=brand.subcategory_id)
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand


@app.get("/brands", response_model=List[schemas.BrandOut])
def list_brands(
    subcategory_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Brand)
    if subcategory_id is not None:
        query = query.filter(models.Brand.subcategory_id == subcategory_id)
    elif category_id is not None:
        primary_ids = {
            row[0]
            for row in db.query(models.Brand.id)
            .join(models.SubCategory, models.Brand.subcategory_id == models.SubCategory.id)
            .filter(models.SubCategory.category_id == category_id)
            .all()
        }
        visible_ids = {
            row[0]
            for row in db.query(models.BrandCategoryVisibility.brand_id)
            .filter(models.BrandCategoryVisibility.category_id == category_id)
            .all()
        }
        all_ids = primary_ids | visible_ids
        if not all_ids:
            return []
        query = query.filter(models.Brand.id.in_(all_ids))
    return query.order_by(models.Brand.name).all()


@app.get("/api/brand-category-visibility", response_model=List[schemas.BrandCategoryVisibilityOut])
def list_brand_category_visibility(db: Session = Depends(get_db)):
    """All (brand, category) pairs — a brand can legitimately appear under
    more than one division (e.g. Samsung under both Mobiles and Home
    Entertainment) even though its `subcategory_id` only points to one."""
    return db.query(models.BrandCategoryVisibility).all()


@app.post("/products", response_model=schemas.ProductOut)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = models.Product(brand_id=product.brand_id, name=product.name)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.get("/products", response_model=List[schemas.ProductOut])
def list_products(brand_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if brand_id is not None:
        query = query.filter(models.Product.brand_id == brand_id)
    return query.order_by(models.Product.name).all()


@app.post("/variants", response_model=schemas.VariantOut)
def create_variant(variant: schemas.VariantCreate, db: Session = Depends(get_db)):
    db_variant = models.Variant(product_id=variant.product_id, name=variant.name)
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)
    return db_variant


@app.get("/variants", response_model=List[schemas.VariantOut])
def list_variants(product_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Variant)
    if product_id is not None:
        query = query.filter(models.Variant.product_id == product_id)
    return query.order_by(models.Variant.name).all()


@app.post("/customers", response_model=schemas.CustomerOut)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    db_customer = models.Customer(name=customer.name, phone=customer.phone, city=customer.city)
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


@app.get("/customers", response_model=List[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(models.Customer).order_by(models.Customer.name).all()


@app.post("/dealers", response_model=schemas.DealerOut)
def create_dealer(dealer: schemas.DealerCreate, db: Session = Depends(get_db)):
    db_dealer = models.Dealer(name=dealer.name, city=dealer.city, contact=dealer.contact)
    db.add(db_dealer)
    db.commit()
    db.refresh(db_dealer)
    return db_dealer


@app.get("/dealers", response_model=List[schemas.DealerOut])
def list_dealers(db: Session = Depends(get_db)):
    return db.query(models.Dealer).order_by(models.Dealer.name).all()


@app.post("/stores", response_model=schemas.StoreOut)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db)):
    db_store = models.Store(
        name=store.name,
        code=store.code,
        city=store.city,
        status=store.status or "Active",
    )
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store


@app.get("/stores", response_model=List[schemas.StoreOut])
def list_stores(db: Session = Depends(get_db)):
    return db.query(models.Store).order_by(models.Store.code, models.Store.name).all()


# ============================================================
# CURRENT USER PROFILE & ADMIN ASSIGNMENTS
# (Used to scope a Category Manager's Division and Brand choices to only
#  what's assigned to their account.)
# ============================================================

def serialize_user_with_brands(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "store_id": user.store_id,
        "category_code": user.category_code,
        "brand_ids": [ub.brand_id for ub in user.brands],
        "status": user.status,
    }


@app.get("/api/me", response_model=schemas.MyProfileOut)
def get_my_profile(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "store_id": current_user.store_id,
        "category_code": current_user.category_code,
        "brand_ids": [ub.brand_id for ub in current_user.brands],
    }


@app.get("/api/users", response_model=List[schemas.UserAdminOut])
def list_users_for_admin(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    users = db.query(models.User).order_by(models.User.username).all()
    return [serialize_user_with_brands(u) for u in users]


@app.patch("/api/users/{user_id}/assignments", response_model=schemas.UserAdminOut)
def update_user_assignments(
    user_id: int,
    payload: schemas.UserAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    """Assign which store, category (division), and brands a user — typically
    a CategoryManager — can see on the Purchase Orders page."""
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.store_id is not None:
        target_user.store_id = payload.store_id
    if payload.category_code is not None:
        target_user.category_code = normalize_category_code(payload.category_code)
    if payload.brand_ids is not None:
        db.query(models.UserBrand).filter(models.UserBrand.user_id == target_user.id).delete()
        for brand_id in payload.brand_ids:
            db.add(models.UserBrand(user_id=target_user.id, brand_id=brand_id))

    db.commit()
    db.refresh(target_user)
    return serialize_user_with_brands(target_user)


# ============================================================
# PURCHASE ORDERS
# ============================================================

PURCHASE_ORDER_STATUSES = {"Requested", "Approved", "Rejected", "Ordered", "Cancelled"}

# Which roles are allowed to move a PO into which status. A Category
# Manager's request starts as "Requested". Only Admin can Approve or Reject
# it. Only once it's "Approved" can Admin/MIS move it on to "Ordered" (i.e.
# finalized and sent to the supplier) or "Cancelled".
ADMIN_ONLY_STATUSES = {"Approved", "Rejected", "Requested"}


def assert_status_transition_allowed(current_user: models.User, purchase_order: models.PurchaseOrder, new_status: str):
    if new_status in ADMIN_ONLY_STATUSES and current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can approve, reject, or reopen a purchase order.",
        )
    if new_status == "Ordered" and purchase_order.status != "Approved":
        raise HTTPException(
            status_code=400,
            detail="This purchase order must be Approved by Admin before it can be marked Ordered.",
        )


def serialize_purchase_order(purchase_order: models.PurchaseOrder, notification_status: Optional[str] = None):
    return {
        "id": purchase_order.id,
        "request_no": purchase_order.request_no,
        "request_date": purchase_order.request_date,
        "division": purchase_order.division,
        "branch_id": purchase_order.branch_id,
        "brand_name": purchase_order.brand_name,
        "supplier_name": purchase_order.supplier_name,
        "supplier_email": purchase_order.supplier_email,
        "supplier_address": purchase_order.supplier_address,
        "supplier_gstin": purchase_order.supplier_gstin,
        "delivery_address": purchase_order.delivery_address,
        "remarks": purchase_order.remarks,
        "status": purchase_order.status,
        "busy_po_number": purchase_order.busy_po_number,
        "ordered_date": purchase_order.ordered_date,
        "processing_notes": purchase_order.processing_notes,
        "exported_to_busy": purchase_order.exported_to_busy,
        "exported_to_busy_at": purchase_order.exported_to_busy_at,
        "submitted_by_user_id": purchase_order.submitted_by_user_id,
        "submitted_by_username": purchase_order.submitted_by.username if purchase_order.submitted_by else None,
        "approved_by_username": (getattr(purchase_order, "approved_by", None).username if getattr(purchase_order, "approved_by", None) else None),
        "approved_date": getattr(purchase_order, "approved_date", None),
        "created_date": purchase_order.created_date,
        "updated_date": purchase_order.updated_date,
        "items": purchase_order.items,
        "notification_status": notification_status,
    }


def send_purchase_order_whatsapp_notification(purchase_order: models.PurchaseOrder) -> str:
    """Send a short MIS alert through WhatsApp Cloud API when configured."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    recipients = [value.strip() for value in os.getenv("WHATSAPP_MIS_RECIPIENTS", "").split(",") if value.strip()]
    if not (access_token and phone_number_id and recipients):
        return "Not sent: WhatsApp notification is not configured."

    requester = purchase_order.submitted_by.username if purchase_order.submitted_by else "Unknown user"
    message = (
        f"New PO request {purchase_order.request_no} from {requester}. "
        f"Branch: {purchase_order.branch_id or 'Not selected'} | "
        f"Items: {len(purchase_order.items)} | Status: {purchase_order.status}."
    )
    api_version = os.getenv("WHATSAPP_API_VERSION", "v23.0")
    endpoint = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    failures = 0

    for recipient in recipients:
        payload = json.dumps({
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": message},
        }).encode("utf-8")
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10):
                pass
        except (HTTPError, URLError, TimeoutError):
            failures += 1

    if failures:
        return f"Saved, but WhatsApp delivery failed for {failures} recipient(s)."
    return f"WhatsApp notification sent to {len(recipients)} MIS recipient(s)."


def can_access_purchase_order(current_user: models.User, purchase_order: models.PurchaseOrder) -> bool:
    return current_user.role in {"Admin", "MISExecutive"} or purchase_order.submitted_by_user_id == current_user.id


# ============================================================
# BRAND SUPPLIER EMAIL BOOK
# ============================================================

DEFAULT_BRAND_SUPPLIER_EMAILS = {
    "Samsung": ["orders@samsung.com", "sales@samsung.com", "purchase@samsung.com", "support@samsung.com", "distributor@samsung.com"],
    "LG": ["orders@lg.com", "sales@lg.com", "purchase@lg.com", "support@lg.com", "distributor@lg.com"],
    "Haier": ["orders@haier.com", "sales@haier.com", "purchase@haier.com", "support@haier.com", "distributor@haier.com"],
    "Vivo": ["orders@vivo.com", "sales@vivo.com", "purchase@vivo.com", "support@vivo.com", "distributor@vivo.com"],
    "Oppo": ["orders@oppo.com", "sales@oppo.com", "purchase@oppo.com", "support@oppo.com", "distributor@oppo.com"],
    "Redmi": ["orders@mi.com", "sales@mi.com", "purchase@mi.com", "support@mi.com", "distributor@mi.com"],
}


def seed_default_brand_supplier_emails(db: Session):
    existing_count = db.query(models.BrandSupplierEmail).count()
    if existing_count:
        return
    for brand_name, emails in DEFAULT_BRAND_SUPPLIER_EMAILS.items():
        for email in emails:
            db.add(models.BrandSupplierEmail(brand_name=brand_name, email=email))
    db.commit()


with SessionLocal() as _db:
    seed_default_brand_supplier_emails(_db)


@app.get("/api/brand-emails", response_model=List[schemas.BrandSupplierEmailOut])
def list_brand_emails(
    brand: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.BrandSupplierEmail)
    if brand:
        query = query.filter(models.BrandSupplierEmail.brand_name == brand)
    return query.order_by(models.BrandSupplierEmail.brand_name, models.BrandSupplierEmail.id).all()


@app.post("/api/brand-emails", response_model=schemas.BrandSupplierEmailOut)
def add_brand_email(
    payload: schemas.BrandSupplierEmailCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    brand_name = payload.brand_name.strip()
    email = payload.email.strip().lower()
    if not brand_name or not email:
        raise HTTPException(status_code=400, detail="Brand and email are required")
    existing = (
        db.query(models.BrandSupplierEmail)
        .filter(models.BrandSupplierEmail.brand_name == brand_name, models.BrandSupplierEmail.email == email)
        .first()
    )
    if existing:
        return existing
    row = models.BrandSupplierEmail(brand_name=brand_name, email=email)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/brand-emails/{email_id}")
def delete_brand_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    row = db.query(models.BrandSupplierEmail).filter(models.BrandSupplierEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}


# ============================================================
# SUPPLIER PROFILE (per supplier name)
# Address, GSTIN, and every email entered for a supplier are remembered
# under that supplier's name, so the next purchase order for the same
# supplier (on any brand/division) can auto-fill instead of retyping.
# ============================================================

def upsert_supplier_profile(db: Session, supplier_name: Optional[str], supplier_address: Optional[str], supplier_gstin: Optional[str]):
    """Save/update the address and GSTIN on file for this supplier name.
    Only overwrites a field when a non-blank value was actually provided,
    so clearing one field on one PO doesn't blank it out for every other
    request that shares the same supplier."""
    name = (supplier_name or "").strip()
    if not name:
        return
    profile = (
        db.query(models.SupplierProfile)
        .filter(func.lower(models.SupplierProfile.supplier_name) == name.lower())
        .first()
    )
    if not profile:
        profile = models.SupplierProfile(supplier_name=name)
        db.add(profile)
    if supplier_address and supplier_address.strip():
        profile.supplier_address = supplier_address.strip()
    if supplier_gstin and supplier_gstin.strip():
        profile.supplier_gstin = supplier_gstin.strip()
    db.commit()


def upsert_supplier_email(db: Session, supplier_name: Optional[str], email: Optional[str]):
    """Remember this email under the supplier's name (no duplicates)."""
    name = (supplier_name or "").strip()
    email = (email or "").strip().lower()
    if not name or not email:
        return
    existing = (
        db.query(models.SupplierEmail)
        .filter(func.lower(models.SupplierEmail.supplier_name) == name.lower(), models.SupplierEmail.email == email)
        .first()
    )
    if existing:
        return
    db.add(models.SupplierEmail(supplier_name=name, email=email))
    db.commit()


@app.get("/api/supplier-profile", response_model=schemas.SupplierProfileOut)
def get_supplier_profile(
    supplier_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    name = supplier_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="supplier_name is required")

    profile = (
        db.query(models.SupplierProfile)
        .filter(func.lower(models.SupplierProfile.supplier_name) == name.lower())
        .first()
    )
    email_rows = (
        db.query(models.SupplierEmail)
        .filter(func.lower(models.SupplierEmail.supplier_name) == name.lower())
        .order_by(models.SupplierEmail.id)
        .all()
    )
    return {
        "supplier_name": profile.supplier_name if profile else name,
        "supplier_address": profile.supplier_address if profile else None,
        "supplier_gstin": profile.supplier_gstin if profile else None,
        "emails": email_rows,
    }


@app.post("/api/supplier-emails", response_model=schemas.SupplierEmailEntry)
def add_supplier_email(
    payload: schemas.SupplierEmailCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    supplier_name = payload.supplier_name.strip()
    email = payload.email.strip().lower()
    if not supplier_name or not email:
        raise HTTPException(status_code=400, detail="Supplier name and email are required")
    existing = (
        db.query(models.SupplierEmail)
        .filter(func.lower(models.SupplierEmail.supplier_name) == supplier_name.lower(), models.SupplierEmail.email == email)
        .first()
    )
    if existing:
        return existing
    row = models.SupplierEmail(supplier_name=supplier_name, email=email)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/supplier-emails/{email_id}")
def delete_supplier_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    row = db.query(models.SupplierEmail).filter(models.SupplierEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}


def send_purchase_order_email(purchase_order: models.PurchaseOrder, recipients: List[str]) -> str:
    """Email the finalized PO to every address on file for the brand (plus
    the request's own supplier_email if set) in a single send. Host, user,
    port, and from-address all default to the company Gmail mailbox
    (initiative.lucknow@gmail.com), so on Render the only secret you need
    to set is SMTP_PASSWORD (a Gmail App Password) - see README for setup."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_user = os.getenv("SMTP_USER", "initiative.lucknow@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "initiative.lucknow@gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    if not (smtp_host and smtp_user and smtp_password and recipients):
        print("[PO email] Not sent: SMTP_PASSWORD not set (or no recipients).")
        return "Not sent: SMTP is not configured (set SMTP_PASSWORD on the host)."

    lines = [
        f"Purchase Order: {purchase_order.request_no}",
        f"Date: {purchase_order.request_date}",
        f"Brand: {purchase_order.brand_name or '-'}",
        f"Division: {purchase_order.division or '-'}",
        f"Delivery address: {purchase_order.delivery_address or '-'}",
        "",
        "Items:",
    ]
    for item in purchase_order.items:
        variant = f" ({item.variant})" if item.variant else ""
        lines.append(f"  - {item.product_name}{variant} x {item.quantity} {item.unit or 'Nos'}")
    if purchase_order.remarks:
        lines.append("")
        lines.append(f"Remarks: {purchase_order.remarks}")
    body = "\n".join(lines)

    message = MIMEText(body)
    message["Subject"] = f"Purchase Order {purchase_order.request_no} - {purchase_order.brand_name or ''}"
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, recipients, message.as_string())
    except Exception as exc:  # noqa: BLE001 - surface any SMTP failure to the caller
        print(f"[PO email] SMTP send failed ({type(exc).__name__}): {exc}")
        return f"Not sent: email delivery failed ({type(exc).__name__}: {exc})."

    return f"Emailed to {len(recipients)} recipient(s)."


@app.post("/api/purchase-orders/{purchase_order_id}/send-email", response_model=schemas.SendPurchaseOrderEmailResult)
def send_purchase_order_email_endpoint(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    purchase_order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order request not found")
    if purchase_order.status not in {"Approved", "Ordered"}:
        raise HTTPException(
            status_code=400,
            detail="This purchase order must be Approved by Admin before it can be sent to the supplier.",
        )

    recipients = set()
    if purchase_order.brand_name:
        brand_rows = db.query(models.BrandSupplierEmail).filter(models.BrandSupplierEmail.brand_name == purchase_order.brand_name).all()
        recipients.update(row.email for row in brand_rows)
    if purchase_order.supplier_name:
        supplier_rows = (
            db.query(models.SupplierEmail)
            .filter(func.lower(models.SupplierEmail.supplier_name) == purchase_order.supplier_name.strip().lower())
            .all()
        )
        recipients.update(row.email for row in supplier_rows)
    if purchase_order.supplier_email:
        recipients.add(purchase_order.supplier_email.strip().lower())
    recipients = sorted(r for r in recipients if r)

    if not recipients:
        raise HTTPException(status_code=400, detail="No supplier emails on file for this brand or supplier yet. Add at least one first.")

    notification_status = send_purchase_order_email(purchase_order, recipients)
    return {"sent_to": recipients, "notification_status": notification_status}


@app.post("/api/purchase-orders", response_model=schemas.PurchaseOrderOut)
def create_purchase_order(
    payload: schemas.PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Add at least one purchase item")
    if any(not item.product_name.strip() or item.quantity <= 0 for item in payload.items):
        raise HTTPException(status_code=400, detail="Every item needs a product name and quantity greater than zero")

    purchase_order = models.PurchaseOrder(
        request_no=f"REQ-{payload.request_date.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        request_date=payload.request_date,
        division=payload.division,
        branch_id=payload.branch_id,
        brand_name=payload.brand_name,
        supplier_name=payload.supplier_name,
        supplier_email=payload.supplier_email,
        supplier_address=payload.supplier_address,
        supplier_gstin=payload.supplier_gstin,
        delivery_address=payload.delivery_address,
        remarks=payload.remarks,
        status="Requested",
        submitted_by_user_id=current_user.id,
    )
    purchase_order.items = [models.PurchaseOrderItem(**item.dict()) for item in payload.items]
    db.add(purchase_order)
    db.commit()
    db.refresh(purchase_order)

    if payload.supplier_name:
        upsert_supplier_profile(db, payload.supplier_name, payload.supplier_address, payload.supplier_gstin)
        for email in (payload.supplier_emails or ([payload.supplier_email] if payload.supplier_email else [])):
            upsert_supplier_email(db, payload.supplier_name, email)

    notification_status = send_purchase_order_whatsapp_notification(purchase_order)
    return serialize_purchase_order(purchase_order, notification_status)


@app.get("/api/purchase-orders", response_model=List[schemas.PurchaseOrderOut])
def list_purchase_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.PurchaseOrder)
    if current_user.role not in {"Admin", "MISExecutive"}:
        query = query.filter(models.PurchaseOrder.submitted_by_user_id == current_user.id)
    purchase_orders = query.order_by(models.PurchaseOrder.created_date.desc()).all()
    return [serialize_purchase_order(item) for item in purchase_orders]


@app.get("/api/purchase-orders/{purchase_order_id}", response_model=schemas.PurchaseOrderOut)
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    purchase_order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order request not found")
    if not can_access_purchase_order(current_user, purchase_order):
        raise HTTPException(status_code=403, detail="You can only view your own purchase requests")
    return serialize_purchase_order(purchase_order)


@app.patch("/api/purchase-orders/{purchase_order_id}/status", response_model=schemas.PurchaseOrderOut)
def update_purchase_order_status(
    purchase_order_id: int,
    payload: schemas.PurchaseOrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    status_value = (payload.status or "").strip()
    if status_value not in PURCHASE_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {sorted(PURCHASE_ORDER_STATUSES)}")

    purchase_order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order request not found")

    if status_value != purchase_order.status:
        assert_status_transition_allowed(current_user, purchase_order, status_value)

    if status_value == "Approved" and purchase_order.status != "Approved":
        purchase_order.approved_by_user_id = current_user.id
        purchase_order.approved_date = datetime.utcnow()
    elif status_value in {"Rejected", "Requested"}:
        # Sent back for changes or turned down - clear any prior approval so
        # it has to go through Admin again before it can be Ordered.
        purchase_order.approved_by_user_id = None
        purchase_order.approved_date = None

    purchase_order.status = status_value
    purchase_order.busy_po_number = (payload.busy_po_number or "").strip() or None
    purchase_order.ordered_date = payload.ordered_date
    purchase_order.processing_notes = (payload.processing_notes or "").strip() or None

    # Admin/MIS can fill in or correct procurement details while processing
    # a category manager's request. Only touch fields that were actually sent.
    if payload.division is not None:
        purchase_order.division = payload.division or None
    if payload.branch_id is not None:
        purchase_order.branch_id = payload.branch_id
    if payload.brand_name is not None:
        purchase_order.brand_name = payload.brand_name or None
    if payload.supplier_name is not None:
        purchase_order.supplier_name = payload.supplier_name or None
    if payload.supplier_email is not None:
        purchase_order.supplier_email = payload.supplier_email or None
    if payload.supplier_address is not None:
        purchase_order.supplier_address = payload.supplier_address or None
    if payload.supplier_gstin is not None:
        purchase_order.supplier_gstin = payload.supplier_gstin or None
    if payload.delivery_address is not None:
        purchase_order.delivery_address = payload.delivery_address or None
    if payload.remarks is not None:
        purchase_order.remarks = payload.remarks or None

    if payload.items is not None:
        if not payload.items:
            raise HTTPException(status_code=400, detail="A purchase order needs at least one item")
        if any(not item.product_name.strip() or item.quantity <= 0 for item in payload.items):
            raise HTTPException(status_code=400, detail="Every item needs a product name and quantity greater than zero")
        purchase_order.items = [models.PurchaseOrderItem(**item.dict()) for item in payload.items]

    db.commit()
    db.refresh(purchase_order)

    if purchase_order.supplier_name:
        upsert_supplier_profile(db, purchase_order.supplier_name, purchase_order.supplier_address, purchase_order.supplier_gstin)
        for email in (payload.supplier_emails or ([purchase_order.supplier_email] if purchase_order.supplier_email else [])):
            upsert_supplier_email(db, purchase_order.supplier_name, email)

    return serialize_purchase_order(purchase_order)


@app.delete("/api/purchase-orders/{purchase_order_id}")
def delete_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    purchase_order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order request not found")
    db.delete(purchase_order)
    db.commit()
    return {"message": "Purchase order request deleted"}


@app.post("/api/purchase-orders/mark-exported-to-busy")
def mark_purchase_orders_exported_to_busy(
    payload: schemas.MarkExportedToBusyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "MISExecutive")),
):
    """Called after downloading a batch export file for Busy's Import
    Vouchers feature, so the same requests aren't included in next time's
    export. Purely a bookkeeping flag on this side — it does not talk to
    Busy directly."""
    if not payload.purchase_order_ids:
        return {"updated": 0}
    now = datetime.utcnow()
    updated = (
        db.query(models.PurchaseOrder)
        .filter(models.PurchaseOrder.id.in_(payload.purchase_order_ids))
        .update({"exported_to_busy": True, "exported_to_busy_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


# ============================================================
# SCHEMES
# ============================================================

@app.post("/schemes", response_model=schemas.SchemeOut)
def create_scheme(
    scheme: schemas.SchemeCreate,
    db: Session = Depends(get_db),
    # Brand promoters/managers no longer get manual create rights - their
    # only path into the scheme table is "Attach Scheme Document"
    # (POST /schemes/upload-document), which always lands as a Draft for
    # an Admin to review.
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    scheme_code = (scheme.scheme_code or "").strip()
    if not scheme_code:
        # Auto-generate a unique code since the Scheme Maintenance form no
        # longer asks for one. Format: SCH-<epoch-milliseconds>.
        scheme_code = f"SCH-{int(datetime.utcnow().timestamp() * 1000)}"
    else:
        existing = (
            db.query(models.Scheme)
            .filter(models.Scheme.scheme_code == scheme_code)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Scheme code already exists")

    normalized_reward_type = normalize_reward_type(scheme.reward_type)
    normalized_offer_type = normalize_offer_type(scheme.offer_type)

    db_scheme = models.Scheme(
        scheme_code=scheme_code,
        scheme_name=scheme.scheme_name,
        brand_id=scheme.brand_id,
        category_id=scheme.category_id,
        subcategory_id=scheme.subcategory_id,
        product_id=scheme.product_id,
        variant_id=scheme.variant_id,
        offer_type=normalized_offer_type,
        offer_value=scheme.offer_value,
        calculation_method=scheme.calculation_method,
        start_date=scheme.start_date,
        end_date=scheme.end_date,
        min_qty=scheme.min_qty,
        max_qty=scheme.max_qty,
        applicable_branch_id=scheme.applicable_branch_id,
        applicable_customer=scheme.applicable_customer,
        applicable_dealer=scheme.applicable_dealer,
        circular_number=scheme.circular_number,
        remarks=scheme.remarks,
        reward_type=normalized_reward_type,
        reward_value=scheme.reward_value,
        reward_type_other=(scheme.reward_type_other or "").strip() or None,
        status=scheme.status,
    )
    db.add(db_scheme)
    db.commit()
    db.refresh(db_scheme)

    for cond in scheme.conditions:
        db.add(
            models.SchemeCondition(
                scheme_id=db_scheme.id,
                field_name=cond.field_name,
                operator=cond.operator,
                value=cond.value,
            )
        )

    for slab in scheme.slabs:
        db.add(
            models.SchemeSlab(
                scheme_id=db_scheme.id,
                min_quantity=slab.min_quantity,
                reward_per_unit=slab.reward_per_unit,
            )
        )

    db.commit()
    db.refresh(db_scheme)
    return db_scheme


@app.get("/schemes", response_model=List[schemas.SchemeOut])
def list_schemes(
    status: Optional[str] = Query(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Scheme)
    if status:
        query = query.filter(models.Scheme.status == status)
    if current_user.role != "Admin":
        # Draft schemes hold whatever a document upload extracted and
        # haven't been reviewed yet. Only Admin should see those fields -
        # everyone else (including the promoter who attached the
        # document) only sees schemes once they're Active/Paused.
        query = query.filter(models.Scheme.status != "Draft")
    return query.all()


@app.get("/schemes/my-attachments")
def list_my_scheme_attachments(
    current_user: models.User = Depends(auth.require_roles("Admin", "BrandManager", "BrandPartner")),
    db: Session = Depends(get_db),
):
    """Upload history for a brand promoter/manager. Deliberately excludes
    the extracted scheme fields (offer, reward value, target, etc.) -
    those stay hidden until an Admin reviews and activates the Draft.
    Non-admins only ever see their own uploads."""
    query = db.query(models.SchemeAttachment).order_by(models.SchemeAttachment.id.desc())
    if current_user.role != "Admin":
        query = query.filter(models.SchemeAttachment.uploaded_by_user_id == current_user.id)

    rows = []
    for attachment in query.limit(200).all():
        scheme = attachment.scheme
        brand = (
            db.query(models.Brand).filter(models.Brand.id == scheme.brand_id).first()
            if scheme and scheme.brand_id
            else None
        )
        uploader = (
            db.query(models.User).filter(models.User.id == attachment.uploaded_by_user_id).first()
            if attachment.uploaded_by_user_id
            else None
        )
        rows.append({
            "id": attachment.id,
            "scheme_id": attachment.scheme_id,
            "filename": attachment.original_filename,
            "brand": brand.name if brand else "Not matched yet",
            "uploaded_by": uploader.username if uploader else "",
            "uploaded_date": attachment.created_date.isoformat() if attachment.created_date else None,
            "review_status": "Reviewed" if scheme and scheme.status != "Draft" else "Pending review",
        })
    return rows


def apply_scheme_extraction(db: Session, db_scheme: "models.Scheme", attachment: "models.SchemeAttachment", extraction: dict) -> None:
    """Applies a Claude extraction result onto a Draft scheme + its
    attachment record. Shared by the upload endpoint (Admin uploads, which
    still extract immediately) and the Admin-triggered
    POST /schemes/{id}/extract endpoint (used for promoter uploads, which
    are deferred until an Admin runs OCR)."""
    attachment.extraction_status = extraction["status"]
    attachment.extraction_error = extraction.get("error")
    attachment.extraction_raw_json = json.dumps(extraction.get("data") or {})

    if extraction["status"] == "Extracted":
        data = extraction["data"]
        try:
            if data.get("brand_name") and db_scheme.brand_id is None:
                match = (
                    db.query(models.Brand)
                    .filter(func.lower(models.Brand.name) == str(data["brand_name"]).strip().lower())
                    .first()
                )
                if match:
                    db_scheme.brand_id = match.id

            if data.get("product_name"):
                product_match = (
                    db.query(models.Product)
                    .filter(func.lower(models.Product.name) == str(data["product_name"]).strip().lower())
                    .first()
                )
                if product_match:
                    db_scheme.product_id = product_match.id

            if data.get("scheme_name"):
                db_scheme.scheme_name = str(data["scheme_name"]).strip()[:200] or db_scheme.scheme_name
            if data.get("start_date"):
                db_scheme.start_date = parse_date_value(data["start_date"])
            if data.get("end_date"):
                db_scheme.end_date = parse_date_value(data["end_date"])
            if data.get("reward_type"):
                db_scheme.reward_type = normalize_reward_type(data["reward_type"])
            if data.get("reward_value") is not None:
                db_scheme.reward_value = parse_float_value(data.get("reward_value"), fallback=0.0)
            if data.get("min_qty") is not None:
                db_scheme.min_qty = int(parse_float_value(data.get("min_qty"), fallback=0.0))
            if data.get("max_qty"):
                db_scheme.max_qty = int(parse_float_value(data.get("max_qty"), fallback=0.0))
            if data.get("offer_type"):
                db_scheme.offer_type = normalize_offer_type(data["offer_type"])
            if data.get("circular_number"):
                db_scheme.circular_number = str(data["circular_number"])[:50]

            extracted_remarks = str(data.get("remarks") or "").strip()
            db_scheme.remarks = (
                (extracted_remarks or "Extracted from attached scheme document.")
                + " (Draft - review before activating.)"
            )[:255]

            for slab in data.get("slabs") or []:
                try:
                    db.add(models.SchemeSlab(
                        scheme_id=db_scheme.id,
                        min_quantity=int(slab.get("min_quantity") or 0),
                        reward_per_unit=float(slab.get("reward_per_unit") or 0),
                    ))
                except Exception:
                    continue
        except Exception as exc:
            attachment.extraction_status = "Failed"
            attachment.extraction_error = f"Extracted data didn't fit the scheme form: {exc}"


@app.post("/schemes/upload-document")
def upload_scheme_document(
    file: UploadFile = File(...),
    brand_id: Optional[int] = Query(None),
    scheme_name: Optional[str] = Query(None),
    current_user: models.User = Depends(auth.require_roles("Admin", "BrandManager", "BrandPartner")),
    db: Session = Depends(get_db),
):
    """A promoter/brand manager attaches a scheme circular (image, PDF, or
    Excel). This creates a Draft scheme and saves the document. When an
    Admin uploads directly, Claude reads it immediately (Admin already
    reviews everything). When a promoter/brand manager uploads, extraction
    is deferred - the document just sits in "Draft Schemes Pending
    Review" until an Admin clicks "Extract (OCR)" there. Either way, Admin
    reviews and hits Activate (existing PUT /schemes/{id}/activate) when
    it looks right."""
    filename = file.filename or "scheme_document"
    raw_bytes = file.file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if current_user.role in {"BrandManager", "BrandPartner"}:
        allowed_brand_ids = [ub.brand_id for ub in current_user.brands]
        if not allowed_brand_ids:
            raise HTTPException(status_code=403, detail="Your account has no brand assigned yet. Ask an Admin to assign one.")
        if brand_id is None:
            brand_id = allowed_brand_ids[0]
        elif brand_id not in allowed_brand_ids:
            raise HTTPException(status_code=403, detail="You can only attach documents for your own assigned brand(s).")

    today = date.today()
    db_scheme = models.Scheme(
        scheme_code=f"SCH-{int(datetime.utcnow().timestamp() * 1000)}",
        scheme_name=(scheme_name or "").strip() or f"Pending review - {filename}",
        brand_id=brand_id,
        start_date=today,
        end_date=today,
        status="Draft",
        reward_type="Fixed",
        reward_value=0,
        offer_type="Backend",
        calculation_method="Fixed Amount",
        remarks="Awaiting extraction from attached document.",
    )
    db.add(db_scheme)
    db.commit()
    db.refresh(db_scheme)

    content_type = file.content_type or ""
    attachment = models.SchemeAttachment(
        scheme_id=db_scheme.id,
        original_filename=filename,
        content_type=content_type,
        file_size=len(raw_bytes),
        file_data=raw_bytes,
        uploaded_by_user_id=current_user.id,
        extraction_status="Pending",
    )
    db.add(attachment)
    db.commit()

    if current_user.role == "Admin":
        # Admin uploads still extract right away, same as before.
        extraction = extract_scheme_from_document(db, filename, content_type, raw_bytes)
        apply_scheme_extraction(db, db_scheme, attachment, extraction)
        db.commit()
        db.refresh(db_scheme)
        db.refresh(attachment)

    return {
        "scheme_id": db_scheme.id,
        "scheme_code": db_scheme.scheme_code,
        "status": db_scheme.status,
        "extraction_status": attachment.extraction_status,
        "extraction_error": attachment.extraction_error,
        "message": (
            "Document attached and scheme fields pre-filled. Review and Activate when ready."
            if attachment.extraction_status == "Extracted"
            else "Document attached. An Admin will review it shortly."
            if current_user.role != "Admin"
            else "Document attached, but automatic extraction did not complete - fill the scheme fields manually before activating."
        ),
    }


@app.post("/schemes/{scheme_id}/extract")
def extract_scheme_document(
    scheme_id: int,
    current_user: models.User = Depends(auth.require_roles("Admin")),
    db: Session = Depends(get_db),
):
    """Admin-triggered OCR/extraction for a Draft scheme's most recently
    attached document - used for promoter/brand-manager uploads, which no
    longer auto-extract at upload time."""
    db_scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not db_scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    attachment = (
        db.query(models.SchemeAttachment)
        .filter(models.SchemeAttachment.scheme_id == scheme_id)
        .order_by(models.SchemeAttachment.id.desc())
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="No document attached to this scheme")

    extraction = extract_scheme_from_document(
        db, attachment.original_filename, attachment.content_type or "", attachment.file_data
    )
    apply_scheme_extraction(db, db_scheme, attachment, extraction)
    db.commit()
    db.refresh(db_scheme)
    db.refresh(attachment)

    return {
        "scheme_id": db_scheme.id,
        "extraction_status": attachment.extraction_status,
        "extraction_error": attachment.extraction_error,
        "message": (
            "Extraction complete. Review the fields and Activate when ready."
            if attachment.extraction_status == "Extracted"
            else "Automatic extraction did not complete - fill the scheme fields manually before activating."
        ),
    }


@app.get("/schemes/drafts")
def list_draft_schemes(
    current_user: models.User = Depends(auth.require_roles("Admin")),
    db: Session = Depends(get_db),
):
    """Admin-only feed for the "Draft Schemes Pending Review" table -
    includes attachment/extraction status so the UI can decide whether to
    show "Extract (OCR)" or the normal Edit/Activate actions."""
    drafts = (
        db.query(models.Scheme)
        .filter(models.Scheme.status == "Draft")
        .order_by(models.Scheme.id.desc())
        .all()
    )

    rows = []
    for scheme in drafts:
        brand = db.query(models.Brand).filter(models.Brand.id == scheme.brand_id).first() if scheme.brand_id else None
        attachment = (
            db.query(models.SchemeAttachment)
            .filter(models.SchemeAttachment.scheme_id == scheme.id)
            .order_by(models.SchemeAttachment.id.desc())
            .first()
        )
        rows.append({
            "id": scheme.id,
            "scheme_name": scheme.scheme_name,
            "brand": brand.name if brand else "Not matched",
            "start_date": str(scheme.start_date) if scheme.start_date else "",
            "end_date": str(scheme.end_date) if scheme.end_date else "",
            "reward_type": scheme.reward_type,
            "reward_value": scheme.reward_value,
            "extraction_status": attachment.extraction_status if attachment else "Pending",
            "extraction_error": attachment.extraction_error if attachment else None,
            "filename": attachment.original_filename if attachment else None,
        })
    return rows


@app.get("/schemes/{scheme_id}/attachment")
def download_scheme_attachment(
    scheme_id: int,
    current_user: models.User = Depends(auth.require_roles("Admin", "BrandManager", "BrandPartner")),
    db: Session = Depends(get_db),
):
    attachment = (
        db.query(models.SchemeAttachment)
        .filter(models.SchemeAttachment.scheme_id == scheme_id)
        .order_by(models.SchemeAttachment.id.desc())
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="No document attached to this scheme")

    if current_user.role in {"BrandManager", "BrandPartner"}:
        scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
        allowed_brand_ids = [ub.brand_id for ub in current_user.brands]
        if not scheme or scheme.brand_id not in allowed_brand_ids:
            raise HTTPException(status_code=403, detail="You can only view documents for your own brand's schemes.")

    return Response(
        content=attachment.file_data,
        media_type=attachment.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{attachment.original_filename}"'},
    )


@app.put("/schemes/{scheme_id}", response_model=schemas.SchemeOut)
def update_scheme(
    scheme_id: int,
    scheme: schemas.SchemeCreate,
    db: Session = Depends(get_db),
    # Editing (including Draft review/correction) is Admin-only. Brand
    # promoters/managers only attach documents; they don't see or touch
    # the extracted fields.
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    db_scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not db_scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    normalized_reward_type = normalize_reward_type(scheme.reward_type)
    normalized_offer_type = normalize_offer_type(scheme.offer_type)

    db_scheme.scheme_name = scheme.scheme_name
    db_scheme.brand_id = scheme.brand_id
    db_scheme.category_id = scheme.category_id
    db_scheme.subcategory_id = scheme.subcategory_id
    db_scheme.product_id = scheme.product_id
    db_scheme.variant_id = scheme.variant_id
    db_scheme.offer_type = normalized_offer_type
    db_scheme.offer_value = scheme.offer_value
    db_scheme.calculation_method = scheme.calculation_method
    db_scheme.start_date = scheme.start_date
    db_scheme.end_date = scheme.end_date
    db_scheme.min_qty = scheme.min_qty
    db_scheme.max_qty = scheme.max_qty
    db_scheme.applicable_branch_id = scheme.applicable_branch_id
    db_scheme.applicable_customer = scheme.applicable_customer
    db_scheme.applicable_dealer = scheme.applicable_dealer
    db_scheme.circular_number = scheme.circular_number
    db_scheme.remarks = scheme.remarks
    db_scheme.reward_type = normalized_reward_type
    db_scheme.reward_value = scheme.reward_value
    db_scheme.reward_type_other = (scheme.reward_type_other or "").strip() or None
    db_scheme.status = scheme.status

    # Replace conditions/slabs entirely with whatever was submitted.
    db_scheme.conditions.clear()
    db_scheme.slabs.clear()
    db.flush()

    for cond in scheme.conditions:
        db.add(
            models.SchemeCondition(
                scheme_id=db_scheme.id,
                field_name=cond.field_name,
                operator=cond.operator,
                value=cond.value,
            )
        )

    for slab in scheme.slabs:
        db.add(
            models.SchemeSlab(
                scheme_id=db_scheme.id,
                min_quantity=slab.min_quantity,
                reward_per_unit=slab.reward_per_unit,
            )
        )

    db.commit()
    db.refresh(db_scheme)
    return db_scheme


@app.put("/schemes/{scheme_id}/pause")
def pause_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    scheme.status = "Paused"
    db.commit()
    return {"message": f"Scheme {scheme_id} paused"}


@app.put("/schemes/{scheme_id}/activate")
def activate_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    scheme.status = "Active"
    db.commit()
    return {"message": f"Scheme {scheme_id} activated"}


@app.delete("/schemes/{scheme_id}")
def delete_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    existing_claims = (
        db.query(models.ClaimHeader.id)
        .filter(models.ClaimHeader.scheme_id == scheme_id)
        .count()
    )
    if existing_claims:
        raise HTTPException(
            status_code=400,
            detail="This scheme has claims linked to it and can't be deleted. Pause it instead.",
        )

    # SchemeCondition and SchemeSlab rows are removed automatically via the
    # cascade="all, delete-orphan" relationship on the Scheme model.
    db.delete(scheme)
    db.commit()
    return {"message": f"Scheme {scheme_id} deleted"}


# ============================================================
# SALES (this is what TRIGGERS the scheme engine)
# ============================================================

@app.post("/sales", response_model=schemas.SaleOut)
def create_sale(
    sale: schemas.SaleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    allowed_roles = {"Admin", "StoreManager", "CategoryManager", "BrandManager", "BrandPartner", "Super Admin", "Management", "Branch Manager", "Sales Executive", "Scheme Manager"}
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="You are not allowed to create sales")

    if current_user.role in {"StoreManager", "Branch Manager"}:
        if current_user.store_id is None or sale.store_id != current_user.store_id:
            raise HTTPException(status_code=403, detail="You can only create sales for your assigned branch")

    if current_user.role == "CategoryManager":
        if not current_user.category_code:
            raise HTTPException(status_code=403, detail="You are not assigned to a category")
        sale_category = db.query(models.Category).filter(models.Category.id == sale.category_id).first()
        if not sale_category or sale_category.code != current_user.category_code:
            raise HTTPException(status_code=403, detail="You can only create sales for your assigned category")

    if current_user.role in {"BrandManager", "BrandPartner", "Scheme Manager"}:
        brand_ids = [ub.brand_id for ub in current_user.brands]
        if sale.brand_id not in brand_ids:
            raise HTTPException(status_code=403, detail="You can only create sales for your assigned brands")

    existing = (
        db.query(models.Sale)
        .filter(models.Sale.invoice_no == sale.invoice_no)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    def quantize_money(raw_text: Optional[str], numeric_value: Optional[float], field_name: str):
        if raw_text is not None and str(raw_text).strip() != "":
            cleaned = str(raw_text).strip()
            try:
                dec = Decimal(cleaned)
            except Exception:
                raise HTTPException(status_code=400, detail=f"{field_name} must be a valid number")
            dec = dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(dec), cleaned

        if numeric_value is None:
            return None, None

        dec = Decimal(str(numeric_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fallback_text = format(dec, "f").rstrip("0").rstrip(".")
        if not fallback_text:
            fallback_text = "0"
        return float(dec), fallback_text

    # Keep money fields stable at 2 decimals so users see the same values they entered.
    sale_value_num, sale_value_exact = quantize_money(sale.sale_value_exact, sale.sale_value, "sale_value")
    scheme_amount_num, scheme_amount_exact = quantize_money(sale.scheme_amount_exact, sale.scheme_amount, "scheme_amount")
    upi_amount_num, upi_amount_exact = quantize_money(sale.upi_scheme_amount_exact, sale.upi_scheme_amount, "upi_scheme_amount")
    backend_amount_num, backend_amount_exact = quantize_money(sale.backend_scheme_amount_exact, sale.backend_scheme_amount, "backend_scheme_amount")

    sale.sale_value = sale_value_num
    sale.sale_value_exact = sale_value_exact
    sale.scheme_amount = scheme_amount_num
    sale.scheme_amount_exact = scheme_amount_exact
    sale.upi_scheme_amount = upi_amount_num
    sale.upi_scheme_amount_exact = upi_amount_exact
    sale.backend_scheme_amount = backend_amount_num
    sale.backend_scheme_amount_exact = backend_amount_exact

    db_sale = models.Sale(**sale.dict())
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)

    scheme_engine.evaluate_sale_against_schemes(db, db_sale)

    return db_sale


@app.put("/sales/{sale_id}", response_model=schemas.SaleOut)
def update_sale(
    sale_id: int,
    sale: schemas.SaleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in ("Admin", "MISExecutive"):
        raise HTTPException(status_code=403, detail="You are not allowed to edit sales")

    db_sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not db_sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    duplicate_invoice = (
        db.query(models.Sale)
        .filter(models.Sale.invoice_no == sale.invoice_no, models.Sale.id != sale_id)
        .first()
    )
    if duplicate_invoice:
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    def quantize_money(raw_text: Optional[str], numeric_value: Optional[float], field_name: str):
        if raw_text is not None and str(raw_text).strip() != "":
            cleaned = str(raw_text).strip()
            try:
                dec = Decimal(cleaned)
            except Exception:
                raise HTTPException(status_code=400, detail=f"{field_name} must be a valid number")
            dec = dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(dec), cleaned

        if numeric_value is None:
            return None, None

        dec = Decimal(str(numeric_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fallback_text = format(dec, "f").rstrip("0").rstrip(".")
        if not fallback_text:
            fallback_text = "0"
        return float(dec), fallback_text

    sale_value_num, sale_value_exact = quantize_money(sale.sale_value_exact, sale.sale_value, "sale_value")
    scheme_amount_num, scheme_amount_exact = quantize_money(sale.scheme_amount_exact, sale.scheme_amount, "scheme_amount")
    upi_amount_num, upi_amount_exact = quantize_money(sale.upi_scheme_amount_exact, sale.upi_scheme_amount, "upi_scheme_amount")
    backend_amount_num, backend_amount_exact = quantize_money(sale.backend_scheme_amount_exact, sale.backend_scheme_amount, "backend_scheme_amount")

    sale.sale_value = sale_value_num
    sale.sale_value_exact = sale_value_exact
    sale.scheme_amount = scheme_amount_num
    sale.scheme_amount_exact = scheme_amount_exact
    sale.upi_scheme_amount = upi_amount_num
    sale.upi_scheme_amount_exact = upi_amount_exact
    sale.backend_scheme_amount = backend_amount_num
    sale.backend_scheme_amount_exact = backend_amount_exact

    for field_name, value in sale.dict().items():
        setattr(db_sale, field_name, value)

    db.commit()
    db.refresh(db_sale)
    return db_sale


@app.get("/sales", response_model=List[schemas.SaleOut])
def list_sales(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return get_sales_for_user(db, current_user)


@app.delete("/sales/{sale_id}")
def delete_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="You are not allowed to delete sales")

    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    if not can_user_access_sale(db, current_user, sale):
        raise HTTPException(status_code=403, detail="You can only delete sales in your access scope")

    claim_ids = [cid for (cid,) in db.query(models.ClaimHeader.id).filter(models.ClaimHeader.sale_id == sale.id).all()]
    if claim_ids:
        db.query(models.ClaimStatusHistory).filter(models.ClaimStatusHistory.claim_id.in_(claim_ids)).delete(synchronize_session=False)
        db.query(models.ClaimHeader).filter(models.ClaimHeader.id.in_(claim_ids)).delete(synchronize_session=False)

    db.delete(sale)
    db.commit()
    return {"message": f"Sale {sale_id} deleted successfully"}


@app.get("/dashboard-stats")
def dashboard_stats(db: Session = Depends(get_db)):
    from datetime import date
    today = date.today()

    active_schemes = db.query(models.Scheme).filter(models.Scheme.status == "Active").count()
    expired_schemes = db.query(models.Scheme).filter(models.Scheme.status != "Active").count()
    todays_sales = db.query(models.Sale).filter(models.Sale.sale_date == today).count()
    pending_claims = db.query(models.ClaimHeader).filter(models.ClaimHeader.status == "Draft").count()
    approved_claims = db.query(models.ClaimHeader).filter(models.ClaimHeader.status == "Approved").count()
    rejected_claims = db.query(models.ClaimHeader).filter(models.ClaimHeader.status == "Rejected").count()
    received_claims = db.query(models.ClaimHeader).filter(models.ClaimHeader.status == "Received").count()
    total_claim_amount = sum(claim.claim_amount for claim in db.query(models.ClaimHeader).all())
    pending_amount = sum(claim.claim_amount for claim in db.query(models.ClaimHeader).filter(models.ClaimHeader.status.in_(["Draft", "Pending", "Submitted"])).all())

    return {
        "active_schemes": active_schemes,
        "expired_schemes": expired_schemes,
        "todays_sales": todays_sales,
        "eligible_sales": db.query(models.ClaimHeader).count(),
        "total_claim_amount": round(total_claim_amount, 2),
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "received_claims": received_claims,
        "pending_amount": round(pending_amount, 2),
    }


@app.post("/admin/interval-sales/upload")
def upload_interval_sales_file(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.require_roles("Admin")),
    db: Session = Depends(get_db),
):
    filename = file.filename or "uploaded_file"
    ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
    raw_content = file.file.read()
    if not raw_content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    parsed_rows = parse_tabular_rows(ext, raw_content)
    if not parsed_rows:
        raise HTTPException(status_code=400, detail="No readable sales rows found. Ensure columns include Date, Vch No, Item, Qty, Sales Amt, Cost Amt, Profit/Loss, Profit %")

    inserted_count = 0
    skipped_rows = []
    for idx, row in enumerate(parsed_rows, start=1):
        try:
            sale_date = parse_date_value(row.get("sale_date"))
            vch_no = str(row.get("vch_no") or "").strip() or None
            account = str(row.get("account") or "").strip() or None
            item = str(row.get("item") or "").strip() or None
            qty = parse_float_value(row.get("qty"), fallback=0.0)
            unit = str(row.get("unit") or "").strip() or None
            sales_amt = parse_float_value(row.get("sales_amt"), fallback=0.0)
            cost_amt = parse_float_value(row.get("cost_amt"), fallback=0.0)
            profit_loss = parse_float_value(row.get("profit_loss"), fallback=sales_amt - cost_amt)
            profit_percent = parse_float_value(
                row.get("profit_percent"),
                fallback=((profit_loss / sales_amt) * 100.0 if sales_amt else 0.0),
            )

            db.add(
                models.IntervalSaleUpload(
                    sale_date=sale_date,
                    vch_no=vch_no,
                    account=account,
                    item=item,
                    qty=qty,
                    unit=unit,
                    sales_amt=sales_amt,
                    cost_amt=cost_amt,
                    profit_loss=profit_loss,
                    profit_percent=profit_percent,
                    source_file=filename,
                    uploaded_by=current_user.id,
                )
            )
            inserted_count += 1
        except Exception as exc:
            skipped_rows.append({"row": idx, "reason": str(exc)})

    db.commit()

    return {
        "message": "File processed successfully",
        "file_name": filename,
        "inserted": inserted_count,
        "skipped": len(skipped_rows),
        "errors_preview": skipped_rows[:10],
    }


@app.delete("/admin/interval-sales/clear")
def clear_interval_sales_data(
    current_user: models.User = Depends(auth.require_roles("Admin")),
    db: Session = Depends(get_db),
):
    deleted_count = db.query(models.IntervalSaleUpload).delete()
    db.commit()
    return {"message": "All uploaded interval sales data cleared", "deleted": deleted_count}


@app.get("/admin/interval-sales/summary")
def interval_sales_summary(
    interval: str = Query("daily", pattern="^(daily|weekly|monthly|custom)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: models.User = Depends(auth.require_roles("Admin", "Accounts", "MISExecutive")),
    db: Session = Depends(get_db),
):
    query = db.query(models.IntervalSaleUpload)
    if start_date:
        query = query.filter(models.IntervalSaleUpload.sale_date >= start_date)
    if end_date:
        query = query.filter(models.IntervalSaleUpload.sale_date <= end_date)

    rows = query.order_by(models.IntervalSaleUpload.sale_date.asc()).all()
    data = build_interval_analytics(rows, interval="daily" if interval == "custom" else interval)
    data["filters"] = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "requested_interval": interval,
    }
    data["sources"] = [
        {
            "file": file_name,
            "rows": count,
        }
        for file_name, count in (
            db.query(models.IntervalSaleUpload.source_file, text("COUNT(*)"))
            .group_by(models.IntervalSaleUpload.source_file)
            .order_by(text("COUNT(*) DESC"))
            .limit(5)
            .all()
        )
    ]
    return data


@app.get("/admin/interval-sales/records")
def interval_sales_records(
    limit: int = Query(200, ge=1, le=2000),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: models.User = Depends(auth.require_roles("Admin", "Accounts", "MISExecutive")),
    db: Session = Depends(get_db),
):
    query = db.query(models.IntervalSaleUpload)
    if start_date:
        query = query.filter(models.IntervalSaleUpload.sale_date >= start_date)
    if end_date:
        query = query.filter(models.IntervalSaleUpload.sale_date <= end_date)

    rows = (
        query.order_by(models.IntervalSaleUpload.sale_date.desc(), models.IntervalSaleUpload.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "sale_date": row.sale_date,
            "vch_no": row.vch_no,
            "account": row.account,
            "item": row.item,
            "qty": row.qty,
            "unit": row.unit,
            "sales_amt": row.sales_amt,
            "cost_amt": row.cost_amt,
            "profit_loss": row.profit_loss,
            "profit_percent": row.profit_percent,
            "source_file": row.source_file,
            "created_date": row.created_date,
        }
        for row in rows
    ]


@app.get("/admin/interval-sales/scheme-matches")
def interval_sales_scheme_matches(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: models.User = Depends(auth.require_roles("Admin", "Accounts", "MISExecutive")),
    db: Session = Depends(get_db),
):
    """Feeds 'Sales in your scope': out of the uploaded profitability report
    (Interval Sales Analytics Upload), return only the rows whose item and
    sale date fall inside an Active scheme from Scheme Maintenance, with the
    backend claim amount computed for each - so Admin can see exactly which
    Busy sales are scheme-eligible without re-typing anything."""
    filters = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    empty_result = {"matches": [], "totals": {"records": 0, "qty": 0, "sales_amt": 0, "backend_amount": 0}, "filters": filters}

    sales_query = db.query(models.IntervalSaleUpload)
    if start_date:
        sales_query = sales_query.filter(models.IntervalSaleUpload.sale_date >= start_date)
    if end_date:
        sales_query = sales_query.filter(models.IntervalSaleUpload.sale_date <= end_date)
    sale_rows = sales_query.all()
    if not sale_rows:
        return empty_result

    active_schemes = db.query(models.Scheme).filter(models.Scheme.status == "Active").all()
    if not active_schemes:
        return empty_result

    # For each scheme, the exact product-name set it applies to: its own
    # product if one is set, else every product under its brand.
    scheme_product_names = {}
    for scheme in active_schemes:
        names = set()
        if scheme.product_id:
            product = db.query(models.Product).filter(models.Product.id == scheme.product_id).first()
            if product:
                names.add(product.name.strip().lower())
        elif scheme.brand_id:
            for product in db.query(models.Product).filter(models.Product.brand_id == scheme.brand_id).all():
                names.add(product.name.strip().lower())
        scheme_product_names[scheme.id] = names

    matches = []
    for row in sale_rows:
        item_name = (row.item or "").strip().lower()
        if not item_name:
            continue
        for scheme in active_schemes:
            if not (scheme.start_date <= row.sale_date <= scheme.end_date):
                continue
            if item_name not in scheme_product_names.get(scheme.id, set()):
                continue

            backend_amount = _calculate_reward_for_interval_row(scheme, row)
            if backend_amount <= 0:
                continue

            matches.append({
                "sale_id": row.id,
                "sale_date": row.sale_date.isoformat(),
                "vch_no": row.vch_no,
                "account": row.account,
                "item": row.item,
                "qty": row.qty,
                "unit": row.unit,
                "sales_amt": row.sales_amt,
                "scheme_id": scheme.id,
                "scheme_code": scheme.scheme_code,
                "scheme_name": scheme.scheme_name,
                "reward_type": scheme.reward_type,
                "backend_amount": round(backend_amount, 2),
            })
            break  # a sale counts once, against its first matching scheme

    totals = {
        "records": len(matches),
        "qty": round(sum(m["qty"] or 0 for m in matches), 2),
        "sales_amt": round(sum(m["sales_amt"] or 0 for m in matches), 2),
        "backend_amount": round(sum(m["backend_amount"] for m in matches), 2),
    }

    return {
        "matches": sorted(matches, key=lambda m: m["sale_date"], reverse=True),
        "totals": totals,
        "filters": filters,
    }


# ============================================================
# CLAIMS
# ============================================================

@app.get("/claims", response_model=List[schemas.ClaimOut])
def list_claims(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return get_claims_for_user(db, current_user)


@app.put("/claims/{claim_id}/status")
def update_claim_status(
    claim_id: int, update: schemas.ClaimStatusUpdate, db: Session = Depends(get_db)
):
    claim = db.query(models.ClaimHeader).filter(models.ClaimHeader.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    old_status = claim.status
    claim.status = update.new_status
    db.commit()

    history = models.ClaimStatusHistory(
        claim_id=claim.id,
        old_status=old_status,
        new_status=update.new_status,
        remarks=update.remarks,
    )
    db.add(history)
    db.commit()

    return {
        "message": f"Claim {claim_id} status changed from {old_status} to {update.new_status}"
    }