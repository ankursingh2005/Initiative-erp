"""Identity card data is separate from account permissions and login details."""
import base64
import re
import warnings
from io import BytesIO
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import update, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(prefix="/api/identity-cards", tags=["Identity cards"])
MANAGERS = {"Admin", "Owner", "HR"}
OUTLET_ABBREVIATIONS = {
    "hazratganj": "HZT", "alambagh": "ALM", "ashiyana": "ASH",
    "gomtinagar": "GNG", "gomti nagar": "GNG", "vikas nagar": "VKN",
    "vikasnagar": "VKN", "warehouse": "WH", "head office": "HO",
    "head-office": "HO",
}


def outlet_abbreviation(store):
    if store is None:
        return ""
    known = OUTLET_ABBREVIATIONS.get(store.name.strip().lower())
    if known:
        return known
    return re.sub(r"[^A-Z0-9]", "", (store.code or "").upper())[:15] or f"OUT{store.id}"


def issue_year():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%y")


def next_employee_id(db, abbreviation):
    """Atomically reserve a serial. Counters survive employee deletion."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as postgres_insert
    prefix = f"IDS-{abbreviation + '-' if abbreviation else ''}{issue_year()}"
    insert = postgres_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(models.IdentityCardSequence).values(prefix=prefix, last_number=0)
               .on_conflict_do_nothing(index_elements=["prefix"]))
    # Also respect IDs already present when adopting the new counter table.
    ids = db.scalars(select(models.IdentityCard.employee_id).where(
        models.IdentityCard.employee_id.startswith(prefix))).all()
    largest = max([int(value[len(prefix):]) for value in ids
                   if value[len(prefix):].isdigit()] or [0])
    db.execute(update(models.IdentityCardSequence).where(
        models.IdentityCardSequence.prefix == prefix,
        models.IdentityCardSequence.last_number < largest).values(last_number=largest))
    number = db.scalar(update(models.IdentityCardSequence).where(
        models.IdentityCardSequence.prefix == prefix).values(
            last_number=models.IdentityCardSequence.last_number + 1
        ).returning(models.IdentityCardSequence.last_number))
    return f"{prefix}{number:03d}"


def assign_employee_id(db, user):
    """Assign a missing ID in the caller's transaction for every account role."""
    card = db.get(models.IdentityCard, user.id)
    if card is not None:
        return card
    store = db.get(models.Store, user.store_id) if user.store_id else None
    card = models.IdentityCard(
        user_id=user.id, employee_id=next_employee_id(db, outlet_abbreviation(store)),
        employee_name=user.full_name or user.username,
        designation=re.sub(r"(?<=[a-z])(?=[A-Z])", " ", user.role), mobile="")
    db.add(card)
    db.flush()
    return card


def ensure_employee_ids(db):
    """Assign stable IDs and migrate legacy IDs without touching card corrections."""
    for attempt in range(3):
        try:
            rows = (db.query(models.User, models.IdentityCard, models.Store)
                    .outerjoin(models.IdentityCard, models.IdentityCard.user_id == models.User.id)
                    .outerjoin(models.Store, models.Store.id == models.User.store_id)
                    .order_by(models.User.id).all())
            changed = False
            for user, card, store in rows:
                abbreviation = outlet_abbreviation(store)
                # A year rollover does not renumber a card. Outlet transfers do.
                prefix = f"IDS-{abbreviation + '-' if abbreviation else ''}"
                if card and re.fullmatch(rf"{re.escape(prefix)}\d{{2}}\d{{3,}}", card.employee_id):
                    continue
                number = next_employee_id(db, abbreviation)
                if card is None:
                    card = models.IdentityCard(user_id=user.id, employee_name=user.full_name or user.username,
                                              designation=re.sub(r"(?<=[a-z])(?=[A-Z])", " ", user.role), mobile="")
                    db.add(card)
                card.employee_id = number
                db.flush()
                changed = True
            if changed:
                db.commit()
            return
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Employee IDs are being assigned. Please refresh and retry.")


class CardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str | None = Field(default=None, min_length=1, max_length=40)
    employee_name: str = Field(min_length=1, max_length=150)
    designation: str = Field(min_length=1, max_length=100)
    mobile: str = Field(default="", max_length=25)
    joining_date: date | None = None
    photo: str | None = Field(default=None, max_length=4_000_000)

    @field_validator("employee_id", "employee_name", "designation", "mobile")
    @classmethod
    def clean_text(cls, value, info):
        if value is None:
            return value
        value = value.strip()
        if info.field_name != "mobile" and not value:
            raise ValueError("This field is required")
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        if info.field_name == "employee_id":
            value = value.upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,39}", value):
                raise ValueError("Use letters, numbers, dots, slashes, or hyphens for employee ID")
        if info.field_name == "mobile" and value:
            if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(re.sub(r"\D", "", value)) <= 15:
                raise ValueError("Enter a valid mobile number with 7 to 15 digits")
        return value


def eligible(user):
    if user.role == "BrandPartner":
        raise HTTPException(403, "Identity cards are not available for Brand Promoters")


