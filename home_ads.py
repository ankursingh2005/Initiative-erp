"""Permanent home advertisement, including media stored in the database."""
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, defer
import auth
import models
from database import get_db

router = APIRouter(prefix="/api/home-ad", tags=["Home advertisement"])
MAX_MEDIA = 50 * 1024 * 1024
MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif", "video/mp4", "video/webm", "video/ogg", "video/quicktime"}
AD_EDITOR_ROLES = {"Admin", "HR"}


def admin(user=Depends(auth.get_current_user)):
    if user.role not in AD_EDITOR_ROLES:
        raise HTTPException(403, "Only Admin and HR can manage advertisements")
    return user


def state(db):
    return db.query(models.HomeAdvertisement).options(defer(models.HomeAdvertisement.media)).filter_by(id=1).first()


def serialize(ad):
    return {"title": ad.title if ad else "", "message": ad.message if ad else "",
            "visible": bool(ad and ad.visible), "media_type": ad.media_type if ad else None,
            "version": ad.version if ad else None}


@router.get("")
def read_ad(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    ad = state(db)
    return serialize(ad if user.role in AD_EDITOR_ROLES or (ad and ad.visible) else None)


@router.put("")
async def save_ad(title: str = Form(""), message: str = Form(""), visible: bool = Form(True),
                  remove_media: bool = Form(False), media: UploadFile | None = File(None),
                  db: Session = Depends(get_db), user=Depends(admin)):
    title, message = title.strip(), message.strip()
    if len(title) > 160 or len(message) > 4000:
        raise HTTPException(422, "Title limit is 160 characters; message limit is 4,000 characters")
    data = None
    if media:
        if media.content_type not in MEDIA_TYPES:
            raise HTTPException(422, "Choose a supported image or video")
        data = await media.read(MAX_MEDIA + 1)
        if not data or len(data) > MAX_MEDIA:
            raise HTTPException(422, "Upload a non-empty file up to 50 MB")
    ad = state(db)
    if not ad:
        ad = models.HomeAdvertisement(id=1)
        db.add(ad)
    if remove_media:
        ad.media, ad.media_type = None, None
    if media:
        ad.media, ad.media_type = data, media.content_type
    if not (title or message or ad.media_type):
        raise HTTPException(422, "Add text, an image or a video before saving")
    ad.title, ad.message, ad.visible, ad.version = title, message, visible, uuid4().hex
    db.commit()
    return serialize(ad)


@router.patch("/visibility")
def visibility(visible: bool = Form(...), db: Session = Depends(get_db), user=Depends(admin)):
    ad = state(db)
    if not ad or not (ad.title or ad.message or ad.media_type):
        raise HTTPException(422, "Save an advertisement first")
    ad.visible = visible
    db.commit()
    return serialize(ad)


@router.delete("")
def clear_ad(db: Session = Depends(get_db), user=Depends(admin)):
    ad = state(db)
    if ad:
        db.delete(ad)
        db.commit()
    return serialize(None)


@router.get("/media")
def read_media(db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    ad = state(db)
    if not ad or not ad.media_type or (not ad.visible and user.role not in AD_EDITOR_ROLES):
        raise HTTPException(404, "No advertisement media")
    return Response(ad.media, media_type=ad.media_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
