"""Receipt matching and verification for sent purchase orders."""
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(dependencies=[Depends(auth.require_purchase_order_access)])
WAREHOUSE_ROLES = {"LogisticManager", "Supervisor"}
VERIFIERS = {"Accounts", "MISExecutive"} | WAREHOUSE_ROLES
OUTLET_MANAGER_ROLES = {"AsstSalesManager", "StoreManager", "Branch Manager"}
RECEIPT_OPERATORS = {"Admin", "Owner", "MISExecutive"} | VERIFIERS


def can_verify(user, order=None):
    if user.role in VERIFIERS:
        return True
    if user.role not in OUTLET_MANAGER_ROLES or user.store_id is None:
        return False
    if order is None:
        return True
    receipts = [receipt for receipt in order.receipts if not receipt.voided_at]
    return bool(receipts) and all(receipt.store_id == user.store_id for receipt in receipts)


@router.get("/api/po-receiving-options")
def receiving_options(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    locations = []
    if can_receive(user):
        stores = db.query(models.Store).filter(models.Store.status == "Active")
        if user.role in RECEIPT_OPERATORS:
            locations.append({"id": None, "name": "Warehouse"})
        else:
            stores = stores.filter(models.Store.id == user.store_id)
        locations.extend({"id": store.id, "name": store.name} for store in stores.all())
    return {"can_receive": can_receive(user), "can_verify": can_verify(user),
            "verification_store_id": user.store_id if user.role in OUTLET_MANAGER_ROLES else None,
            "user_id": user.id, "locations": locations}


def can_receive(user):
    return user.role != "BrandPartner" and (
        user.role in RECEIPT_OPERATORS or user.store_id is not None
    )


def receipt_summary(order):
    totals = {item.id: 0 for item in order.items}
    receipts = []
    for receipt in order.receipts:
        for line in receipt.lines:
            if not receipt.voided_at:
                totals[line.purchase_order_item_id] = totals.get(line.purchase_order_item_id, 0) + line.quantity
        receipts.append({
            "id": receipt.id, "location_name": receipt.location_name, "store_id": receipt.store_id,
            "document_number": receipt.document_number,
            "received_date": receipt.received_date,
            "received_by": receipt.received_by.username if receipt.received_by else "Deleted user",
            "received_by_user_id": receipt.received_by_user_id,
            "created_at": receipt.created_at, "notes": receipt.notes,
            "voided_at": receipt.voided_at,
            "lines": [{"item_id": line.purchase_order_item_id, "quantity": line.quantity} for line in receipt.lines],
        })
    matching = [{"item_id": item.id, "product_name": item.product_name,
                 "model_no": item.model_no, "variant": item.variant, "unit": item.unit,
                 "ordered": item.quantity, "received": totals[item.id],
                 "difference": totals[item.id] - item.quantity} for item in order.items]
    matched = bool(matching) and all(line["difference"] == 0 for line in matching)
    active = any(not receipt.voided_at for receipt in order.receipts)
    stage = ("Completed" if order.verified_at else "Awaiting verification" if active and matched
             else "Receipt mismatch" if active else "Sent — awaiting receipt" if order.email_sent_at
             else "Not sent")
    return {"stage": stage, "matched": matched, "matching": matching, "receipts": receipts,
            "verified_at": order.verified_at,
            "verified_by": order.verified_by.username if order.verified_by else None}


class ReceiptLineInput(BaseModel):
    item_id: int
    quantity: int = Field(ge=0, strict=True)


class ReceiptInput(BaseModel):
    store_id: Optional[int] = None  # null denotes the warehouse
    document_number: str = Field(min_length=1, max_length=100)
    received_date: date
    notes: str = Field(default="", max_length=500)
    lines: List[ReceiptLineInput] = Field(min_length=1)


def locked_order(db, order_id):
    # UPDATE serializes receipt, void and verification mutations on SQLite and PostgreSQL.
    changed = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == order_id).update(
        {models.PurchaseOrder.updated_date: datetime.utcnow()}, synchronize_session=False)
    if not changed:
        raise HTTPException(404, "Purchase order not found")
    db.expire_all()
    order = db.get(models.PurchaseOrder, order_id)
    if not order.email_sent_at or order.status in {"Rejected", "Cancelled"}:
        raise HTTPException(400, "Only a sent, active PO can receive stock or be verified")
    if order.verified_at:
        raise HTTPException(409, "This PO has been verified and completed")
    return order