def normalize_photo(value):
    if value is None:
        return None
    try:
        header, encoded = value.split(",", 1)
        if header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}:
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 3_000_000:
            raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.width * source.height > 16_000_000:
                    raise ValueError()
                photo = ImageOps.exif_transpose(source).convert("RGB")
                photo = ImageOps.fit(photo, (480, 480), method=Image.Resampling.LANCZOS)
                output = BytesIO()
                photo.save(output, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Upload a valid JPG, PNG, or WebP photo, up to 3 MB and 16 megapixels")


def serialize(user, card, store):
    return {
        "user_id": user.id,
        "employee_id": card.employee_id if card else "",
        "employee_name": card.employee_name if card else (user.full_name or user.username),
        "designation": card.designation if card else re.sub(r"(?<=[a-z])(?=[A-Z])", " ", user.role),
        "mobile": card.mobile if card else "",
        "joining_date": card.joining_date.isoformat() if card and card.joining_date else None,
        "photo": card.photo if card else None,
        "role": user.role,
        "status": user.status,
        "outlet": store.name if store else "Unassigned",
        "saved": card is not None,
    }


class AttendanceProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=150)
    mobile: str = Field(default="", max_length=25)
    photo: str | None = Field(default=None, max_length=4_000_000)


@router.patch("/profile/{user_id}")
def update_attendance_profile(user_id: int, payload: AttendanceProfileUpdate,
                              db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    if current_user.id != user_id and current_user.role not in MANAGERS:
        raise HTTPException(403, "You can only edit your own profile")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    name, mobile = payload.name.strip(), payload.mobile.strip()
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address")
    from sqlalchemy import func
    if db.query(models.User).filter(func.lower(models.User.email) == email, models.User.id != user_id).first():
        raise HTTPException(409, "Email is already used by another account")
    if not name or any(ord(c) < 32 for c in name):
        raise HTTPException(422, "Enter a valid name")
    if mobile and (not re.fullmatch(r"\+?[0-9 ()-]+", mobile) or not 7 <= len(re.sub(r"\D", "", mobile)) <= 15):
        raise HTTPException(422, "Enter a valid contact number")
    photo = normalize_photo(payload.photo) if "photo" in payload.model_fields_set else None
    card = db.get(models.IdentityCard, user_id)
    if not card:
        store = db.get(models.Store, user.store_id) if user.store_id else None
        card = models.IdentityCard(user_id=user_id, employee_id=next_employee_id(db, outlet_abbreviation(store)),
                                   employee_name=name, designation=user.role, mobile=mobile)
        db.add(card)
    card.employee_name, card.mobile = name, mobile
    user.full_name = name
    if user.email != email:
        user.email = email
        user.reset_token = None
    if "photo" in payload.model_fields_set:
        card.photo = photo
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email or employee ID is already in use. Reload and try again.")
    return {"name": name, "email": user.email, "contact_number": mobile, "profile_photo": card.photo, "employee_id": card.employee_id}


@router.get("")
def list_cards(response: Response, db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    eligible(current_user)
    response.headers["Cache-Control"] = "no-store"
    ensure_employee_ids(db)
    query = (db.query(models.User, models.IdentityCard, models.Store)
             .outerjoin(models.IdentityCard, models.IdentityCard.user_id == models.User.id)
             .outerjoin(models.Store, models.Store.id == models.User.store_id)
             .filter(models.User.role != "BrandPartner"))
    if current_user.role not in MANAGERS:
        query = query.filter(models.User.id == current_user.id)
    return {"can_edit": current_user.role in MANAGERS,
            "cards": [serialize(*row) for row in query.order_by(models.User.full_name, models.User.username).all()]}


@router.put("/{user_id}")
def save_card(user_id: int, payload: CardUpdate, response: Response,
              db: Session = Depends(get_db), current_user=Depends(auth.get_current_user)):
    eligible(current_user)
    if current_user.role not in MANAGERS:
        raise HTTPException(403, "Only Admin, Owner, and HR can correct identity cards")
    user = db.get(models.User, user_id)
    if not user or user.role == "BrandPartner":
        raise HTTPException(404, "Eligible user not found")
    if "photo" in payload.model_fields_set:
        normalized_photo = normalize_photo(payload.photo)
    ensure_employee_ids(db)
    card = db.get(models.IdentityCard, user_id)
    if payload.employee_id is not None and payload.employee_id != card.employee_id:
        raise HTTPException(409, "Employee ID is generated from the outlet. Reload the card to use its assigned ID.")
    photo = normalized_photo if "photo" in payload.model_fields_set else card.photo
    for name in ("employee_name", "designation", "mobile"):
        setattr(card, name, getattr(payload, name))
    card.photo = photo
    if "joining_date" in payload.model_fields_set:
        card.joining_date = payload.joining_date
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Employee ID is already assigned. Reload and try again.")
    db.refresh(card)
    response.headers["Cache-Control"] = "no-store"
    return serialize(user, card, db.get(models.Store, user.store_id) if user.store_id else None)
