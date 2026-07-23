from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, LargeBinary, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


# ============================================================
# SIMPLE MASTER TABLES
# (Just enough to test the scheme engine realistically.
#  Your full ERP will expand these later with more fields.)
# ============================================================

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    subcategory_id = Column(Integer, ForeignKey("sub_categories.id"), nullable=True)

    products = relationship("Product", back_populates="brand", cascade="all, delete-orphan")
    subcategory = relationship("SubCategory", back_populates="brands")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)

    subcategories = relationship("SubCategory", back_populates="category", cascade="all, delete-orphan")


class SubCategory(Base):
    __tablename__ = "sub_categories"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(100), nullable=False)

    category = relationship("Category", back_populates="subcategories")
    brands = relationship("Brand", back_populates="subcategory")


class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=True)
    city = Column(String(100), nullable=True)
    status = Column(String(20), default="Active")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    name = Column(String(150), nullable=False)

    brand = relationship("Brand", back_populates="products")
    variants = relationship("Variant", back_populates="product", cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String(150), nullable=False)

    product = relationship("Product", back_populates="variants")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    city = Column(String(100), nullable=True)


class Dealer(Base):
    __tablename__ = "dealers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=True)
    contact = Column(String(50), nullable=True)


# ============================================================
# SCHEME TABLES
# ============================================================