@router.post("/api/purchase-orders/{order_id}/receipts")
def receive_order(order_id: int, payload: ReceiptInput, db: Session = Depends(get_db),
                  user: models.User = Depends(auth.get_current_user)):
    if not can_receive(user):
        raise HTTPException(403, "Warehouse logistics staff or staff assigned to an outlet can enter receipts")
    if user.role not in RECEIPT_OPERATORS and payload.store_id != user.store_id:
        raise HTTPException(403, "Enter receipts only for your assigned outlet")
    if payload.store_id is None:
        if user.role not in RECEIPT_OPERATORS:
            raise HTTPException(403, "Warehouse receipt entry requires a logistics role")
        location = "Warehouse"
    else:
        store = db.get(models.Store, payload.store_id)
        if not store or store.status != "Active":
            raise HTTPException(400, "Select an active receiving outlet")
        location = store.name
    if not payload.document_number.strip():
        raise HTTPException(400, "Enter the delivery challan or invoice number")
    if payload.received_date > date.today():
        raise HTTPException(400, "Receipt date cannot be in the future")
    order = locked_order(db, order_id)
    if payload.received_date < order.request_date:
        raise HTTPException(400, "Receipt date cannot precede the PO date")
    valid_ids = {item.id for item in order.items}
    ids = [line.item_id for line in payload.lines]
    if len(ids) != len(set(ids)) or not set(ids).issubset(valid_ids):
        raise HTTPException(400, "Receipt items must be unique and belong to this PO")
    if not any(line.quantity > 0 for line in payload.lines):
        raise HTTPException(400, "Enter at least one received quantity")
    if any(not r.voided_at and r.store_id == payload.store_id and
           r.document_number.casefold() == payload.document_number.strip().casefold() for r in order.receipts):
        raise HTTPException(409, "This document is already recorded for this PO and location")
    receipt = models.PurchaseOrderReceipt(
        purchase_order=order, store_id=payload.store_id, location_name=location,
        document_number=payload.document_number.strip(), received_date=payload.received_date,
        notes=payload.notes.strip(), received_by_user_id=user.id,
        lines=[models.PurchaseOrderReceiptLine(purchase_order_item_id=line.item_id, quantity=line.quantity)
               for line in payload.lines if line.quantity > 0])
    db.add(receipt)
    db.commit()
    return receipt_summary(order)


@router.post("/api/purchase-orders/{order_id}/receipts/{receipt_id}/void")
def void_receipt(order_id: int, receipt_id: int, db: Session = Depends(get_db),
                 user: models.User = Depends(auth.get_current_user)):
    order = locked_order(db, order_id)
    receipt = next((r for r in order.receipts if r.id == receipt_id), None)
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    manages_receipt = (user.role in VERIFIERS or
                       (can_verify(user) and receipt.store_id == user.store_id))
    if not manages_receipt and receipt.received_by_user_id != user.id:
        raise HTTPException(403, "Only the receipt author or a verifier can void this entry")
    if receipt.voided_at:
        raise HTTPException(409, "Receipt already voided")
    receipt.voided_at = datetime.utcnow()
    receipt.voided_by_user_id = user.id
    db.commit()
    return receipt_summary(order)


@router.post("/api/purchase-orders/{order_id}/verify")
def verify_order(order_id: int, db: Session = Depends(get_db),
                 user: models.User = Depends(auth.get_current_user)):
    if not can_verify(user):
        raise HTTPException(403, "Only Accounts, MIS Executive, warehouse staff or an assigned outlet manager can verify a PO")
    order = locked_order(db, order_id)
    if not can_verify(user, order):
        raise HTTPException(403, "Outlet managers can verify only receipts at their assigned outlet. Accounts or warehouse staff must verify mixed-location POs.")
    if not receipt_summary(order)["matched"] or not any(not r.voided_at for r in order.receipts):
        raise HTTPException(409, "Received quantities must exactly match every sent PO item before verification")
    order.verified_at = datetime.utcnow()
    order.verified_by_user_id = user.id
    db.commit()
    return receipt_summary(order)
