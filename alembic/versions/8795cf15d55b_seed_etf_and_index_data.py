"""
Seed ETF and Index data

Revision ID: 8795cf15d55b
Revises: f7c0c53066eb
Create Date: 2026-03-02 16:13:02.089603
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import uuid
import csv
from datetime import datetime
from app.db.models import Instrument, HistoricalPrice

# revision identifiers
revision = "8795cf15d55b"
down_revision = "f7c0c53066eb"
branch_labels = None
depends_on = None


def clean_headers(reader):
    """Normalize CSV headers by stripping whitespace, quotes, and BOM."""
    normalized = []
    for h in reader.fieldnames:
        if h is None:
            continue
        h = h.strip().strip('"').lstrip("\ufeff")
        normalized.append(h)
    reader.fieldnames = normalized
    return reader


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    # --- Seed Instruments from ETF CSV ---
    with open("./app/seed_data/MW-ETF-02-Mar-2026_1.csv", newline="") as f:
        reader = clean_headers(csv.DictReader(f))
        print("ETF headers:", reader.fieldnames)  # debug
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip()
            if not symbol:
                continue
            name = row.get("ETF_NAME")

            instrument = session.query(Instrument).filter_by(symbol=symbol).first()
            if not instrument:
                instrument = Instrument(
                    id=uuid.uuid4(),
                    symbol=symbol,
                    name=name,
                    instrument_type="ETF",
                )
                session.add(instrument)
    print("Finished seeding instruments")  # debug

    # --- Seed Instruments from Index CSV ---
    with open("./app/seed_data/MW-All-Indices-02-Mar-2026_1.csv", newline="") as f:
        reader = clean_headers(csv.DictReader(f))
        print("Index headers:", reader.fieldnames)  # debug
        for row in reader:
            index_name = (row.get("INDEX") or "").strip()
            if not index_name:
                continue
            instrument = session.query(Instrument).filter_by(symbol=index_name).first()
            if not instrument:
                instrument = Instrument(
                    id=uuid.uuid4(),
                    symbol=index_name,
                    name=index_name,
                    instrument_type="INDEX",
                )
                session.add(instrument)
    print("Finished seeding indices")  # debug

    session.commit()

    # --- Seed Historical Prices for ETFs ---
    with open("./app/seed_data/ETF_5yr_history_2.csv", newline="") as f:
        reader = clean_headers(csv.DictReader(f))
        print("ETF history headers:", reader.fieldnames)  # debug
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip()
            if not symbol:
                continue
            instrument = session.query(Instrument).filter_by(symbol=symbol).first()
            if not instrument:
                continue

            try:
                date = datetime.strptime(row["DATE"], "%d-%b-%Y").date()
            except Exception:
                continue

            hp = HistoricalPrice(
                id=uuid.uuid4(),
                instrument_id=instrument.id,
                date=date,
                open=row.get("OPEN"),
                high=row.get("HIGH"),
                low=row.get("LOW"),
                close=row.get("CLOSE"),
                adjusted_close=row.get("CLOSE"),
                volume=row.get("VOLUME") or None,
            )
            session.merge(hp)

    print("Finished seeding ETF historical prices")  # debug

    # --- Seed Historical Prices for Indices ---
    with open("./app/seed_data/Index_5yr_history_1.csv", newline="") as f:
        reader = clean_headers(csv.DictReader(f))
        print("Index history headers:", reader.fieldnames)  # debug
        for row in reader:
            # print("Processing index row:", row)  # debug
            index_name = (row.get("INDEX_NAME") or "").strip()
            if not index_name:
                continue
            instrument = session.query(Instrument).filter_by(symbol=index_name.upper()).first()
            if not instrument:
                continue

            try:
                date = datetime.strptime(row["DATE"], "%d %b %Y").date()
            except Exception:
                print(f"Error parsing date for index {index_name}")  # debug
                continue

            hp = HistoricalPrice(
                id=uuid.uuid4(),
                instrument_id=instrument.id,
                date=date,
                open=row.get("OPEN"),
                high=row.get("HIGH"),
                low=row.get("LOW"),
                close=row.get("CLOSE"),
                adjusted_close=row.get("CLOSE"),
                volume=None,
            )
            session.merge(hp)
    print("Finished seeding index historical prices")  # debug

    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session.execute(sa.text("DELETE FROM historical_prices"))
    session.execute(sa.text("DELETE FROM instruments WHERE instrument_type IN ('ETF','INDEX')"))
    session.commit()