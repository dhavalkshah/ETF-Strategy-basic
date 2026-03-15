# Indian ETF and Mutual Fund Backtesting and Advisory API
API for backtesting investment strategies and getting AI-powered investment recommendations for Indian markets

## Version: 1.0.0

### /api/v1/auth/register

#### POST
##### Summary:

Register User

##### Responses

| Code | Description |
| ---- | ----------- |
| 201 | Successful Response |
| 422 | Validation Error |

### /api/v1/auth/login

#### POST
##### Summary:

Login Access Token

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

### /api/v1/instruments/search

#### GET
##### Summary:

Search Instruments

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| query | query | Partial symbol or name to search for | Yes | string |
| instrument_type | query | Filter by instrument type (ETF, MF, INDEX) | No |  |
| limit | query | Maximum number of results to return | No | integer |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/transactions/

#### POST
##### Summary:

Create Transaction

##### Description:

Create a new transaction.

Records a buy, sell, SIP, or dividend transaction for the current user.
The instrument must exist in the database before creating the transaction.

##### Responses

| Code | Description |
| ---- | ----------- |
| 201 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

#### GET
##### Summary:

Get Transactions

##### Description:

Get paginated list of transactions for the current user.

Supports filtering by:
- Date range (start_date, end_date)
- Instrument symbol
- Transaction type (BUY, SELL, SIP, DIVIDEND, DIP_BUY)

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| page | query | Page number (1-indexed) | No | integer |
| page_size | query | Items per page (max 100) | No | integer |
| start_date | query | Filter by start date | No |  |
| end_date | query | Filter by end date | No |  |
| instrument_symbol | query | Filter by instrument symbol | No |  |
| transaction_type | query | Filter by transaction type | No |  |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/transactions/summary

#### GET
##### Summary:

Get Transaction Summary

##### Description:

Get transaction summary statistics for the current user.

Returns:
- Total transactions count
- Total buy/sell amounts
- Total fees paid
- Net investment
- Number of unique instruments
- Date range of transactions

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| start_date | query | Filter by start date | No |  |
| end_date | query | Filter by end date | No |  |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/transactions/{transaction_id}

#### GET
##### Summary:

Get Transaction

##### Description:

Get a specific transaction by ID.

Returns 404 if transaction doesn't exist or doesn't belong to the current user.

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| transaction_id | path |  | Yes | string (uuid) |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

#### PUT
##### Summary:

Update Transaction

##### Description:

Update a transaction.

Can update: transaction_date, quantity, price_per_unit, amount, fees
Cannot update: transaction_type, instrument

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| transaction_id | path |  | Yes | string (uuid) |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

#### DELETE
##### Summary:

Delete Transaction

##### Description:

Delete a transaction.

Returns 404 if transaction doesn't exist or doesn't belong to the current user.

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| transaction_id | path |  | Yes | string (uuid) |

##### Responses

| Code | Description |
| ---- | ----------- |
| 204 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/portfolio/

#### GET
##### Summary:

Get Portfolio Summary

##### Description:

Get complete portfolio summary calculated from transaction history

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| as_of_date | query | Calculate holdings as of this date (default: today) | No | date |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/portfolio/{instrument_symbol}

#### GET
##### Summary:

Get Holdings for Specific Instrument

##### Description:

Get holding details for a specific instrument

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| instrument_symbol | path |  | Yes | string |
| as_of_date | query | Calculate holdings as of this date | No | date |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/advisor/recommendation/{instrument_symbol}

#### GET
##### Summary:

Get Investment Recommendation

##### Description:

Get AI-powered investment recommendation for a specific instrument.
    
    The recommendation is based on:
    - Your actual transaction history and current holdings
    - Technical analysis (RSI, Moving Averages)
    - Market conditions
    
    Returns recommended investment amount and reasoning.

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| instrument_symbol | path |  | Yes | string |
| sip_amount | query | Regular SIP amount in ₹ | No | number |
| dip_multiplier | query | Multiplier for dip buying (1.0-10.0) | No | number |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/advisor/portfolio-recommendations

#### GET
##### Summary:

Get Recommendations for All Holdings

##### Description:

Get investment recommendations for all instruments in your portfolio

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
| sip_amount | query | Regular SIP amount in ₹ | No | number |
| dip_multiplier | query | Multiplier for dip buying | No | number |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/backtest/

#### POST
##### Summary:

Run Backtest Api

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |
| 422 | Validation Error |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### /api/v1/

#### GET
##### Summary:

API Root

##### Description:

Root endpoint returning welcome message.

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |

### /api/v1/health

