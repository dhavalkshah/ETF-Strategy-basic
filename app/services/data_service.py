import logging
import time
import os
from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd
import requests
import yfinance as yf
from jugaad_data.nse import bhavcopy_save
from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.crud.historical_price import historical_price as crud_historical_price
from app.crud.symbol_cache import symbol_cache as crud_symbol_cache
from app.db.models import Instrument, HistoricalPrice, SymbolCache
from app.schemas.instrument import InstrumentCreate, HistoricalPriceCreate, SymbolCacheCreate

logger = logging.getLogger(__name__)


# Yahoo Finance configurations
YAHOO_SUFFIX = {
    "EQUITY": ".NS",
    "ETF": ".NS",
    "INDEX": "",
    "MF": ""
}

YAHOO_INDEX_MAPPING = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY NEXT 50": "NIFTYJR-BE.NS",
    "NIFTY 100": "^CNX100",
    "NIFTY 200": "^CNX200",
    "NIFTY 500": "^CNX500",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY FINANCIAL SERVICES": "NIFTY_FIN_SERVICE.NS",
}

# ETF mappings for search
ETF_NAME_MAPPING = {
    "ITBEES": "Nippon India ETF Nifty IT",
    "BANKBEES": "Nippon India ETF Nifty Bank",
    "NIFTYBEES": "Nippon India ETF Nifty 50",
    "JUNIORBEES": "Nippon India ETF Nifty Next 50",
    "GOLDBEES": "Nippon India ETF Gold",
    "LIQUIDBEES": "Nippon India ETF Liquid",
    "SETFNIF50": "SBI ETF Nifty 50",
    "SETFNN50": "SBI ETF Nifty Next 50",
    "ICICIB22": "ICICI Prudential Nifty Next 50 ETF",
    "KOTAKBKETF": "Kotak Nifty Bank ETF",
    "ICICIBANKN": "ICICI Prudential Nifty Bank ETF",
    "HDFCNIF50": "HDFC Nifty 50 ETF",
    "MON100": "Motilal Oswal Nifty Midcap 150 ETF",
    "MOM30": "Motilal Oswal Nifty Midcap 150 Momentum 50 ETF",
}

# NSE Indices for search
NSE_INDICES = [
    "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 50",
    "NIFTY SMALLCAP 100", "NIFTY SMALLCAP 250", "NIFTY NEXT 50",
    "NIFTY AUTO", "NIFTY PHARMA", "NIFTY FMCG", "NIFTY METAL",
    "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA", "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK", "NIFTY FINANCIAL SERVICES"
]


