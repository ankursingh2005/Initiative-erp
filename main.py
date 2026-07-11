from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from io import BytesIO
from collections import defaultdict
import csv
import re
import importlib

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

    ensure_column("schemes", "brand_id", "INTEGER")
    ensure_column("schemes", "category_id", "INTEGER")
    ensure_column("schemes", "subcategory_id", "INTEGER")
    ensure_column("schemes", "product_id", "INTEGER")
    ensure_column("schemes", "variant_id", "INTEGER")
    ensure_column("schemes", "offer_type", "VARCHAR(50)")
    ensure_column("schemes", "offer_value", "FLOAT")
    ensure_column("schemes", "calculation_method", "VARCHAR(50)")
    ensure_column("schemes", "min_qty", "INTEGER")
    ensure_column("schemes", "max_qty", "INTEGER")
    ensure_column("schemes", "applicable_branch_id", "INTEGER")
    ensure_column("schemes", "applicable_customer", "VARCHAR(100)")
    ensure_column("schemes", "applicable_dealer", "VARCHAR(100)")
    ensure_column("schemes", "circular_number", "VARCHAR(50)")
    ensure_column("schemes", "remarks", "VARCHAR(255)")

    ensure_column("users", "store_id", "INTEGER")
    ensure_column("users", "category_code", "VARCHAR(20)")
    ensure_column("users", "status", "VARCHAR(20)")
    ensure_column("users", "created_date", "DATETIME")


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
            ]

            mobile_subcategories = (
                db.query(models.SubCategory)
                .filter(models.SubCategory.category_id == mh_category.id)
                .all()
            )

            if mobile_subcategories:
                for index, brand_name in enumerate(mobile_brand_names):
                    target_subcategory = mobile_subcategories[index % len(mobile_subcategories)]
                    existing_brand = (
                        db.query(models.Brand)
                        .filter(models.Brand.name.ilike(brand_name))
                        .first()
                    )
                    if existing_brand:
                        existing_brand.subcategory_id = target_subcategory.id
                    else:
                        db.add(models.Brand(name=brand_name, subcategory_id=target_subcategory.id))

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
                    existing_brand = (
                        db.query(models.Brand)
                        .filter(models.Brand.name.ilike(brand_name))
                        .first()
                    )
                    if existing_brand:
                        if existing_brand.subcategory_id != led_tv_subcategory.id:
                            existing_brand.subcategory_id = led_tv_subcategory.id
                    else:
                        db.add(models.Brand(name=brand_name, subcategory_id=led_tv_subcategory.id))

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
                    existing_brand = (
                        db.query(models.Brand)
                        .filter(models.Brand.name.ilike(brand_name))
                        .first()
                    )
                    if existing_brand:
                        if existing_brand.subcategory_id != laptop_subcategory.id:
                            existing_brand.subcategory_id = laptop_subcategory.id
                    else:
                        db.add(models.Brand(name=brand_name, subcategory_id=laptop_subcategory.id))

                db.commit()


ensure_default_branches()
ensure_default_master_data()

app = FastAPI(title="IDSPL Scheme Management ERP")

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
    raise HTTPException(status_code=400, detail="reward_type must be one of: Fixed Amount, Target Based, %, Slab")


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


@app.get("/dashboard")
@app.get("/dashboard.html")
def dashboard_page():
    return serve_html("static/dashboard.html")


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

    if user.role in ("BrandManager", "BrandPartner"):
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


@app.post("/auth/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")

    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    if not username and not email:
        raise HTTPException(status_code=400, detail="Enter username or email to reset the password")

    query = db.query(models.User)
    if username and email:
        user = query.filter((models.User.username == username) | (models.User.email == email)).first()
    elif username:
        user = query.filter(models.User.username == username).first()
    else:
        user = query.filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found for the provided username or email")

    user.password_hash = auth.hash_password(payload.new_password)
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
        query = (
            query.join(models.SubCategory, models.Brand.subcategory_id == models.SubCategory.id)
            .filter(models.SubCategory.category_id == category_id)
        )
    return query.order_by(models.Brand.name).all()


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
# SCHEMES
# ============================================================

@app.post("/schemes", response_model=schemas.SchemeOut)
def create_scheme(
    scheme: schemas.SchemeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    existing = (
        db.query(models.Scheme)
        .filter(models.Scheme.scheme_code == scheme.scheme_code)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Scheme code already exists")

    normalized_reward_type = normalize_reward_type(scheme.reward_type)
    normalized_offer_type = normalize_offer_type(scheme.offer_type)

    db_scheme = models.Scheme(
        scheme_code=scheme.scheme_code,
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
def list_schemes(db: Session = Depends(get_db)):
    return db.query(models.Scheme).all()


@app.put("/schemes/{scheme_id}/pause")
def pause_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    scheme.status = "Paused"
    db.commit()
    return {"message": f"Scheme {scheme_id} paused"}


@app.put("/schemes/{scheme_id}/activate")
def activate_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    scheme.status = "Active"
    db.commit()
    return {"message": f"Scheme {scheme_id} activated"}


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

    sale.sale_value = sale_value_num
    sale.sale_value_exact = sale_value_exact
    sale.scheme_amount = scheme_amount_num
    sale.scheme_amount_exact = scheme_amount_exact

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

    sale.sale_value = sale_value_num
    sale.sale_value_exact = sale_value_exact
    sale.scheme_amount = scheme_amount_num
    sale.scheme_amount_exact = scheme_amount_exact

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