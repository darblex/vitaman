FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for JSON storage
RUN mkdir -p /app/data/backups

CMD ["python", "bot_new.py"]
