from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.schemas.instrument import InstrumentOut # This will be used if we need to return instrument details
from app.strategy.models import StrategyInput, StrategyResult
from app.services.strategy_service import strategy_service

router = APIRouter()

@router.post("/", response_model=StrategyResult, status_code=status.HTTP_200_OK)
async def run_backtest_api(
    strategy_input: StrategyInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    # Ensure the instrument type is valid
    if strategy_input.instrument_type not in ["ETF", "MF"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instrument_type. Must be 'ETF' or 'MF'."
        )

    result = await strategy_service.run_backtest_strategy(db, current_user, strategy_input)
    return result