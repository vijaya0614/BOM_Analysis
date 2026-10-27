"""JWT auth helpers for the FastAPI backend (OAuth2 password bearer)."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def jwt_secret() -> str:
    return os.environ.get("JWT_SECRET_KEY", "bom-dev-jwt-secret-change-me-32b+")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    material = (salt or jwt_secret()).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), material, 120_000).hex()


def verify_password(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(plain), hashed)


@dataclass(frozen=True)
class User:
    username: str
    hashed_password: str
    disabled: bool = False


def _bootstrap_users() -> Dict[str, User]:
    demo_user = os.environ.get("JWT_DEMO_USER", "engineer")
    demo_password = os.environ.get("JWT_DEMO_PASSWORD", "changeme")
    reviewer_password = os.environ.get("JWT_REVIEWER_PASSWORD", "changeme")
    return {
        demo_user: User(username=demo_user, hashed_password=hash_password(demo_password)),
        "reviewer": User(username="reviewer", hashed_password=hash_password(reviewer_password)),
        "auditor": User(username="auditor", hashed_password=hash_password(reviewer_password)),
    }


USERS = _bootstrap_users()


def get_user(username: str) -> Optional[User]:
    return USERS.get(username)


def authenticate_user(username: str, password: str) -> Optional[User]:
    user = get_user(username)
    if user is None or user.disabled or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username or not isinstance(username, str):
            raise credentials_exception
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc
    user = get_user(username)
    if user is None or user.disabled:
        raise credentials_exception
    return user
