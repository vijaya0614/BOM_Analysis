"""JWT auth helpers for the FastAPI backend (OAuth2 password bearer)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
_EPHEMERAL_DEV_SECRET = secrets.token_urlsafe(48)


def jwt_secret() -> str:
    configured = settings.JWT_SECRET_KEY.strip()
    environment = settings.ENV.lower()
    if configured:
        if len(configured) < 32:
            raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")
        return configured
    if environment in {"prod", "production", "staging"}:
        raise RuntimeError("JWT_SECRET_KEY must be configured outside development.")
    return _EPHEMERAL_DEV_SECRET


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
    roles: tuple[str, ...] = ("viewer",)


def _bootstrap_users() -> Dict[str, User]:
    users: Dict[str, User] = {}
    demo_user = settings.JWT_DEMO_USER.strip()
    demo_password = settings.JWT_DEMO_PASSWORD.get_secret_value()
    if demo_user and demo_password:
        users[demo_user] = User(username=demo_user, hashed_password=hash_password(demo_password), roles=("viewer", "engineer"))
    for username, env_key, roles in (
        ("reviewer", settings.JWT_REVIEWER_PASSWORD.get_secret_value(), ("viewer", "reviewer")),
        ("auditor", settings.JWT_AUDITOR_PASSWORD.get_secret_value(), ("viewer", "auditor")),
    ):
        password = env_key
        if password:
            users[username] = User(username=username, hashed_password=hash_password(password), roles=roles)
    return users


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
    user = get_user(subject)
    payload = {"sub": subject, "exp": expire, "roles": list(user.roles) if user else []}
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