#### GET
##### Summary:

Health Check

##### Description:

Health check endpoint for monitoring.

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |

### /api/v1/users/me

#### GET
##### Summary:

Get Current User

##### Description:

Get current authenticated user details.

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Successful Response |

##### Security

| Security Schema | Scopes |
| --- | --- |
| OAuth2PasswordBearer | |

### Models


#### AdvisorRecommendation

Daily investment recommendation from the advisor.

Attributes:
    recommended_amount: Amount to invest (SIP or dip buy)
    reason: Explanation for the recommendation
    portfolio_state_snapshot: Current portfolio state (holdings, cash, etc.)
    rsi_value: RSI value used for recommendation (if applicable)
    signal_type: Type of signal (SIP, DIP_BUY, HOLD)

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| recommended_amount | number | Recommended investment amount (non-negative) | Yes |
| reason | string | Explanation for recommendation | Yes |
| portfolio_state_snapshot |  | Current portfolio state | No |
| rsi_value |  | RSI value (0-100) | No |
| signal_type |  | Signal type: SIP, DIP_BUY, HOLD | No |

#### Body_login_access_token_api_v1_auth_login_post

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| grant_type |  |  | No |
| username | string |  | Yes |
| password | string |  | Yes |
| scope | string |  | No |
| client_id |  |  | No |
| client_secret |  |  | No |

#### DailyPortfolioValue

Daily snapshot of portfolio value.

Attributes:
    date: Portfolio value date
    value: Total portfolio value on this date

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| date | date |  | Yes |
| value | number | Portfolio value must be non-negative | Yes |

