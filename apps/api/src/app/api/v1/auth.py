from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import get_auth_service
from app.services.auth import AuthService, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["authentication"])


class TokenRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def set_refresh_cookie(response: Response, token: str, service: AuthService) -> None:
    response.set_cookie(
        key="argus_refresh",
        value=token,
        max_age=service.refresh_token_max_age_seconds,
        httponly=True,
        secure=service._settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )


def token_response(access_token: str, service: AuthService) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=service._settings.access_token_expire_minutes * 60,
    )


@router.post("/token", response_model=TokenResponse)
def create_token(
    payload: TokenRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        user = service.authenticate(payload.email, payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    access_token, refresh_token = service.issue_token_pair(user)
    set_refresh_cookie(response, refresh_token, service)
    return token_response(access_token, service)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request, response: Response, service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenResponse:
    raw_token = request.cookies.get("argus_refresh")
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is required"
        )
    try:
        access_token, replacement_token = service.rotate_refresh_token(raw_token)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from error
    set_refresh_cookie(response, replacement_token, service)
    return token_response(access_token, service)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, response: Response, service: Annotated[AuthService, Depends(get_auth_service)]
) -> Response:
    raw_token = request.cookies.get("argus_refresh")
    if raw_token is not None:
        service.revoke_refresh_token(raw_token)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie("argus_refresh", path="/api/v1/auth")
    return response
