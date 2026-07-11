from pydantic import BaseModel
from datetime import date, datetime
from typing import List, Optional


# ============================================================
# MASTERS
# ============================================================

class BrandCreate(BaseModel):
    name: str


class BrandOut(BrandCreate):
    id: int

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str


class CategoryOut(CategoryCreate):
    id: int

    class Config:
        from_attributes = True


class StoreCreate(BaseModel):
    name: str


class StoreOut(StoreCreate):
    id: int

    class Config:
        from_attributes = True


# ============================================================
# SCHEME
# ============================================================

class SchemeConditionCreate(BaseModel):
    field_name: str   # "brand_id", "category_id", "store_id", "min_quantity", "min_value"
    operator: str     # "=", ">=", "<="
    value: str


class SchemeSlabCreate(BaseModel):
    min_quantity: int
    reward_per_unit: float


class SchemeCreate(BaseModel):
    scheme_code: str
    scheme_name: str
    start_date: date
    end_date: date
    reward_type: str          # "Fixed", "Percentage", "Slab"
    reward_value: float = 0
    conditions: List[SchemeConditionCreate] = []
    slabs: List[SchemeSlabCreate] = []


class SchemeOut(BaseModel):
    id: int
    scheme_code: str
    scheme_name: str
    start_date: date
    end_date: date
    status: str
    reward_type: str
    reward_value: float

    class Config:
        from_attributes = True


# ============================================================
# SALES
# ============================================================

class SaleCreate(BaseModel):
    invoice_no: str
    store_id: int
    brand_id: int
    category_id: int
    product_name: str
    quantity: int
    sale_value: float
    sale_date: date


class SaleOut(SaleCreate):
    id: int

    class Config:
        from_attributes = True


# ============================================================
# CLAIMS
# ============================================================

class ClaimOut(BaseModel):
    id: int
    scheme_id: int
    sale_id: int
    claim_amount: float
    status: str
    created_date: datetime

    class Config:
        from_attributes = True


class ClaimStatusUpdate(BaseModel):
    new_status: str
    remarks: Optional[str] = None