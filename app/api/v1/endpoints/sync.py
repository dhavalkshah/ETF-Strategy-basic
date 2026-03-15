from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.nse_sync_service import nse_sync_service

router = APIRouter()


@router.post(
    "/sync",
    summary="Sync NSE Data",
    description="Internal endpoint to sync latest data from NSE for all instruments. No authentication required."
)
async def sync_nse_data(
    lookback_days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    background: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Sync historical data from NSE for all instruments in database.
    
    - Fetches latest data for all indices, ETFs, and equities
    - Updates database with new records
    - Skips dates that already exist
    
    **This endpoint has NO authentication** - use only from internal services/cron jobs.
    
    Query Parameters:
    - lookback_days: How many days back to sync (default: 30, max: 365)
    
    Returns:
    - Summary of sync operation including records added and any errors
    """
    result = nse_sync_service.sync_all_instruments(db, lookback_days=lookback_days)
    
    return {
        "status": "success",
        "summary": result
    }


@router.post(
    "/sync/index/{index_name}",
    summary="Sync Single Index",
    description="Sync data for a specific index. No authentication required."
)
async def sync_single_index(
    index_name: str,
    lookback_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Sync data for a single index.
    
    Example: /sync/index/NIFTY%2050?lookback_days=7
    """
    from datetime import date, timedelta
    from app.crud.instrument import instrument as crud_instrument
    
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    
    # Get instrument
    instrument = crud_instrument.get_by_symbol(db, index_name)
    if not instrument:
        return {
            "status": "error",
            "message": f"Index {index_name} not found in database"
        }
    
    if instrument.instrument_type != "INDEX":
        return {
            "status": "error",
            "message": f"{index_name} is not an index (type: {instrument.instrument_type})"
        }
    
    try:
        records_added = nse_sync_service._sync_index(db, index_name, start_date, end_date)
        return {
            "status": "success",
            "index": index_name,
            "records_added": records_added,
            "date_range": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat()
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.post(
    "/sync/symbol/{symbol}",
    summary="Sync Single Symbol",
    description="Sync data for a specific ETF or equity. No authentication required."
)
async def sync_single_symbol(
    symbol: str,
    lookback_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Sync data for a single ETF or equity.
    
    Example: /sync/symbol/NIFTYBEES?lookback_days=7
    """
    from datetime import date, timedelta
    from app.crud.instrument import instrument as crud_instrument
    
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    
    # Get instrument
    instrument = crud_instrument.get_by_symbol(db, symbol)
    if not instrument:
        return {
            "status": "error",
            "message": f"Symbol {symbol} not found in database"
        }
    
    if instrument.instrument_type not in ["ETF", "EQUITY"]:
        return {
            "status": "error",
            "message": f"{symbol} is not an ETF/equity (type: {instrument.instrument_type})"
        }
    
    try:
        records_added = nse_sync_service._sync_etf(db, symbol, start_date, end_date)
        return {
            "status": "success",
            "symbol": symbol,
            "type": instrument.instrument_type,
            "records_added": records_added,
            "date_range": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat()
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get(
    "/status",
    summary="Sync Status",
    description="Check data freshness for all instruments"
)
async def sync_status(db: Session = Depends(get_db)):
    """
    Get sync status - shows which instruments have stale data.
    
    Returns instruments grouped by:
    - up_to_date: Last data within 3 days
    - needs_update: Last data 3-7 days old
    - stale: Last data >7 days old or no data
    """
    from datetime import date, timedelta
    from app.crud.instrument import instrument as crud_instrument
    from app.crud.historical_price import historical_price as crud_historical_price
    
    today = date.today()
    
    # Get all instruments
    all_instruments = (
        crud_instrument.get_multi_by_type(db, "INDEX", limit=1000) +
        crud_instrument.get_multi_by_type(db, "ETF", limit=1000) +
        crud_instrument.get_multi_by_type(db, "EQUITY", limit=1000)
    )
    
    status = {
        "total_instruments": len(all_instruments),
        "up_to_date": [],
        "needs_update": [],
        "stale": []
    }
    
    for instrument in all_instruments:
        # Get latest data point
        latest_data = crud_historical_price.get_historical_prices_for_instrument(
            db, instrument.id, today - timedelta(days=30), today
        )
        
        if not latest_data:
            status["stale"].append({
                "symbol": instrument.symbol,
                "type": instrument.instrument_type,
                "last_update": None,
                "days_ago": None
            })
            continue
        
        latest_date = max(hp.date for hp in latest_data)
        days_ago = (today - latest_date).days
        
        item = {
            "symbol": instrument.symbol,
            "type": instrument.instrument_type,
            "last_update": latest_date.isoformat(),
            "days_ago": days_ago
        }
        
        if days_ago <= 3:
            status["up_to_date"].append(item)
        elif days_ago <= 7:
            status["needs_update"].append(item)
        else:
            status["stale"].append(item)
    
    return status