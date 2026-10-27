"""FastAPI service for hybrid substitute search with JWT, rate limits, and Sentry."""

import logging
import os
from functools import lru_cache
from typing import Optional

import sentry_sdk
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from src.auth import User, authenticate_user, create_access_token, decode_access_token, get_current_user
from src.hybrid_substitute import HybridSubstitutePipeline, TOP_K

logger = logging.getLogger("bom.api")

GENERIC_500 = {"detail": "Internal server error"}


class FindSubstitutesRequest(BaseModel):
    part_number: str = Field(min_length=1)
    top_k: int = Field(default=TOP_K, ge=1, le=50)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@lru_cache(maxsize=1)
def get_pipeline() -> HybridSubstitutePipeline:
    return HybridSubstitutePipeline.from_env()


def init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0, send_default_pii=False)


def report_exception(exc: BaseException) -> None:
    logger.exception("Unhandled server error")
    sentry_sdk.capture_exception(exc)


def rate_limit_key(request: Request) -> str:
    """Limit by authenticated user (JWT sub), not shared IP, when a bearer token is present."""
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            username = decode_access_token(token).get("sub")
            if username:
                return f"user:{username}"
        except Exception:
            pass
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _run(part_number: str, top_k: int, pipeline: Optional[HybridSubstitutePipeline] = None) -> dict:
    engine = pipeline or get_pipeline()
    payload = engine.find_substitutes(part_number, top_k=top_k)
    if payload.get("error") == "COMPONENT_NOT_FOUND":
        raise HTTPException(status_code=404, detail=payload["message"])
    return payload


def build_app(
    pipeline: Optional[HybridSubstitutePipeline] = None,
    *,
    rate_limit: str = "1/second",
) -> FastAPI:
    init_sentry()
    limiter = Limiter(key_func=rate_limit_key, default_limits=[])
    application = FastAPI(title="BOM Substitute Finder", version="1.0.0", debug=False)
    application.state.limiter = limiter
    application.state.pipeline = pipeline
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, RateLimitExceeded):
            return await _rate_limit_exceeded_handler(request, exc)
        if isinstance(exc, RequestValidationError):
            return await request_validation_exception_handler(request, exc)
        if isinstance(exc, StarletteHTTPException):
            return await http_exception_handler(request, exc)
        report_exception(exc)
        return JSONResponse(status_code=500, content=GENERIC_500)

    @application.post("/token", response_model=TokenResponse)
    def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        user = authenticate_user(form_data.username, form_data.password)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenResponse(access_token=create_access_token(user.username))

    def bound_pipeline() -> Optional[HybridSubstitutePipeline]:
        return getattr(application.state, "pipeline", None)

    @application.get("/find_substitutes")
    @limiter.limit(rate_limit)
    def find_substitutes_get(
        request: Request,
        part_number: str = Query(..., min_length=1, description="Base MPN or catalog component_id"),
        top_k: int = Query(default=TOP_K, ge=1, le=50),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        _ = current_user
        return _run(part_number, top_k, bound_pipeline())

    @application.post("/find_substitutes")
    @limiter.limit(rate_limit)
    def find_substitutes_post(
        request: Request,
        body: FindSubstitutesRequest = Body(...),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        _ = current_user
        return _run(body.part_number, body.top_k, bound_pipeline())

    return application


app = build_app()
create_app = build_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.find_substitutes_api:app", host="127.0.0.1", port=8001, reload=False)
