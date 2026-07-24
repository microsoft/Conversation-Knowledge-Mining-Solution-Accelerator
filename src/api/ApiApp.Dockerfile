FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install ODBC driver for SQL Server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 unixodbc-dev && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./src/api/
RUN pip install --no-cache-dir --root-user-action=ignore -r src/api/requirements.txt

# Build context is ./src/api — recreate the src.api package layout
COPY . ./src/api/
RUN touch src/__init__.py

# Non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
