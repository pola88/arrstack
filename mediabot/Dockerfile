FROM python:3.12-slim-bookworm

# ARM64-compatible — works natively on Raspberry Pi 4 64-bit
WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser /app
USER botuser

CMD ["python", "-m", "bot.main"]
