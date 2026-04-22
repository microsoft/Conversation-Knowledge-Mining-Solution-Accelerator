FROM python:3.13-slim

WORKDIR /app
COPY backend/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY Sample_Data/ ./Sample_Data/
COPY .env* ./

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
