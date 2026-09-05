"""FastAPI auth dependencies for the admin backend."""
from __future__ import annotations

import time

from fastapi import Cookie, HTTPException, Request, status

from ..config import get_settings
from .security import verify_signed_payload


def get_current_admin(
    request: Request,
    admin_session: str | None = Cookie(default=None),
) -> str:
    settings = get_settings()
    token = admin_session or request.cookies.get("admin_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    data = verify_signed_payload(token, settings.secret_key)
    if not data or data.get("sub") != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    if int(data.get("exp", 0)) < time.time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
    return data["sub"]
