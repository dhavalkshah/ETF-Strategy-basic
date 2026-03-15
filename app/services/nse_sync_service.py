import logging
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.crud.historical_price import historical_price as crud_historical_price
from app.schemas.instrument import HistoricalPriceCreate

logger = logging.getLogger(__name__)


class NSEDataSyncService:
    """
    Service to sync historical data from NSE for indices and ETFs.
    Updates database with latest available data.
    """
    
    # NSE API endpoints
    INDEX_URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
    ETF_URL = "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi"
    
    # Headers for NSE requests
    INDEX_HEADERS = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.niftyindices.com/reports/historical-data'
    }
    
    ETF_HEADERS = {
        'accept': '*/*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    def __init__(self):
        self.session = requests.Session()
    
    def sync_all_instruments(
        self,
        db: Session,
        lookback_days: int = 30
    ) -> Dict[str, any]:
        """
        Sync data for all instruments in database.
        
        Args:
            db: Database session
            lookback_days: Number of days to look back for updates
            
        Returns:
            Summary of sync operation
        """
        start_time = time.time()
        logger.info(f"=" * 80)
        logger.info(f"NSE DATA SYNC START")
        logger.info(f"Lookback: {lookback_days} days")
        logger.info(f"=" * 80)
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Get all instruments from database
        indices = crud_instrument.get_multi_by_type(db, instrument_type="INDEX", limit=1000)
        etfs = crud_instrument.get_multi_by_type(db, instrument_type="ETF", limit=1000)
        equities = crud_instrument.get_multi_by_type(db, instrument_type="EQUITY", limit=1000)
        
        logger.info(f"Found {len(indices)} indices, {len(etfs)} ETFs, {len(equities)} equities")
        
        results = {
            'total_instruments': len(indices) + len(etfs) + len(equities),
            'indices_synced': 0,
            'etfs_synced': 0,
            'equities_synced': 0,
            'total_records_added': 0,
            'errors': []
        }
        
        # Sync indices
        logger.info(f"\n--- Syncing {len(indices)} Indices ---")
        for instrument in indices:
            try:
                records_added = self._sync_index(db, instrument.symbol, start_date, end_date)
                results['indices_synced'] += 1
                results['total_records_added'] += records_added
                logger.info(f"✓ {instrument.symbol}: {records_added} records")
            except Exception as e:
                logger.error(f"✗ {instrument.symbol}: {e}")
                results['errors'].append(f"INDEX {instrument.symbol}: {str(e)}")
        
        # Sync ETFs
        logger.info(f"\n--- Syncing {len(etfs)} ETFs ---")
        for instrument in etfs:
            try:
                records_added = self._sync_etf(db, instrument.symbol, start_date, end_date)
                results['etfs_synced'] += 1
                results['total_records_added'] += records_added
                logger.info(f"✓ {instrument.symbol}: {records_added} records")
            except Exception as e:
                logger.error(f"✗ {instrument.symbol}: {e}")
                results['errors'].append(f"ETF {instrument.symbol}: {str(e)}")
        
        # Sync Equities
        logger.info(f"\n--- Syncing {len(equities)} Equities ---")
        for instrument in equities:
            try:
                records_added = self._sync_etf(db, instrument.symbol, start_date, end_date)
                results['equities_synced'] += 1
                results['total_records_added'] += records_added
                logger.info(f"✓ {instrument.symbol}: {records_added} records")
            except Exception as e:
                logger.error(f"✗ {instrument.symbol}: {e}")
                results['errors'].append(f"EQUITY {instrument.symbol}: {str(e)}")
        
        total_time = time.time() - start_time
        
        logger.info(f"=" * 80)
        logger.info(f"NSE DATA SYNC COMPLETE in {total_time:.2f}s")
        logger.info(f"Instruments synced: {results['indices_synced'] + results['etfs_synced'] + results['equities_synced']}/{results['total_instruments']}")
        logger.info(f"Total records added: {results['total_records_added']}")
        logger.info(f"Errors: {len(results['errors'])}")
        logger.info(f"=" * 80)
        
        results['duration_seconds'] = round(total_time, 2)
        return results
    
    def _sync_index(
        self,
        db: Session,
        index_name: str,
        start_date: date,
        end_date: date
    ) -> int:
        """Sync single index data from NSE."""
        # Get instrument
        instrument = crud_instrument.get_by_symbol(db, index_name)
        if not instrument:
            raise ValueError(f"Index {index_name} not found in database")
        
        # Fetch from NSE
        data = self._fetch_index_data(index_name, start_date, end_date)
        # data.date is in datetime.datetime format converting into datetime.date format
        for rec in data:
            if isinstance(rec.date, datetime):
                rec.date = rec.date.date()
        api_dates = {rec.date for rec in data}
        if not data:
            return 0
        
        # Get existing dates from database
        existing_data = crud_historical_price.get_historical_prices_for_instrument(
            db, instrument.id, start_date, end_date
        )
        existing_dates = {hp.date for hp in existing_data}
        
        # Filter new records
        new_records = [rec for rec in data if rec.date not in existing_dates]
        
        if not new_records:
            return 0
        
        # Save to database
        saved = crud_historical_price.create_multi(db, new_records, instrument.id)
        return len(saved)
    
    def _sync_etf(
        self,
        db: Session,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> int:
        """Sync single ETF/Equity data from NSE."""
        # Get instrument
        instrument = crud_instrument.get_by_symbol(db, symbol)
        if not instrument:
            raise ValueError(f"Symbol {symbol} not found in database")
        
        # Fetch from NSE
        data = self._fetch_etf_data(symbol, start_date, end_date)
        for rec in data:
            if isinstance(rec.date, datetime):
                rec.date = rec.date.date()
        
        if not data:
            return 0
        
        # Get existing dates
        existing_data = crud_historical_price.get_historical_prices_for_instrument(
            db, instrument.id, start_date, end_date
        )
        existing_dates = {hp.date for hp in existing_data}
        
        # Filter new records
        new_records = [rec for rec in data if rec.date not in existing_dates]
        
        if not new_records:
            return 0
        
        # Save to database
        saved = crud_historical_price.create_multi(db, new_records, instrument.id)
        return len(saved)
    
    def _fetch_index_data(
        self,
        index_name: str,
        start_date: date,
        end_date: date
    ) -> List[HistoricalPriceCreate]:
        """Fetch index data from NSE Indices API."""
        try:
            # Format dates for API (dd-MMM-yyyy format)
            from_date_str = start_date.strftime("%d-%b-%Y")
            to_date_str = end_date.strftime("%d-%b-%Y")
            
            # Prepare request payload
            payload = {
                "cinfo": str({
                    'name': index_name,
                    'startDate': from_date_str,
                    'endDate': to_date_str,
                    'indexName': index_name
                })
            }
            
            # Make request
            response = self.session.post(
                self.INDEX_URL,
                headers=self.INDEX_HEADERS,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Parse response
            # NSE returns: {"d": "[{\"EOD_INDEX_NAME\":\"...\", \"EOD_OPEN_INDEX_VAL\":\"...\", ...}]"}
            if 'd' not in result:
                logger.warning(f"Unexpected response format for {index_name}")
                return []
            
            import json
            data_str = result['d']
            data_list = json.loads(data_str)
            
            records = []
            for item in data_list:
                try:
                    # Parse date (format: "31-Dec-2024")
                    record_date = datetime.strptime(item['HistoricalDate'], "%d %b %Y").date()
                    
                    records.append(HistoricalPriceCreate(
                        date=record_date,
                        open=float(item['OPEN']),
                        high=float(item['HIGH']),
                        low=float(item['LOW']),
                        close=float(item['CLOSE']),
                        adjusted_close=float(item['CLOSE']),
                        volume=0  # Indices don't have volume
                    ))
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error parsing index record: {e}")
                    continue
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching index {index_name}: {e}")
            raise
    
    def _fetch_etf_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[HistoricalPriceCreate]:
        """Fetch ETF/Equity data from NSE API."""
        try:
            # Format dates for API (dd-MM-yyyy format)
            from_date_str = start_date.strftime("%d-%m-%Y")
            to_date_str = end_date.strftime("%d-%m-%Y")
            
            # Build URL with query parameters
            url = (
                f"{self.ETF_URL}?"
                f"functionName=getHistoricalTradeData&"
                f"symbol={symbol}&"
                f"series=EQ&"
                f"fromDate={from_date_str}&"
                f"toDate={to_date_str}"
            )
            
            # Update referer for this specific symbol
            headers = self.ETF_HEADERS.copy()
            headers['referer'] = f"https://www.nseindia.com/get-quote/equity/{symbol}"
            
            # Make request
            response = self.session.get(
                url,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not isinstance(data, list):
                logger.warning(f"Unexpected response format for {symbol}")
                return []
            
            records = []
            for item in data:
                try:
                    # Parse timestamp (format: "31-DEC-2024")
                    record_date = datetime.strptime(item['mtimestamp'], "%d-%b-%Y").date()
                    
                    records.append(HistoricalPriceCreate(
                        date=record_date,
                        open=float(item['chOpeningPrice']),
                        high=float(item['chTradeHighPrice']),
                        low=float(item['chTradeLowPrice']),
                        close=float(item['chClosingPrice']),
                        adjusted_close=float(item['chClosingPrice']),
                        volume=int(item['chTotTradedQty'])
                    ))
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error parsing ETF record: {e}")
                    continue
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching ETF {symbol}: {e}")
            raise


nse_sync_service = NSEDataSyncService()