"""Email account recovery; delivery is invoked only by a reset request."""
import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from fastapi import HTTPException
from sqlalchemy import func

import auth
import models
from po_email import send_gmail


REQUEST_MESSAGE = {"message": "If this email belongs to an active account, a code has been sent. Check Spam too. Wait 60 seconds before retrying; maximum 5 requests per hour."}
INVALID_CODE = "The verification code is invalid, expired, or has reached its attempt limit. Request a new code."


def email_provider():
    # Reuse an explicitly selected PO sender unless recovery overrides it.
    provider = os.getenv("PASSWORD_RESET_EMAIL_PROVIDER", os.getenv("PO_EMAIL_PROVIDER", "smtp")).strip().lower()
    required = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER") if provider == "gmail" else ("SMTP_PASSWORD",)
    if provider not in {"gmail", "smtp"} or not all(os.getenv(key, "").strip() for key in required):
        raise HTTPException(503, "Password reset email is unavailable. Please contact your Admin.")
    return provider


def request_reset(payload, db):
    provider = email_provider()
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.identifier.strip().lower(), models.User.status == "Active").first()
    if not user:
        return REQUEST_MESSAGE
    now = datetime.utcnow()
    if user.reset_requested_at and now - user.reset_requested_at < timedelta(seconds=60):
        return REQUEST_MESSAGE
    fresh_window = not user.reset_request_window or now - user.reset_request_window >= timedelta(hours=1)
    if not fresh_window and (user.reset_request_count or 0) >= 5:
        return REQUEST_MESSAGE
    code = f"{secrets.randbelow(1_000_000):06d}"
    token = hashlib.sha256(code.encode()).hexdigest()
    user_id = user.id
    # Compare-and-set reserves the send once, including across app workers.
    reserved = db.query(models.User).filter(models.User.id == user_id, models.User.status == "Active", models.User.reset_requested_at == user.reset_requested_at).update({
        models.User.reset_requested_at: now,
        models.User.reset_request_window: now if fresh_window else user.reset_request_window,
        models.User.reset_request_count: 1 if fresh_window else (user.reset_request_count or 0) + 1,
        models.User.reset_attempts: 0,
        models.User.reset_token: token,
        models.User.reset_token_expires: now + timedelta(minutes=15),
    }, synchronize_session=False)
    recipient = user.email
    db.commit()
    if not reserved:
        return REQUEST_MESSAGE
    message = MIMEText(f"Your Initiative ERP password reset code is: {code}\n\nThis code expires in 15 minutes. If you did not request it, ignore this email.")
    message["Subject"] = "Initiative ERP password reset code"
    message["To"] = recipient
    try:
        if provider == "gmail":
            if send_gmail(message) != "Accepted by Gmail for sending.":
                raise RuntimeError("Email provider did not confirm acceptance")
        else:
            message["From"] = os.getenv("SMTP_FROM", "initiative.lucknow@gmail.com")
            with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER", "initiative.lucknow@gmail.com"), os.environ["SMTP_PASSWORD"])
                server.send_message(message)
    except Exception:
        db.query(models.User).filter(models.User.id == user_id, models.User.reset_token == token).update({models.User.reset_token: None, models.User.reset_token_expires: None}, synchronize_session=False)
        db.commit()
        raise HTTPException(503, "Unable to send the reset email. Please try again later or contact your Admin.")
    return REQUEST_MESSAGE


def confirm_reset(payload, db):
    if len(payload.new_password) < 8 or len(payload.new_password.encode("utf-8")) > 72:
        raise HTTPException(400, "Password must contain at least 8 characters and no more than 72 UTF-8 bytes.")
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.identifier.strip().lower(), models.User.status == "Active").first()
    now = datetime.utcnow()
    if not user or not user.reset_token or not user.reset_token_expires or user.reset_token_expires <= now:
        raise HTTPException(400, INVALID_CODE)
    token = user.reset_token
    user_id = user.id
    # Atomically reserve an attempt so concurrent guesses cannot bypass five.
    challenge = db.query(models.User).filter(models.User.id == user_id, models.User.status == "Active", models.User.reset_token == token, models.User.reset_token_expires > now)
    attempted = challenge.filter(func.coalesce(models.User.reset_attempts, 0) < 5).update({models.User.reset_attempts: func.coalesce(models.User.reset_attempts, 0) + 1}, synchronize_session=False)
    db.commit()
    if not attempted or not secrets.compare_digest(token, hashlib.sha256(payload.code.strip().encode()).hexdigest()):
        raise HTTPException(400, INVALID_CODE)
    password_hash = auth.hash_password(payload.new_password)
    # Consume once; an old request cannot overwrite a newer reset or admin reset.
    changed = challenge.filter(models.User.reset_token_expires > datetime.utcnow()).update({models.User.password_hash: password_hash, models.User.reset_token: None, models.User.reset_token_expires: None}, synchronize_session=False)
    db.commit()
    if not changed:
        raise HTTPException(400, INVALID_CODE)
    return {"message": "Password reset successfully. You can now sign in."}
