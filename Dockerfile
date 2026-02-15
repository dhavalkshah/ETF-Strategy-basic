FROM python:3.11-slim

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps for psycopg2 + bcrypt
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install packages in specific order to avoid conflicts
RUN pip install --upgrade pip && \
    # Install all normal dependencies first (includes yfinance with beautifulsoup4>=4.11.1)
    pip install --no-cache-dir -r requirements.txt && \
    # Then force install jugaad-data ignoring dependency conflicts
    pip install --no-cache-dir --no-deps jugaad-data==0.29

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]