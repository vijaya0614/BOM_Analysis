from fastapi import FastAPI, HTTPException, Request, status, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.auth import authenticate_user, create_access_token
from src.dependencies import get_user_dependency
from src.config import settings

from src.risk_api import (
    SAMPLE_PROJECTS,
    INDUSTRY_PROJECT_IDS,
    analyze_bom_path,
    analyze_uploaded_csv,
    analyze_industry_product,
)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app = FastAPI(title="PS5 Risk Analysis API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration – origins from Pydantic settings
origins = settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check() -> dict:
    """Simple health endpoint used by orchestration tools."""
    return {"status": "ok"}

@app.post("/auth/login")
async def login(payload: dict) -> dict:
    username = payload.get("username")
    password = payload.get("password")
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(subject=user.username)
    response = JSONResponse(content={"access_token": access_token})
    # HttpOnly cookie
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"token": access_token}

@app.get("/risk/projects")
async def list_projects() -> dict:
    projects = [{"id": pid, "name": meta["name"], "bom_path": meta.get("bom_path")} for pid, meta in SAMPLE_PROJECTS.items()]
    return {"projects": projects}

@app.get("/risk/analyze")
@limiter.limit("100/minute")
async def analyze_get(project: str = None, user: dict = Depends(get_user_dependency)) -> dict:
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' query parameter")
    if project in INDUSTRY_PROJECT_IDS:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        result = analyze_industry_product(project, meta["name"])
    else:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        result = analyze_bom_path(meta["bom_path"], meta["name"])  # type: ignore[arg-type]
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result.get("message", "Error"))
    return result

@app.post("/risk/analyze")
@limiter.limit("100/minute")
async def analyze_post(payload: dict, user: dict = Depends(get_user_dependency)) -> dict:
    project = payload.get("project")
    if project:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        if project in INDUSTRY_PROJECT_IDS:
            result = analyze_industry_product(project, meta["name"])
        else:
            result = analyze_bom_path(meta["bom_path"], meta["name"])  # type: ignore[arg-type]
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("message", "Error"))
        return result
    csv_text = payload.get("csv_text")
    if not csv_text:
        raise HTTPException(status_code=400, detail="Payload must include 'project' or 'csv_text'.")
    filename = payload.get("filename", "uploaded_bom.csv")
    result = analyze_uploaded_csv(csv_text, filename)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("message", "Error"))
    return result

# Global exception handler to match the previous JSON error format
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "message": exc.detail, "status": exc.status_code})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