class Scheme(Base):
    __tablename__ = "schemes"
    id = Column(Integer, primary_key=True, index=True)
    scheme_code = Column(String(50), unique=True, nullable=False)
    scheme_name = Column(String(200), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    subcategory_id = Column(Integer, ForeignKey("sub_categories.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=True)
    offer_type = Column(String(50), nullable=False, default="Backend")
    offer_value = Column(Float, default=0)
    calculation_method = Column(String(50), nullable=False, default="Fixed Amount")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    min_qty = Column(Integer, default=0)
    max_qty = Column(Integer, nullable=True)
    applicable_branch_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    applicable_customer = Column(String(100), nullable=True)
    applicable_dealer = Column(String(100), nullable=True)
    status = Column(String(20), default="Active")
    circular_number = Column(String(50), nullable=True)
    remarks = Column(String(255), nullable=True)
    reward_type = Column(String(20), nullable=False, default="Fixed")
    reward_value = Column(Float, default=0)
    reward_type_other = Column(String(100), nullable=True)

    created_date = Column(DateTime, default=datetime.utcnow)

    conditions = relationship(
        "SchemeCondition", back_populates="scheme", cascade="all, delete-orphan"
    )
    slabs = relationship(
        "SchemeSlab", back_populates="scheme", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "SchemeAttachment", back_populates="scheme", cascade="all, delete-orphan"
    )


class SchemeCondition(Base):
    """
    Each row here is ONE condition for a scheme.
    A scheme can have multiple conditions (all must match - AND logic).

    Examples of field_name: "brand_id", "category_id", "store_id",
                             "min_quantity", "min_value"
    Examples of operator:   "=", ">=", "<="
    """
    __tablename__ = "scheme_conditions"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    field_name = Column(String(50), nullable=False)
    operator = Column(String(10), nullable=False)
    value = Column(String(100), nullable=False)

    scheme = relationship("Scheme", back_populates="conditions")


class SchemeSlab(Base):
    """Used only when reward_type = 'Slab'.
    Example: sell 10+ units -> ₹50/unit, sell 20+ units -> ₹80/unit."""
    __tablename__ = "scheme_slabs"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    reward_per_unit = Column(Float, nullable=False)

    scheme = relationship("Scheme", back_populates="slabs")


# ============================================================
# SCHEME DOCUMENT ATTACHMENTS
# A brand promoter/manager attaches the scheme circular (image, PDF, or
# Excel) they received from the brand. Admin can view/download it. The
# file bytes are stored IN THE DATABASE rather than on disk, because
# Render's web-service filesystem is temporary (same reason this project
# already recommends PostgreSQL over SQLite in production - see README).
# Claude reads the document and pre-fills the linked Scheme's fields; the
# scheme is always created with status="Draft" so an Admin reviews and
# confirms it before it goes Active.
# ============================================================

class SchemeAttachment(Base):
    __tablename__ = "scheme_attachments"
    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, default=0)
    file_data = Column(LargeBinary, nullable=False)

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Pending -> Extracted / Failed / Skipped (no ANTHROPIC_API_KEY configured)
    extraction_status = Column(String(20), default="Pending", nullable=False)
    extraction_error = Column(String(500), nullable=True)
    extraction_raw_json = Column(Text, nullable=True)

    created_date = Column(DateTime, default=datetime.utcnow)

    scheme = relationship("Scheme", back_populates="attachments")


# ============================================================
# SALES TABLE (simplified - just enough to trigger the engine)
# ============================================================

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(50), unique=True, nullable=False)
    invoice_date = Column(Date, nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(Integer, ForeignKey("sub_categories.id"), nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=True)
    imei = Column(String(100), nullable=True)
    serial_no = Column(String(100), nullable=True)
    model_no = Column(String(100), nullable=True)
    customer_name = Column(String(150), nullable=True)
    product_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    sale_value = Column(Float, nullable=False)
    sale_value_exact = Column(String(40), nullable=True)
    gst = Column(Float, default=0)
    schemes = Column(String(50), nullable=True)
    schemes_other = Column(String(255), nullable=True)
    scheme_match = Column(String(20), nullable=True)
    scheme_match_other = Column(String(255), nullable=True)
    scheme_amount = Column(Float, default=0)
    scheme_amount_exact = Column(String(40), nullable=True)
    claim_status = Column(String(50), nullable=True)
    claim_status_other = Column(String(255), nullable=True)
    claim_overall_status = Column(String(50), nullable=True)
    settled_date = Column(Date, nullable=True)
    # "BACKEND & UPI" combined scheme: separate amount + claim tracking for
    # each half instead of one single scheme_amount/claim_status pair.
    upi_scheme_amount = Column(Float, nullable=True)
    upi_scheme_amount_exact = Column(String(40), nullable=True)
    upi_claim_status = Column(String(20), nullable=True)  # Pending / Settled
    backend_scheme_amount = Column(Float, nullable=True)
    backend_scheme_amount_exact = Column(String(40), nullable=True)
    backend_claim_type = Column(String(30), nullable=True)  # Automatic Claim / Mannual Claim
    backend_claim_status = Column(String(20), nullable=True)  # Pending / Settled
    sales_executive = Column(String(150), nullable=True)
    sale_date = Column(Date, nullable=False)


class IntervalSaleUpload(Base):
    __tablename__ = "interval_sales_uploads"
    id = Column(Integer, primary_key=True, index=True)
    sale_date = Column(Date, nullable=False, index=True)
    vch_no = Column(String(80), nullable=True, index=True)
    account = Column(String(200), nullable=True)
    item = Column(String(200), nullable=True, index=True)
    qty = Column(Float, default=0)
    unit = Column(String(50), nullable=True)
    sales_amt = Column(Float, default=0)
    cost_amt = Column(Float, default=0)
    profit_loss = Column(Float, default=0)
    profit_percent = Column(Float, default=0)
    source_file = Column(String(255), nullable=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================
# CLAIM TABLES
# ============================================================

class ClaimHeader(Base):
    __tablename__ = "claim_headers"
    id = Column(Integer, primary_key=True, index=True)
    claim_no = Column(String(50), nullable=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    invoice_no = Column(String(50), nullable=True)
    branch_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    claim_amount = Column(Float, nullable=False)
    status = Column(String(20), default="Draft")
    submission_date = Column(Date, nullable=True)
    approval_date = Column(Date, nullable=True)
    received_date = Column(Date, nullable=True)
    payment_amount = Column(Float, default=0)
    balance = Column(Float, default=0)
    remarks = Column(String(255), nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)

    history = relationship(
        "ClaimStatusHistory", back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimStatusHistory(Base):
    __tablename__ = "claim_status_history"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claim_headers.id"), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20))
    changed_date = Column(DateTime, default=datetime.utcnow)
    remarks = Column(String(255))

    claim = relationship("ClaimHeader", back_populates="history")


# ============================================================
# USERS & ROLE-BASED ACCESS
# ============================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150))

    # Role controls what this user can see/do.
    # Admin          - full access to everything
    # StoreManager   - limited to ONE assigned store
    # CategoryManager - limited to ONE assigned category
    # BrandManager   - limited to their assigned brand(s)
    # BrandPartner   - limited to their assigned brand(s) (e.g. brand promoter/partner)
    # Accounts       - can see all claims for payment reconciliation
    role = Column(String(30), nullable=False)

    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)  # used when role = StoreManager
    category_code = Column(String(20), nullable=True)  # used when role = CategoryManager
    status = Column(String(20), default="Active")
    created_date = Column(DateTime, default=datetime.utcnow)

    # Used for the email-verified "forgot password" flow. A reset link is
    # only valid if the token matches AND it hasn't expired.
    reset_token = Column(String(100), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

    brands = relationship("UserBrand", back_populates="user", cascade="all, delete-orphan")


class UserBrand(Base):
    """A user can be linked to MULTIPLE brands (used for BrandManager / BrandPartner roles)."""
    __tablename__ = "user_brands"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    user = relationship("User", back_populates="brands")


# ============================================================
# PURCHASE ORDER REQUESTS
# ============================================================

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    request_no = Column(String(50), unique=True, nullable=False, index=True)
    request_date = Column(Date, nullable=False)
    division = Column(String(50), nullable=True)
    branch_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    brand_name = Column(String(150), nullable=True)
    supplier_name = Column(String(200), nullable=True)
    supplier_email = Column(String(150), nullable=True)
    supplier_address = Column(String(500), nullable=True)
    supplier_gstin = Column(String(30), nullable=True)
    delivery_address = Column(String(255), nullable=True)
    remarks = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="Requested")
    busy_po_number = Column(String(80), nullable=True, unique=True)
    ordered_date = Column(Date, nullable=True)
    processing_notes = Column(String(500), nullable=True)
    exported_to_busy = Column(Boolean, default=False, nullable=False)
    exported_to_busy_at = Column(DateTime, nullable=True)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Admin approval gate: a Category Manager's request must be Approved by
    # an Admin before MIS is allowed to send it to the supplier / finalize it
    # as Ordered. Set when an Admin moves the status to "Approved".
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    submitted_by = relationship("User", foreign_keys=[submitted_by_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    model_no = Column(String(100), nullable=True)
    serial_no = Column(String(100), nullable=True)
    variant = Column(String(100), nullable=True)
    color = Column(String(80), nullable=True)
    hsn_code = Column(String(30), nullable=True)
    stock_balance = Column(Float, nullable=True)
    rate_of_sale = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    unit = Column(String(30), nullable=False, default="Nos")
    estimated_price = Column(Float, nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="items")


# ============================================================
# BRAND VISIBILITY PER DIVISION (for Purchase Order dropdowns)
# A brand's `subcategory_id` above is its primary home (used elsewhere for
# schemes/products) and brand names must stay unique, so a brand can't just
# get a second row for a second category. This table instead says "show this
# existing brand in the Procurement Details dropdown for this category too" —
# e.g. Samsung shows for both Home Entertainment and Mobiles/Handset.
# ============================================================

class BrandCategoryVisibility(Base):
    __tablename__ = "brand_category_visibility"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)



# ============================================================
# BRAND SUPPLIER EMAIL BOOK
# (Pre-fed contact emails per brand so Admin/MIS can send a PO to every
#  distributor contact for that brand in one click, and add more over time.)
# ============================================================

class BrandSupplierEmail(Base):
    __tablename__ = "brand_supplier_emails"
    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String(150), nullable=False, index=True)
    email = Column(String(150), nullable=False)


# ============================================================
# SUPPLIER PROFILE (per supplier name, not per brand)
# Once Admin/MIS types a supplier's address and GSTIN on any purchase
# order, it's remembered here and auto-filled next time the same supplier
# name is used on a different request. Emails are tracked separately in
# SupplierEmail so more than one contact can be saved per supplier.
# ============================================================

class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"
    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(200), unique=True, nullable=False, index=True)
    supplier_address = Column(String(500), nullable=True)
    supplier_gstin = Column(String(30), nullable=True)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SupplierEmail(Base):
    __tablename__ = "supplier_emails"
    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(200), nullable=False, index=True)
    email = Column(String(150), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)