#### HTTPValidationError

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| detail | [ [ValidationError](#validationerror) ] |  | No |

#### HoldingDetail

Details of a single holding.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| units | number | Number of units held | Yes |
| avg_price | number | Average purchase price | Yes |
| total_invested | number | Total amount invested | Yes |
| instrument_id | string | Instrument ID | Yes |

#### InstrumentType

Supported instrument types for trading strategies.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| InstrumentType | string | Supported instrument types for trading strategies. |  |

#### Msg

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| msg | string |  | Yes |

#### PortfolioSummary

Complete portfolio summary.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| holdings | object |  | Yes |
| cash_balance | number | Cash balance (negative = net invested) | Yes |
| total_invested | number | Total amount invested across all instruments | Yes |
| num_instruments | integer | Number of unique instruments held | Yes |
| total_units | number | Total units across all instruments | Yes |
| as_of_date | date | Date of portfolio calculation | Yes |

#### StrategyInput

Input configuration for running a backtesting strategy.

Attributes:
    instrument_type: Type of instrument (EQUITY, ETF, INDEX, MF)
    symbol: Trading symbol or scheme code
    sip_amount: Regular SIP amount per period
    start_date: Start date for backtest
    end_date: End date for backtest
    benchmark_index: Optional benchmark index symbol for comparison
    dip_multiplier: Optional multiplier for dip buying (e.g., 2.0 means buy 2x on dips)
    carry_over_fraction: Fraction of unused cash to carry forward (0.0-1.0)

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| instrument_type | [InstrumentType](#instrumenttype) |  | Yes |
| symbol | string | Trading symbol or scheme code | Yes |
| sip_amount | number | Regular SIP amount (must be positive) | No |
| start_date | date | Backtest start date | Yes |
| end_date | date | Backtest end date | Yes |
| benchmark_index |  | Benchmark index symbol for comparison | No |
| dip_multiplier |  | Multiplier for dip buying (1.0-10.0, e.g., 2.0 = buy 2x on dips) | No |
| carry_over_fraction | number | Fraction of unused cash to carry forward (0.0-1.0) | No |

#### StrategyResult

Complete result of a strategy backtest.

Attributes:
    equity_curve: Daily portfolio values over backtest period
    benchmark_curve: Daily benchmark values (if benchmark provided)
    transactions: List of all transactions executed
    summary_stats: Summary statistics of strategy performance
    message: Overall status or info message

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| equity_curve | [ [DailyPortfolioValue](#dailyportfoliovalue) ] | Daily portfolio values | Yes |
| benchmark_curve | [ [DailyPortfolioValue](#dailyportfoliovalue) ] | Daily benchmark values | No |
| transactions | [ [TransactionRecord](#transactionrecord) ] | Transaction history | Yes |
| summary_stats | [SummaryStatistics](#summarystatistics) |  | Yes |
| message |  | Overall status message | No |

#### SummaryStatistics

Summary statistics for strategy performance.

Attributes:
    total_investment: Total amount invested
    final_portfolio_value: Final portfolio value at end date
    absolute_return: Absolute return amount
    absolute_return_pct: Absolute return percentage
    xirr: XIRR (Extended Internal Rate of Return) in percentage
    benchmark_return: Benchmark return percentage (if benchmark provided)
    cagr: Compound Annual Growth Rate in percentage
    max_drawdown: Maximum drawdown percentage
    message: Additional information or status message

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| total_investment | number | Total invested amount | Yes |
| final_portfolio_value | number | Final portfolio value | Yes |
| absolute_return | number | Absolute return amount | Yes |
| absolute_return_pct |  | Absolute return percentage | No |
| xirr |  | XIRR percentage | No |
| benchmark_return |  | Benchmark return percentage | No |
| cagr |  | CAGR percentage | No |
| max_drawdown |  | Maximum drawdown percentage (negative) | No |
| message |  | Status or info message | No |

#### SymbolCacheOut

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| symbol | string |  | Yes |
| name | string |  | Yes |
| instrument_type | string |  | Yes |
| source |  |  | No |
| id | string (uuid) |  | Yes |
| last_fetched_at |  |  | No |
| created_at | dateTime |  | Yes |
| updated_at | dateTime |  | Yes |

#### Token

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| access_token | string |  | Yes |
| token_type | string |  | No |

#### TransactionCreate

Schema for creating a new transaction.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| instrument_symbol | string | Trading symbol or scheme code | Yes |
| transaction_date | date | Transaction date | Yes |
| transaction_type | [TransactionType](#transactiontype) | Transaction type | Yes |
| quantity | number | Quantity (must be positive) | Yes |
| price_per_unit | number | Price per unit (must be positive) | Yes |
| amount | number | Transaction amount | Yes |
| fees | number | Transaction fees | No |
| backtest_id |  | Optional backtest ID if from backtest | No |

#### TransactionListResponse

Schema for paginated transaction list.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| total | integer |  | Yes |
| page | integer |  | Yes |
| page_size | integer |  | Yes |
| transactions | [ [TransactionOut](#transactionout) ] |  | Yes |

#### TransactionOut

Schema for transaction output.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| id | string (uuid) |  | Yes |
| user_id |  |  | Yes |
| backtest_id |  |  | Yes |
| instrument_id | string (uuid) |  | Yes |
| transaction_date | date |  | Yes |
| transaction_type | string |  | Yes |
| quantity | number |  | Yes |
| price_per_unit | number |  | Yes |
| amount | number |  | Yes |
| fees | number |  | Yes |
| created_at | date |  | Yes |
| instrument_symbol |  |  | No |
| instrument_name |  |  | No |

#### TransactionRecord

Record of a single transaction in the portfolio.

Attributes:
    date: Transaction date
    type: Transaction type (BUY, SELL, SIP, DIP_BUY)
    quantity: Number of units transacted
    price_per_unit: Price per unit at transaction
    amount: Total transaction amount
    cash_balance: Cash balance after transaction
    units_accumulated: Total units held after transaction

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| date | date |  | Yes |
| type | [TransactionType](#transactiontype) |  | Yes |
| quantity | number | Quantity must be non-negative | Yes |
| price_per_unit | number | Price must be positive | Yes |
| amount | number | Transaction amount (can be negative for sells) | Yes |
| cash_balance | number | Cash balance after transaction | Yes |
| units_accumulated | number | Total units held after transaction | Yes |

#### TransactionSummary

Schema for transaction summary statistics.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| total_transactions | integer |  | Yes |
| total_buy_amount | number |  | Yes |
| total_sell_amount | number |  | Yes |
| total_fees | number |  | Yes |
| net_investment | number |  | Yes |
| unique_instruments | integer |  | Yes |
| date_range | object |  | Yes |

#### TransactionType

Types of transactions in portfolio.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| TransactionType | string | Types of transactions in portfolio. |  |

#### TransactionUpdate

Schema for updating a transaction.

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| transaction_date |  |  | No |
| quantity |  |  | No |
| price_per_unit |  |  | No |
| amount |  |  | No |
| fees |  |  | No |

#### UserCreate

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| email | string (email) |  | Yes |
| is_active |  |  | No |
| password | string |  | Yes |

#### UserOut

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| email |  |  | No |
| is_active |  |  | No |
| id | string (uuid) |  | Yes |
| created_at | dateTime |  | Yes |
| updated_at | dateTime |  | Yes |

#### ValidationError

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| loc | [  ] |  | Yes |
| msg | string |  | Yes |
| type | string |  | Yes |