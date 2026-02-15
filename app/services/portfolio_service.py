import logging
from datetime import date
from typing import Dict, Optional, List
from uuid import UUID
from collections import defaultdict

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db.models import Transaction, User, Instrument
from app.crud.transaction import transaction as crud_transaction

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for calculating portfolio holdings and metrics from transactions."""
    
    def get_current_holdings(
        self,
        db: Session,
        user: User,
        instrument_symbol: Optional[str] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate current holdings from transaction history.
        
        Args:
            db: Database session
            user: Current user
            instrument_symbol: Optional filter by specific instrument
            as_of_date: Optional date to calculate holdings as of (default: today)
            
        Returns:
            Dictionary mapping symbol to holdings:
            {
                "NIFTYBEES": {
                    "units": 150.5,
                    "avg_price": 95.24,
                    "total_invested": 14332.82,
                    "instrument_id": "uuid"
                }
            }
        """
        try:
            if as_of_date is None:
                as_of_date = date.today()
            
            # Get all transactions up to as_of_date
            query = (
                db.query(Transaction)
                .join(Instrument)
                .filter(
                    and_(
                        Transaction.user_id == user.id,
                        Transaction.transaction_date <= as_of_date
                    )
                )
            )
            
            if instrument_symbol:
                query = query.filter(Instrument.symbol == instrument_symbol.upper())
            
            transactions = query.order_by(Transaction.transaction_date.asc()).all()
            
            # Calculate holdings by instrument
            holdings = defaultdict(lambda: {
                'units': 0.0,
                'total_invested': 0.0,
                'total_cost': 0.0,  # Including fees
                'instrument_id': None,
                'symbol': None
            })
            
            for txn in transactions:
                symbol = txn.instrument.symbol
                
                if holdings[symbol]['instrument_id'] is None:
                    holdings[symbol]['instrument_id'] = str(txn.instrument_id)
                    holdings[symbol]['symbol'] = symbol
                
                if txn.transaction_type in ['BUY', 'SIP', 'DIP_BUY']:
                    # Buy transactions - increase units and cost
                    holdings[symbol]['units'] += float(txn.quantity)
                    holdings[symbol]['total_invested'] += float(txn.amount)
                    holdings[symbol]['total_cost'] += float(txn.amount) + float(txn.fees)
                
                elif txn.transaction_type == 'SELL':
                    # Sell transactions - decrease units
                    holdings[symbol]['units'] -= float(txn.quantity)
                    # Proportionally reduce invested amount
                    if holdings[symbol]['units'] > 0:
                        sell_ratio = float(txn.quantity) / (holdings[symbol]['units'] + float(txn.quantity))
                        holdings[symbol]['total_invested'] *= (1 - sell_ratio)
                        holdings[symbol]['total_cost'] *= (1 - sell_ratio)
            
            # Calculate average price and filter out zero holdings
            result = {}
            for symbol, data in holdings.items():
                if data['units'] > 0.01:  # Filter out negligible holdings
                    result[symbol] = {
                        'units': data['units'],
                        'avg_price': data['total_cost'] / data['units'] if data['units'] > 0 else 0.0,
                        'total_invested': data['total_invested'],
                        'instrument_id': data['instrument_id']
                    }
            
            logger.info(f"Calculated holdings for user {user.email}: {len(result)} instruments")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating holdings: {e}", exc_info=True)
            return {}
    
    def get_cash_balance(
        self,
        db: Session,
        user: User,
        as_of_date: Optional[date] = None
    ) -> float:
        """
        Calculate cash balance from transactions.
        
        This is a simplified calculation. In a real system, you'd track
        cash deposits and withdrawals separately.
        
        Args:
            db: Database session
            user: Current user
            as_of_date: Optional date to calculate balance as of
            
        Returns:
            Cash balance (negative means invested)
        """
        try:
            if as_of_date is None:
                as_of_date = date.today()
            
            # Get all transactions
            query = db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_date <= as_of_date
                )
            )
            
            transactions = query.all()
            
            cash_balance = 0.0
            
            for txn in transactions:
                if txn.transaction_type in ['BUY', 'SIP', 'DIP_BUY']:
                    # Purchases reduce cash
                    cash_balance -= float(txn.amount) + float(txn.fees)
                elif txn.transaction_type == 'SELL':
                    # Sales increase cash
                    cash_balance += float(txn.amount) - float(txn.fees)
                elif txn.transaction_type == 'DIVIDEND':
                    # Dividends increase cash
                    cash_balance += float(txn.amount)
            
            return cash_balance
            
        except Exception as e:
            logger.error(f"Error calculating cash balance: {e}", exc_info=True)
            return 0.0
    
    def get_portfolio_summary(
        self,
        db: Session,
        user: User,
        as_of_date: Optional[date] = None
    ) -> Dict[str, any]:
        """
        Get complete portfolio summary.
        
        Args:
            db: Database session
            user: Current user
            as_of_date: Optional date for calculation
            
        Returns:
            Dictionary with portfolio summary
        """
        try:
            holdings = self.get_current_holdings(db, user, as_of_date=as_of_date)
            cash_balance = self.get_cash_balance(db, user, as_of_date=as_of_date)
            
            total_invested = sum(h['total_invested'] for h in holdings.values())
            total_units = sum(h['units'] for h in holdings.values())
            
            return {
                "holdings": holdings,
                "cash_balance": cash_balance,
                "total_invested": total_invested,
                "num_instruments": len(holdings),
                "total_units": total_units,
                "as_of_date": as_of_date or date.today()
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}", exc_info=True)
            return {
                "holdings": {},
                "cash_balance": 0.0,
                "total_invested": 0.0,
                "num_instruments": 0,
                "total_units": 0.0,
                "as_of_date": as_of_date or date.today()
            }


portfolio_service = PortfolioService()