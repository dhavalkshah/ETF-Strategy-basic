"""Add EQUITY instrument type and DIP_BUY transaction type

Revision ID: f7c0c53066eb
Revises: a1b2c3d4e5f6
Create Date: 2024-02-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7c0c53066eb'
down_revision = 'a1b2c3d4e5f6'  # Replace with your last migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Add EQUITY to instrument_type_enum and DIP_BUY to transaction_type_enum."""
    
    # Add EQUITY to instrument_type_enum
    op.execute("ALTER TYPE instrument_type_enum ADD VALUE IF NOT EXISTS 'EQUITY'")
    op.execute("ALTER TYPE instrument_type_enum ADD VALUE IF NOT EXISTS 'INDEX'")
    
    # Add EQUITY to symbol_instrument_type_enum (for SymbolCache)
    op.execute("ALTER TYPE symbol_instrument_type_enum ADD VALUE IF NOT EXISTS 'EQUITY'")
    
    # Add DIP_BUY to transaction_type_enum
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'DIP_BUY'")


def downgrade():
    """
    Note: PostgreSQL does not support removing values from enums.
    To downgrade, you would need to:
    1. Create a new enum without the values
    2. Alter all columns to use the new enum
    3. Drop the old enum
    
    This is complex and risky, so we don't provide automatic downgrade.
    Manual intervention required if downgrade is needed.
    """
    pass