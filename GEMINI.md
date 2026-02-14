This file is the authoritative system design document.
All implementation decisions must strictly follow this file.
If conflicts arise, GEMINI.md overrides CLI prompts.

You are a senior Python backend architect and quantitative developer.

Your goal is to design and implement a production-ready, dockerized backend system for Indian ETF and Mutual Fund backtesting and advisory.

Before writing any code:
1. First scan and review all existing code in the current directory. The current folder has a rudimentary python but it has a effective strategy, but the source of information may not be realiable.
2. Produce a detailed architecture plan explaining:
   - Project structure
   - Tech stack choices
   - Data flow
   - Strategy engine separation
   - DB schema design
   - External data integration design
3. Only after approval of plan, proceed to implementation phase-by-phase.

------------------------------------------------------------
MANDATORY TECH STACK
------------------------------------------------------------

Backend Framework: FastAPI
ORM: SQLAlchemy (2.0 style)
Database: PostgreSQL
Migrations: Alembic
Auth: JWT (email + password, hashed with bcrypt)
Testing: Pytest
API Documentation: OpenAPI/Swagger (auto from FastAPI)
Containerization: Docker + docker-compose

For local testing:
- Use SQLite via SQLAlchemy
- Create and Use a Virtual Environment for Python 
- But production config must use PostgreSQL

------------------------------------------------------------
DATA SOURCES (INDIAN MARKET)
------------------------------------------------------------

Evaluate and choose the best approach:

ETF & Index Data:
- nsepython
- jugaad-data
- Or any better NSE compatible library

Mutual Fund Data:
- https://www.mfapi.in/docs/

The system must abstract data providers behind a DataService layer so that
changing provider does not affect strategy logic.

------------------------------------------------------------
CORE FEATURES
------------------------------------------------------------

1) USER AUTHENTICATION
- Register with email + password
- Login and receive JWT
- Password must be hashed
- Unique email constraint
- Proper error handling
- User investment history tied to user_id

------------------------------------------------------------

2) BACKTEST ENGINE (RSI + MA20 STRATEGY)

Create a dedicated strategy module.

Inputs:
- instrument_type: MF or ETF
- symbol
- sip_amount (default 1000)
- start_date
- end_date
- benchmark_index
- dip_multiplier (optional)
- carry_over_fraction (default 0.5)

Requirements:
- Fetch historical data
- Calculate:
    - RSI (14 period)
    - MA20
- Implement strategy logic cleanly
- Track:
    - Daily portfolio value
    - Units accumulated
    - Cash balance
    - Carry-over logic
- Compute:
    - Absolute returns
    - Benchmark returns
    - XIRR

Output:
{
  equity_curve: [...],
  benchmark_curve: [...],
  transactions: [...],
  xirr: float,
  summary_stats: {...}
}

Strategy logic must NOT depend on FastAPI or DB layer.

------------------------------------------------------------

3) DAILY ETF ADVISOR

User inputs today's transactions.

System must:
- Store all user holdings
- Based on yesterday’s close:
    - Calculate RSI
    - Evaluate if additional SIP or dip buy needed
- Return recommendation:
    {
        recommended_amount,
        reason,
        portfolio_state_snapshot
    }

------------------------------------------------------------

4) SYMBOL DISCOVERY API

API for:
- ETF search
- MF search
- Benchmark index search

Requirements:
- Autocomplete by partial symbol
- Cache symbols in DB
- If not found locally → fetch live → store in DB
- Avoid repeated live calls

------------------------------------------------------------

DATABASE DESIGN REQUIREMENTS

Tables must include:
- users
- instruments
- historical_prices
- transactions
- backtest_results (optional cache)
- symbol_cache

Use proper indexing.

------------------------------------------------------------

DOCKER REQUIREMENTS

- Dockerfile
- docker-compose.yml
- Separate service for:
    - backend
    - postgres
- Environment variables via .env
- Production-ready config

------------------------------------------------------------

MIGRATIONS

- Use Alembic
- Include initial migration
- Include migration scripts

------------------------------------------------------------

TESTING

- Unit tests for:
    - Strategy logic
    - RSI & MA calculation
    - XIRR
- Integration tests for:
    - Auth
    - Backtest API
    - Advisor API

At least 70% coverage.

------------------------------------------------------------

SWAGGER

- Ensure full OpenAPI spec
- Include example request/response models

------------------------------------------------------------

README.md

Must include:
- Architecture explanation
- Setup instructions
- Docker usage
- DB migration instructions
- Example API calls
- Strategy explanation
- Assumptions
- Known limitations

------------------------------------------------------------

IMPORTANT EXECUTION RULES

1. Implement phase-by-phase:
   Phase 1: Architecture & folder structure (Completed - Architecture plan approved, basic project structure and Docker setup created.)
   Phase 2: Auth + DB setup (Completed - Database base, session, config, models, initial Alembic migration, security, schemas, CRUD, auth service, and API endpoints implemented.)
   Phase 3: Data abstraction layer (Completed - Instrument, HistoricalPrice, Transaction, BacktestResult, SymbolCache models; CRUD operations; InstrumentService; initial DataService with caching logic and external API placeholders.)
   Phase 4: Strategy engine (Completed - Strategy models, RSI/MA calculations, backtesting logic, and advisor logic implemented.)
   Phase 5: Backtest API (Completed - StrategyService implemented, backtest API endpoint created, and integrated into FastAPI application.)
   Phase 6: Advisor API (Completed - AdvisorService and advisor API endpoint created and integrated.)
   Phase 7: Symbol search (Completed - DataService enhanced for live symbol fetching, InstrumentService updated, and symbol search API endpoint created.)
   Phase 8: Tests (Completed - Unit tests for strategy logic and integration tests for API endpoints implemented.)
   Phase 9: Docker + Docs (Completed - Docker setup reviewed, and comprehensive README.md created.)
   Phase 4: Strategy engine
   Phase 5: Backtest API
   Phase 6: Advisor API
   Phase 7: Symbol search
   Phase 8: Tests
   Phase 9: Docker + Docs

2. Do not mix concerns.
3. Keep strategy pure Python.
4. No hardcoding of credentials.
5. Code must be production quality.
6. Avoid monolithic files.

Begin with architecture plan only.

After each phase, summarize what was implemented and wait for confirmation before proceeding.
