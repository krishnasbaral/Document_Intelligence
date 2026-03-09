import json
import logging
import time
from typing import Optional, Dict, Any, List

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.settings import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def load_users() -> list[dict]:
    try:
        with open(settings.USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Users file not found: %s", settings.USERS_FILE)
        return []
    except json.JSONDecodeError:
        raise RuntimeError(f"{settings.USERS_FILE} is not valid JSON")


def get_user(username: str) -> Optional[dict]:
    for u in load_users():
        if (u.get("username") or "").lower() == username.lower():
            return u
    return None


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user(username)
    if not user:
        logger.info("Auth failed — user not found: %s", username)
        return None
    if not verify_password(password, user.get("password_hash", "")):
        logger.info("Auth failed — bad password for: %s", username)
        return None
    logger.info("Auth success: %s", username)
    return user


def create_access_token(sub: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Decode JWT and enrich with allowed_collections from users.json.
    allowed_collections=None means the user can access all collections (admin/unrestricted).
    allowed_collections=["HR Team"] means the user is locked to those collections only.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        sub  = payload.get("sub")
        role = payload.get("role")
        if not sub or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Load allowed_collections from users.json on every request so changes
    # take effect without restarting the server.
    user_record = get_user(sub)
    allowed = user_record.get("allowed_collections") if user_record else None

    return {
        "username": sub,
        "role": role,
        "allowed_collections": allowed,  # None = all, list = restricted
    }


def resolve_collections(user: Dict[str, Any]) -> List[str]:
    """
    Return the list of collections this user may access.
    Admins always get all collections regardless of allowed_collections field.
    """
    if user["role"] == "admin":
        return list(settings.COLLECTIONS)
    allowed = user.get("allowed_collections")
    if allowed is None:
        return list(settings.COLLECTIONS)
    # Return only the intersection of allowed + configured collections
    return [c for c in settings.COLLECTIONS if c in allowed]


def require_role(*roles: str):
    def _dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep
