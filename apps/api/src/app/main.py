from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="ARGUS API", version="0.1.0", docs_url="/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_strings,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, error: OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"},
                        headers={"Retry-After": "5"})
