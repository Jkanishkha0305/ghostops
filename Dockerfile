FROM python:3.12-slim

WORKDIR /app

# Install only the backend dependencies (no desktop extras like PyAudio/mss/Pillow)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
