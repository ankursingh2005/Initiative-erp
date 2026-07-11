from typing import List
from sqlalchemy.orm import Session
import models


def _compare(actual, op, value):
    if op == ">=":
        return actual >= value
    if op == "<=":
        return actual <= value
    if op == "=":
        return actual == value
    return False


def _condition_matches(sale: models.Sale, condition: models.SchemeCondition) -> bool:
    field = condition.field_name
    op = condition.operator
    value = condition.value

    if field == "brand_id":
        return _compare(sale.brand_id, op, int(value))
    if field == "category_id":
        return _compare(sale.category_id, op, int(value))
    if field == "subcategory_id":
        return _compare(sale.subcategory_id, op, int(value)) if sale.subcategory_id is not None else False
    if field == "product_id":
        return _compare(sale.product_id, op, int(value)) if sale.product_id is not None else False
    if field == "variant_id":
        return _compare(sale.variant_id, op, int(value)) if sale.variant_id is not None else False
    if field == "store_id":
        return _compare(sale.store_id, op, int(value))
    if field == "min_quantity":
        return _compare(sale.quantity, op, int(value))
    if field == "min_value":
        return _compare(sale.sale_value, op, float(value))
    if field == "customer_name":
        return _compare((sale.customer_name or "").lower(), "=", value.lower())
    return False


def _calculate_reward(scheme: models.Scheme, sale: models.Sale) -> float:
    if scheme.reward_type == "Fixed":
        return float(scheme.reward_value)

    if scheme.reward_type == "Percentage":
        return round(sale.sale_value * (scheme.reward_value / 100), 2)

    if scheme.reward_type == "Slab":
        applicable_slabs = [s for s in scheme.slabs if sale.quantity >= s.min_quantity]
        if not applicable_slabs:
            return 0
        best_slab = max(applicable_slabs, key=lambda s: s.min_quantity)
        return round(best_slab.reward_per_unit * sale.quantity, 2)

    return 0


def evaluate_sale_against_schemes(db: Session, sale: models.Sale) -> List[dict]:
    active_schemes = (
        db.query(models.Scheme)
        .filter(models.Scheme.status == "Active")
        .filter(models.Scheme.start_date <= sale.sale_date)
        .filter(models.Scheme.end_date >= sale.sale_date)
        .all()
    )

    created_claims = []

    for scheme in active_schemes:
        if not all(_condition_matches(sale, cond) for cond in scheme.conditions):
            continue

        amount = _calculate_reward(scheme, sale)
        if amount <= 0:
            continue

        existing = (
            db.query(models.ClaimHeader)
            .filter(models.ClaimHeader.scheme_id == scheme.id)
            .filter(models.ClaimHeader.sale_id == sale.id)
            .first()
        )
        if existing:
            continue

        claim = models.ClaimHeader(
            scheme_id=scheme.id,
            sale_id=sale.id,
            claim_amount=amount,
            status="Draft",
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)

        history = models.ClaimStatusHistory(
            claim_id=claim.id,
            old_status=None,
            new_status="Draft",
            remarks="Auto-created by scheme engine",
        )
        db.add(history)
        db.commit()

        created_claims.append({"scheme_id": scheme.id, "claim_amount": amount})

    return created_claims
