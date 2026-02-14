from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.strategy.models import AdvisorRecommendation
from app.services.advisor_service import advisor_service
from pydantic import BaseModel, Field

router = APIRouter()

class AdvisorRequest(BaseModel):
    instrument_symbol: str
    current_holdings: Dict[str, float] = Field(default_factory=dict)
    cash_balance: float = Field(default=0.0, ge=0)
    sip_amount: float = Field(default=1000.0, ge=0)
    dip_multiplier: float = Field(default=1.0, ge=0)

@router.post("/", response_model=AdvisorRecommendation, status_code=status.HTTP_200_OK)
async def get_advisor_recommendation_api(
    advisor_request: AdvisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    recommendation = await advisor_service.get_daily_recommendation(
        db,
        current_user,
        advisor_request.instrument_symbol,
        advisor_request.current_holdings,
        advisor_request.cash_balance,
        advisor_request.sip_amount,
        advisor_request.dip_multiplier
    )
    return recommendation