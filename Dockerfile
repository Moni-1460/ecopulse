FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the project
COPY backend ./backend
COPY frontend ./frontend

WORKDIR /app/backend

# Persisted SQLite data lives here; mount a volume at /app/backend/data in
# production so posts survive container restarts.
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
