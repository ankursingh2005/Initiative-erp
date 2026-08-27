import os
from datetime import datetime, timedelta
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
import models

# --------------------------------------------------------------------
# IMPORTANT: Before going live, change this to a long random secret.
# For learning/testing this is fine.
# --------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_BEFORE_GOING_LIVE")
ALGORITHM = "HS256"
# Installed mobile users should not have to sign in every workday. Keep the
# duration configurable for deployments while defaulting to one year. A user
# can still be revoked immediately by setting their account status inactive.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 365)))

# This tells FastAPI's /docs page where to send username/password to get a token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Owner and HR have the same application-wide access as Admin. User
# Management uses a separate strict guard below and remains Admin-only.
ADMIN_ACCESS_ROLES = {"Admin", "Owner", "HR"}


def hash_password(password: str) -> str:
    # Keep the work factor configurable. Ten rounds remains deliberately
    # expensive for attackers while avoiding the noticeable multi-second
    # signup delay seen on small hosted instances.
    rounds = max(10, int(os.getenv("BCRYPT_ROUNDS", "10")))
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Reads the token sent by the browser/app and returns the logged-in user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or user.status != "Active":
        raise credentials_exception
    return user


def require_roles(*allowed_roles):
    """
    Use this on any endpoint that should only be usable by certain roles.
    Example: Depends(require_roles("Admin"))
    """
    def role_checker(current_user: models.User = Depends(get_current_user)):
        inherited_admin_access = (
            current_user.role in {"Owner", "HR"} and "Admin" in allowed_roles
        )
        if current_user.role not in allowed_roles and not inherited_admin_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not allowed to do this. Allowed: {allowed_roles}",
            )
        return current_user
    return role_checker


def require_user_management_admin(
    current_user: models.User = Depends(get_current_user),
):
    """Strict guard for account administration; Owner and HR are excluded."""
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User Management is available only to Admin",
        )
    return current_user


def has_admin_access(user: models.User) -> bool:
    return user.role in ADMIN_ACCESS_ROLES
