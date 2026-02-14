import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any

import requests
from nsepython import nse_get_history, nse_search_symbol
from jugaad_data.nse.history import get_price_list
from jugaad_data.nse.symbols import get_symbol_list

from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.crud.historical_price import historical_price as crud_historical_price
from app.crud.symbol_cache import symbol_cache as crud_symbol_cache # Import for direct access
from app.db.models import Instrument, HistoricalPrice, SymbolCache
from app.schemas.instrument import InstrumentCreate, HistoricalPriceCreate, SymbolCacheCreate

logger = logging.getLogger(__name__)

class DataService:
    async def _fetch_nse_history_data(self, symbol: str, start_date: date, end_date: date) -> List[HistoricalPriceCreate]:
        """Fetches historical data from NSE using nsepython."""
        try:
            # nsepython's get_history uses YYYY-MM-DD format
            data = nse_get_history(symbol, start=start_date.strftime('%d-%m-%Y'), end=end_date.strftime('%d-%m-%Y'))
            if data is None or data.empty:
                logger.warning(f"nse_get_history returned no data for {symbol}.")
                return []
            
            historical_prices = []
            for _, row in data.iterrows():
                # Adjusted_Close is not directly available in nse_get_history for all cases, use Close if not present
                adj_close = row.get('Adj. Close', row['Close'])
                historical_prices.append(HistoricalPriceCreate(
                    date=pd.to_datetime(row['Date']).date(),
                    open=row['Open'],
                    high=row['High'],
                    low=row['Low'],
                    close=row['Close'],
                    adjusted_close=adj_close,
                    volume=row['Volume']
                ))
            return historical_prices
        except Exception as e:
            logger.error(f"Error fetching NSE history for {symbol}: {e}")
            return []

    async def _fetch_mfapi_history_data(self, mf_code: str, start_date: date, end_date: date) -> List[HistoricalPriceCreate]:
        """Fetches historical NAV data from mfapi.in."""
        url = f"https://api.mfapi.in/mf/{mf_code}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            
            if not data.get("data"):
                logger.warning(f"mfapi.in returned no data for MF code {mf_code}.")
                return []
            
            historical_prices = []
            for record in data["data"]:
                record_date = datetime.strptime(record["date"], "%d-%m-%Y").date()
                if start_date <= record_date <= end_date:
                    historical_prices.append(HistoricalPriceCreate(
                        date=record_date,
                        open=float(record["nav"]), # NAV is used for open, high, low, close for MF
                        high=float(record["nav"]),
                        low=float(record["nav"]),
                        close=float(record["nav"]),
                        adjusted_close=float(record["nav"]),
                        volume=0 # MF NAV data typically doesn't have volume
                    ))
            historical_prices.sort(key=lambda x: x.date) # Ensure sorted by date
            return historical_prices
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching MFAPI history for {mf_code}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing MFAPI data for {mf_code}: {e}")
            return []

    async def get_historical_data(self, db: Session, symbol: str, instrument_type: str, start_date: date, end_date: date) -> List[HistoricalPrice]:
        # 1. Check if instrument exists in DB, create if not
        db_instrument = crud_instrument.get_by_symbol(db, symbol)
        if not db_instrument:
            # For simplicity, create a dummy instrument if not found in DB based on provided symbol and type
            # In a real scenario, this would involve a symbol discovery process first
            instrument_create = InstrumentCreate(
                symbol=symbol,
                name=f"{symbol} Name", # Placeholder name
                instrument_type=instrument_type
            )
            db_instrument = crud_instrument.create(db, obj_in=instrument_create)
            logger.info(f"Created new instrument entry for {symbol}")

        # 2. Try to fetch historical data from DB first
        cached_data = crud_historical_price.get_historical_prices_for_instrument(
            db, db_instrument.id, start_date, end_date
        )

        # Check if all required dates are in cache and if data is recent enough (TODO: add recency check)
        # This check needs to be more robust for gaps. For now, a simple check if any data exists.
        if cached_data and len(cached_data) >= (end_date - start_date).days + 1: # Basic check for full range
            logger.info(f"Returning cached historical data for {symbol} from {start_date} to {end_date}")
            return cached_data
        
        # 3. If not fully cached or not found, fetch from external source
        new_data: List[HistoricalPriceCreate] = []
        if instrument_type in ("ETF", "INDEX"):
            new_data = await self._fetch_nse_history_data(symbol, start_date, end_date)
        elif instrument_type == "MF":
            new_data = await self._fetch_mfapi_history_data(symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported instrument type: {instrument_type}")
        
        # 4. Filter out data already in cache (if any) and save new data
        dates_in_cache = {hp.date for hp in cached_data}
        to_save = [d for d in new_data if d.date not in dates_in_cache]

        if to_save:
            saved_data = crud_historical_price.create_multi(db, to_save, db_instrument.id)
            logger.info(f"Saved {len(saved_data)} new historical price entries for {symbol}")
            # Combine cached and newly saved data for a complete return
            return sorted(cached_data + saved_data, key=lambda x: x.date)
        
        logger.info(f"No new data found for {symbol}. Returning cached data.")
        return cached_data

    async def _fetch_nse_symbols(self, query: str) -> List[SymbolCacheCreate]:
        """Fetches ETF/INDEX symbols from NSE."""
        symbols = []
        try:
            # nse_search_symbol often returns a broad list
            # We might need to filter or refine this based on actual need (ETF vs. INDEX)
            search_results = nse_search_symbol(query)
            if search_results and isinstance(search_results, list):
                for item in search_results:
                    # Basic filtering, assume 'type' or 'series' can help categorize
                    if 'symbol' in item and 'companyName' in item:
                        # nsepython doesn't explicitly give ETF/INDEX, need heuristic
                        # For simplicity, assume anything that's not Equity is potentially Index/ETF
                        # Or, check market_type from nse_get_quote or similar if available
                        instrument_type = "INDEX" # Default for now
                        if "ETF" in item['companyName'].upper() or "BEES" in item['symbol'].upper():
                            instrument_type = "ETF"
                        
                        symbols.append(SymbolCacheCreate(
                            symbol=item['symbol'],
                            name=item['companyName'],
                            instrument_type=instrument_type,
                            source="NSE"
                        ))
            
            # Also try jugaad_data
            jugaad_symbols_df = get_symbol_list()
            if not jugaad_symbols_df.empty:
                filtered_jugaad = jugaad_symbols_df[jugaad_symbols_df['SYMBOL'].str.contains(query.upper())]
                for _, row in filtered_jugaad.iterrows():
                     instrument_type = "INDEX" # Default
                     if "ETF" in str(row.get('NAME')).upper() or "BEES" in str(row['SYMBOL']).upper():
                        instrument_type = "ETF"
                     symbols.append(SymbolCacheCreate(
                        symbol=row['SYMBOL'],
                        name=row.get('NAME', row['SYMBOL']),
                        instrument_type=instrument_type,
                        source="NSE_Jugaad"
                    ))
            
            return symbols
        except Exception as e:
            logger.error(f"Error fetching NSE symbols for '{query}': {e}")
            return []

    async def _fetch_mfapi_symbols(self, query: str) -> List[SymbolCacheCreate]:
        """Fetches Mutual Fund symbols from mfapi.in API."""
        symbols = []
        # mfapi.in doesn't have a direct search API, usually we iterate through all MFs
        # For this purpose, we will simulate a search by fetching some popular MFs
        # or relying on a pre-fetched list.
        # This part is highly dependent on how mfapi.in expects search.
        # A full list of all MFs is available at https://api.mfapi.in/mf if we want to cache all.
        # For live search, we can fetch all and filter, but it's not efficient.
        logger.warning("Live MFAPI symbol search is complex; fetching a full list might be required.")
        try:
            # Example: Fetch a list of all MFs and filter locally (not scalable for large lists)
            all_mf_data = requests.get("https://api.mfapi.in/mf", timeout=30).json()
            for mf_code, mf_name in all_mf_data.items():
                if query.lower() in mf_name.lower() or query.lower() in mf_code.lower():
                    symbols.append(SymbolCacheCreate(
                        symbol=mf_code,
                        name=mf_name,
                        instrument_type="MF",
                        source="MFAPI"
                    ))
            return symbols
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching MFAPI full list for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing MFAPI full list for '{query}': {e}")
            return []

    async def search_and_cache_symbols(self, db: Session, query: str, instrument_type: Optional[str] = None) -> List[SymbolCache]:
        # 1. First, search local cache
        cached_symbols = crud_symbol_cache.get_multi_by_partial_symbol(db, query)
        
        # Filter by instrument_type if provided
        if instrument_type:
            cached_symbols = [s for s in cached_symbols if s.instrument_type == instrument_type]

        if cached_symbols:
            logger.info(f"Returning {len(cached_symbols)} cached symbols for '{query}' (type: {instrument_type})")
            # Convert SymbolCache (DB model) to a list of DB models
            return cached_symbols
        
        # 2. If not found in cache, fetch from live data sources
        live_symbols: List[SymbolCacheCreate] = []
        
        if instrument_type in ("ETF", "INDEX", None): # Search NSE if ETF, INDEX or no type specified
            nse_symbols = await self._fetch_nse_symbols(query)
            live_symbols.extend(nse_symbols)

        if instrument_type in ("MF", None): # Search MFAPI if MF or no type specified
            mfapi_symbols = await self._fetch_mfapi_symbols(query)
            live_symbols.extend(mfapi_symbols)
        
        # 3. Cache newly fetched symbols and return them
        saved_symbols = []
        for symbol_data in live_symbols:
            # Check if symbol already exists in cache (could be from another source/type)
            existing_symbol = crud_symbol_cache.get_by_symbol(db, symbol_data.symbol)
            if not existing_symbol:
                saved_symbols.append(crud_symbol_cache.create(db, obj_in=symbol_data))
            else:
                # Update existing if needed (e.g., last_fetched_at) - for now, just append
                saved_symbols.append(existing_symbol)

        logger.info(f"Fetched and cached {len(saved_symbols)} new symbols for '{query}' (type: {instrument_type})")
        return saved_symbols

data_service = DataService()