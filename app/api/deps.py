
"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, Query, HTTPException, status
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
from app.models.orm import Hospital

def get_demo_hospital(
    db: DbSession,
    demo_session_id: str | None = Query(default=None)
) -> Hospital:
    if not demo_session_id:
        demo_session_id = "default"
        
    hospital = db.query(Hospital).filter(Hospital.name == demo_session_id).first()
    if not hospital:
        hospital = Hospital(name=demo_session_id)
        db.add(hospital)
        db.commit()
        db.refresh(hospital)
    return hospital

DemoHospital = Annotated[Hospital, Depends(get_demo_hospital)]

