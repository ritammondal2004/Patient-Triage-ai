
"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
    
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
        

def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Off by default for local demos; flip REQUIRE_API_KEY=true in .env to enforce."""
    settings = get_settings()
    if not settings.require_api_key:
        return   
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )

            
ApiKey = Annotated[None, Depends(require_api_key)]  