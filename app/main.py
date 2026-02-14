from fastapi import FastAPI, APIRouter, Depends

from app.api.v1.endpoints import auth, backtest, advisor, instrument
from app.schemas.msg import Msg
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.schemas.user import UserOut

app = FastAPI(
    title="Indian ETF and Mutual Fund Backtesting and Advisory API",
    openapi_url="/openapi.json"
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_router.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
api_router.include_router(instrument.router, prefix="/instrument", tags=["instrument"])

@api_router.get("/", response_model=Msg)
async def root():
    return {"msg": "Welcome to ETF Backtesting API"}

@api_router.get("/users/me/", response_model=UserOut)
async def read_users_me(
    current_user: UserOut = Depends(get_current_active_user)
):
    return current_user

app.include_router(api_router)