from pydantic import BaseModel
from pydantic import validator
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP


class CategoryCreate(BaseModel):
    code: str
    name: str


class CategoryOut(CategoryCreate):
    id: int

    class Config:
        from_attributes = True


class SubCategoryCreate(BaseModel):
    category_id: int
    name: str


class SubCategoryOut(SubCategoryCreate):
    id: int

    class Config:
        from_attributes = True


class BrandCreate(BaseModel):
    name: str
    subcategory_id: Optional[int] = None


class BrandOut(BrandCreate):
    id: int

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    brand_id: int
    name: str


class ProductOut(ProductCreate):
    id: int

    class Config:
        from_attributes = True


class VariantCreate(BaseModel):
    product_id: int
    name: str


class VariantOut(VariantCreate):
    id: int

    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    city: Optional[str] = None


class CustomerOut(CustomerCreate):
    id: int

    class Config:
        from_attributes = True


class DealerCreate(BaseModel):
    name: str
    city: Optional[str] = None
    contact: Optional[str] = None


class DealerOut(DealerCreate):
    id: int

    class Config:
        from_attributes = True


class StoreCreate(BaseModel):
    name: str
    code: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = "Active"


class StoreOut(StoreCreate):
    id: int

    class Config:
        from_attributes = True


class SchemeConditionCreate(BaseModel):
    field_name: str
    operator: str
    value: str


class SchemeSlabCreate(BaseModel):
    min_quantity: int
    reward_per_unit: float


class SchemeCreate(BaseModel):
    scheme_code: str
    scheme_name: str
    brand_id: Optional[int] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    offer_type: str = "Backend"
    offer_value: float = 0
    calculation_method: str = "Fixed Amount"
    start_date: date
    end_date: date
    min_qty: int = 0
    max_qty: Optional[int] = None
    applicable_branch_id: Optional[int] = None
    applicable_customer: Optional[str] = None
    applicable_dealer: Optional[str] = None
    status: str = "Active"
    circular_number: Optional[str] = None
    remarks: Optional[str] = None
    reward_type: str = "Fixed"
    reward_value: float = 0
    conditions: List[SchemeConditionCreate] = []
    slabs: List[SchemeSlabCreate] = []


class SchemeOut(BaseModel):
    id: int
    scheme_code: str
    scheme_name: str
    brand_id: Optional[int]
    category_id: Optional[int]
    subcategory_id: Optional[int]
    product_id: Optional[int]
    variant_id: Optional[int]
    offer_type: str
    offer_value: float
    calculation_method: str
    start_date: date
    end_date: date
    min_qty: int
    max_qty: Optional[int]
    applicable_branch_id: Optional[int]
    applicable_customer: Optional[str]
    applicable_dealer: Optional[str]
    status: str
    circular_number: Optional[str]
    remarks: Optional[str]
    reward_type: str
    reward_value: float

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    invoice_no: str
    invoice_date: Optional[date] = None
    store_id: int
    category_id: int
    subcategory_id: Optional[int] = None
    brand_id: int
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    imei: Optional[str] = None
    serial_no: Optional[str] = None
    model_no: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: str
    quantity: int
    sale_value: float
    sale_value_exact: Optional[str] = None
    gst: float = 0
    schemes: Optional[str] = None
    schemes_other: Optional[str] = None
    scheme_match: Optional[str] = None
    scheme_match_other: Optional[str] = None
    scheme_amount: Optional[float] = 0
    scheme_amount_exact: Optional[str] = None
    claim_status: Optional[str] = None
    claim_status_other: Optional[str] = None
    claim_overall_status: Optional[str] = None
    settled_date: Optional[date] = None
    sales_executive: Optional[str] = None
    sale_date: date

    @validator("sale_value", pre=True, always=True)
    def normalize_sale_value(cls, value):
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @validator("scheme_amount", pre=True, always=True)
    def normalize_scheme_amount(cls, value):
        if value is None:
            return None
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class SaleOut(SaleCreate):
    id: int

    class Config:
        from_attributes = True


class ClaimOut(BaseModel):
    id: int
    claim_no: Optional[str]
    scheme_id: int
    sale_id: int
    brand_id: Optional[int]
    invoice_no: Optional[str]
    branch_id: Optional[int]
    claim_amount: float
    status: str
    submission_date: Optional[date]
    approval_date: Optional[date]
    received_date: Optional[date]
    payment_amount: float
    balance: float
    remarks: Optional[str]
    created_date: datetime

    class Config:
        from_attributes = True


class ClaimStatusUpdate(BaseModel):
    new_status: str
    remarks: Optional[str] = None


class UserSignup(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: str
    store_id: Optional[int] = None
    category_code: Optional[str] = None
    brand_ids: List[int] = []


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    store_id: Optional[int]
    category_code: Optional[str]
    status: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class ForgotPasswordRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    new_password: str
    confirm_password: str


class PurchaseOrderItemCreate(BaseModel):
    product_name: str
    model_no: Optional[str] = None
    serial_no: Optional[str] = None
    variant: Optional[str] = None
    color: Optional[str] = None
    hsn_code: Optional[str] = None
    stock_balance: Optional[float] = None
    rate_of_sale: Optional[float] = None
    quantity: int
    unit: str = "Nos"
    estimated_price: Optional[float] = None


class PurchaseOrderCreate(BaseModel):
    request_date: date
    division: Optional[str] = None
    branch_id: Optional[int] = None
    brand_name: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_email: Optional[str] = None
    delivery_address: Optional[str] = None
    remarks: Optional[str] = None
    items: List[PurchaseOrderItemCreate]


class PurchaseOrderStatusUpdate(BaseModel):
    status: str
    busy_po_number: Optional[str] = None
    ordered_date: Optional[date] = None
    processing_notes: Optional[str] = None


class PurchaseOrderItemOut(PurchaseOrderItemCreate):
    id: int

    class Config:
        from_attributes = True


class PurchaseOrderOut(BaseModel):
    id: int
    request_no: str
    request_date: date
    division: Optional[str]
    branch_id: Optional[int]
    brand_name: Optional[str]
    supplier_name: Optional[str]
    supplier_email: Optional[str]
    delivery_address: Optional[str]
    remarks: Optional[str]
    status: str
    busy_po_number: Optional[str]
    ordered_date: Optional[date]
    processing_notes: Optional[str]
    submitted_by_user_id: int
    submitted_by_username: Optional[str] = None
    notification_status: Optional[str] = None
    created_date: datetime
    updated_date: datetime
    items: List[PurchaseOrderItemOut]
