from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import auth, backtest, advisor, instrument, transaction, portfolio, sync
from app.schemas.msg import Msg
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.schemas.user import UserOut

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up Indian ETF and Mutual Fund Advisory API")
    yield
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title="Indian ETF and Mutual Fund Backtesting and Advisory API",
    description="API for backtesting investment strategies and getting AI-powered investment recommendations for Indian markets",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    sync.router,
    prefix="/api/v1/sync",
    tags=["Data Sync (Internal)"]
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )


# API router
api_router = APIRouter(prefix="/api/v1")

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(instrument.router, prefix="/instruments", tags=["Instruments"])
api_router.include_router(transaction.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
api_router.include_router(advisor.router, prefix="/advisor", tags=["Advisory"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["Backtesting"])


@api_router.get("/", response_model=Msg, summary="API Root")
async def root():
    """Root endpoint returning welcome message."""
    return {"msg": "Welcome to Indian ETF and Mutual Fund Advisory API v1.0"}


@api_router.get("/health", response_model=Msg, summary="Health Check")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"msg": "API is healthy"}


@api_router.get("/users/me", response_model=UserOut, summary="Get Current User")
async def read_users_me(
    current_user: UserOut = Depends(get_current_active_user)
):
    """Get current authenticated user details."""
    return current_user


# Include API router
app.include_router(api_router)


# Root redirect
@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to API docs."""
    return {"msg": "API is running. Visit /api/v1/docs for documentation."}