class DataService:
    """
    Hybrid data service:
    - yfinance for historical data (fast, reliable)
    - jugaad-data for search/bhavcopy (comprehensive)
    - MFAPI for mutual funds
    """
    
    async def get_historical_data(
        self,
        db: Session,
        symbol: str,
        instrument_type: str,
        start_date: date,
        end_date: date
    ) -> List[HistoricalPrice]:
        """Fetches historical data for a given instrument with caching."""
        
        fetch_start = time.time()
        logger.info(f"DATA SERVICE: Fetching {symbol} ({instrument_type}) from {start_date} to {end_date}")
        
        # Get/Create instrument
        db_instrument = crud_instrument.get_by_symbol(db, symbol)
        if not db_instrument:
            instrument_create = InstrumentCreate(
                symbol=symbol,
                name=f"{symbol}",
                instrument_type=instrument_type
            )
            db_instrument = crud_instrument.create(db, obj_in=instrument_create)
            logger.info(f"  Created new instrument")

        # Check cache
        cached_data = crud_historical_price.get_historical_prices_for_instrument(
            db, db_instrument.id, start_date, end_date
        )
        logger.info(f"  Cache: Found {len(cached_data)} records")

        # FIXED: Calculate expected trading days properly
        # Don't use calendar days - market trades ~250 days/year
        total_days = (end_date - start_date).days
        # Rough estimate: 5/7 days are trading days minus holidays (~10 days/year)
        expected_trading_days = int(total_days * (5/7) * (355/365))
        
        if cached_data:
            cache_coverage = len(cached_data) / max(expected_trading_days, 1)
            logger.info(f"  Cache coverage: {cache_coverage*100:.1f}% ({len(cached_data)}/{expected_trading_days} expected trading days)")
            
            # If we have good coverage (>60%), use cache
            if cache_coverage > 0.6:
                logger.info(f"  CACHE HIT: Returning {len(cached_data)} cached records")
                return cached_data

        logger.info(f"  CACHE MISS: Fetching from external source")

        # Fetch from external source
        new_data: List[HistoricalPriceCreate] = []
        
        if instrument_type == "MF":
            logger.info(f"  Using MFAPI...")
            new_data = await self._fetch_mfapi_history_data(symbol, start_date, end_date)
        else:
            logger.info(f"  Using yfinance for {instrument_type}...")
            new_data = await self._fetch_yfinance_data(symbol, instrument_type, start_date, end_date)
        
        logger.info(f"  External fetch: Got {len(new_data)} records")

        # FIXED: Better duplicate prevention
        if not new_data:
            # No new data from source, return what we have in cache
            logger.info(f"  No new data from source, returning cached data")
            return cached_data
        
        # Filter out dates that already exist in cache
        dates_in_cache = {hp.date for hp in cached_data}
        to_save = [d for d in new_data if d.date not in dates_in_cache]
        
        logger.info(f"  To save: {len(to_save)} records (filtered {len(new_data) - len(to_save)} duplicates)")

        if to_save:
            try:
                saved_data = crud_historical_price.create_multi(db, to_save, db_instrument.id)
                logger.info(f"  DB save: Saved {len(saved_data)} new records")
                all_data = sorted(cached_data + saved_data, key=lambda x: x.date)
            except Exception as e:
                # If save fails (e.g., duplicate key), log and return cached + new data
                logger.error(f"  Error saving to DB: {e}")
                # Return cached data (it's still valid)
                return cached_data if cached_data else []
        else:
            all_data = cached_data

        total_time = time.time() - fetch_start
        logger.info(f"  TOTAL: {total_time:.2f}s - Returning {len(all_data)} records")
        return all_data

    async def _fetch_yfinance_data(
        self,
        symbol: str,
        instrument_type: str,
        start_date: date,
        end_date: date
    ) -> List[HistoricalPriceCreate]:
        """Fetches historical data from Yahoo Finance (FAST)."""
        try:
            yahoo_symbol = self._convert_to_yahoo_symbol(symbol, instrument_type)
            logger.info(f"    Yahoo symbol: {yahoo_symbol}")
            
            api_start = time.time()
            end_date_exclusive = end_date + timedelta(days=1)
            
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(
                start=start_date,
                end=end_date_exclusive,
                auto_adjust=False
            )
            
            api_time = time.time() - api_start
            logger.info(f"    yfinance API: {api_time:.2f}s")
            
            if df is None or df.empty:
                logger.warning(f"    No data from yfinance")
                return []

            historical_prices = []
            for date_idx, row in df.iterrows():
                try:
                    if isinstance(date_idx, pd.Timestamp):
                        record_date = date_idx.date()
                    else:
                        record_date = pd.to_datetime(date_idx).date()
                    
                    if record_date < start_date or record_date > end_date:
                        continue
                    
                    historical_prices.append(HistoricalPriceCreate(
                        date=record_date,
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        adjusted_close=float(row['Close']),
                        volume=int(row['Volume']) if not pd.isna(row['Volume']) else 0
                    ))
                except Exception as e:
                    logger.warning(f"    Error parsing row: {e}")
                    continue
            
            logger.info(f"    Parsed {len(historical_prices)} records")
            return historical_prices
            
        except Exception as e:
            logger.error(f"    yfinance error: {e}")
            return []

    def _convert_to_yahoo_symbol(self, symbol: str, instrument_type: str) -> str:
        """Convert NSE symbol to Yahoo Finance format."""
        if instrument_type == "INDEX":
            if symbol in YAHOO_INDEX_MAPPING:
                return YAHOO_INDEX_MAPPING[symbol]
            return f"^{symbol.replace(' ', '')}"
        else:
            suffix = YAHOO_SUFFIX.get(instrument_type, ".NS")
            return f"{symbol}{suffix}"

    async def _fetch_mfapi_history_data(
        self, mf_code: str, start_date: date, end_date: date
    ) -> List[HistoricalPriceCreate]:
        """Fetches NAV data from MFAPI."""
        url = f"https://api.mfapi.in/mf/{mf_code}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "SUCCESS" or not data.get("data"):
                return []

            historical_prices = []
            for record in data["data"]:
                try:
                    record_date = datetime.strptime(record["date"], "%d-%m-%Y").date()
                    if start_date <= record_date <= end_date:
                        nav_value = float(record["nav"])
                        historical_prices.append(HistoricalPriceCreate(
                            date=record_date,
                            open=nav_value,
                            high=nav_value,
                            low=nav_value,
                            close=nav_value,
                            adjusted_close=nav_value,
                            volume=0
                        ))
                except (KeyError, ValueError):
                    continue
            
            historical_prices.sort(key=lambda x: x.date)
            logger.info(f"    MFAPI: {len(historical_prices)} records")
            return historical_prices
            
        except Exception as e:
            logger.error(f"    MFAPI error: {e}")
            return []

    # ============================================================================
    # SEARCH FUNCTIONALITY - Uses jugaad-data bhavcopy (comprehensive)
    # ============================================================================

    async def search_and_cache_symbols(
        self,
        db: Session,
        query: str,
        instrument_type: Optional[str] = None
    ) -> List[SymbolCache]:
        """
        Search using jugaad-data bhavcopy for comprehensive results.
        This is separate from historical data fetching.
        """
        
        # Check cache first
        cached_symbols = crud_symbol_cache.get_multi_by_partial_symbol(db, query)
        if instrument_type:
            cached_symbols = [s for s in cached_symbols if s.instrument_type == instrument_type]

        if cached_symbols:
            logger.info(f"Returning {len(cached_symbols)} cached symbols")
            return cached_symbols

        logger.info(f"Cache miss - searching for '{query}'")
        
        live_symbols: List[SymbolCacheCreate] = []

        # Search based on instrument type
        if instrument_type == "INDEX":
            live_symbols.extend(await self._search_nse_indices(query))
        elif instrument_type == "ETF":
            live_symbols.extend(await self._search_etfs_by_name(query))
            live_symbols.extend(await self._search_etfs_from_bhavcopy(query))
        elif instrument_type == "EQUITY":
            live_symbols.extend(await self._search_equities_from_bhavcopy(query))
        elif instrument_type == "MF":
            live_symbols.extend(await self._fetch_mfapi_symbols(query))
        else:
            # Search all
            live_symbols.extend(await self._search_nse_indices(query))
            live_symbols.extend(await self._search_etfs_by_name(query))
            live_symbols.extend(await self._search_equities_from_bhavcopy(query))
            live_symbols.extend(await self._fetch_mfapi_symbols(query))

        # Remove duplicates
        seen = set()
        unique_symbols = []
        for sym in live_symbols:
            if sym.symbol not in seen:
                seen.add(sym.symbol)
                unique_symbols.append(sym)

        # Cache results
        saved_symbols = []
        for symbol_data in unique_symbols:
            try:
                existing = crud_symbol_cache.get_by_symbol(db, symbol_data.symbol)
                if not existing:
                    saved = crud_symbol_cache.create(db, obj_in=symbol_data)
                    saved_symbols.append(saved)
                else:
                    saved_symbols.append(existing)
            except Exception as e:
                logger.error(f"Error caching: {e}")
                continue

        logger.info(f"Found {len(saved_symbols)} symbols")
        return saved_symbols

    async def _search_nse_indices(self, query: str) -> List[SymbolCacheCreate]:
        """Search in predefined index list."""
        results = []
        query_upper = query.upper()
        for idx in NSE_INDICES:
            if query_upper in idx:
                results.append(SymbolCacheCreate(
                    symbol=idx,
                    name=idx,
                    instrument_type="INDEX",
                    source="Index_List"
                ))
        return results

    async def _search_etfs_by_name(self, query: str) -> List[SymbolCacheCreate]:
        """Search ETFs by name in mapping."""
        results = []
        query_lower = query.lower()
        for symbol, name in ETF_NAME_MAPPING.items():
            if query_lower in name.lower() or query_lower in symbol.lower():
                results.append(SymbolCacheCreate(
                    symbol=symbol,
                    name=name,
                    instrument_type="ETF",
                    source="ETF_Mapping"
                ))
        return results

    async def _search_etfs_from_bhavcopy(self, query: str) -> List[SymbolCacheCreate]:
        """Search ETFs from bhavcopy."""
        return await self._search_from_bhavcopy(query, "ETF")

    async def _search_equities_from_bhavcopy(self, query: str) -> List[SymbolCacheCreate]:
        """Search equities from bhavcopy."""
        return await self._search_from_bhavcopy(query, "EQUITY")

    async def _search_from_bhavcopy(self, query: str, target_type: str) -> List[SymbolCacheCreate]:
        """
        Search from NSE bhavcopy using jugaad-data.
        This is only used for SEARCH, not for historical data.
        """
        results = []
        try:
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            bhavcopy_date = date.today()
            bhavcopy_df = None
            
            # Try last 5 days
            for _ in range(5):
                try:
                    filepath = bhavcopy_save(bhavcopy_date, temp_dir)
                    if filepath and os.path.exists(filepath):
                        bhavcopy_df = pd.read_csv(filepath)
                        break
                except Exception:
                    bhavcopy_date = bhavcopy_date - timedelta(days=1)
            
            if bhavcopy_df is None or bhavcopy_df.empty:
                logger.warning(f"Could not fetch bhavcopy")
                return results

            # Filter for equity series
            equity_df = bhavcopy_df[bhavcopy_df['SERIES'] == 'EQ']
            
            # Search by symbol
            query_upper = query.upper()
            matching = equity_df[equity_df['SYMBOL'].str.contains(query_upper, na=False, case=False)]

            for _, row in matching.head(50).iterrows():
                symbol = row['SYMBOL']
                
                # Determine type
                if target_type == "ETF":
                    if "BEES" in symbol or "ETF" in symbol or symbol in ETF_NAME_MAPPING:
                        name = ETF_NAME_MAPPING.get(symbol, symbol)
                        results.append(SymbolCacheCreate(
                            symbol=symbol,
                            name=name,
                            instrument_type="ETF",
                            source="NSE_Bhavcopy"
                        ))
                else:  # EQUITY
                    if "BEES" not in symbol and "ETF" not in symbol:
                        results.append(SymbolCacheCreate(
                            symbol=symbol,
                            name=symbol,
                            instrument_type="EQUITY",
                            source="NSE_Bhavcopy"
                        ))

            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            logger.error(f"Bhavcopy search error: {e}")
        
        return results

    async def _fetch_mfapi_symbols(self, query: str) -> List[SymbolCacheCreate]:
        """Search mutual funds via MFAPI."""
        results = []
        try:
            response = requests.get(f"https://api.mfapi.in/mf/search?q={query}", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                for item in data[:50]:
                    try:
                        results.append(SymbolCacheCreate(
                            symbol=str(item["schemeCode"]),
                            name=item["schemeName"],
                            instrument_type="MF",
                            source="MFAPI"
                        ))
                    except KeyError:
                        continue
        except Exception as e:
            logger.error(f"MFAPI search error: {e}")
        
        return results


data_service = DataService()