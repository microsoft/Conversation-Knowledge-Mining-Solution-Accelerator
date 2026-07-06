FROM python:3.11-alpine

# Install system dependencies required for building and running the application
RUN apk add --no-cache \
    ca-certificates \
    && apk add --no-cache --virtual .build-deps \
    build-base \
    libffi-dev \
    openssl-dev \
    curl \
    unixodbc-dev \
    libpq \
    opus-dev \
    libvpx-dev \
    && update-ca-certificates

# Download and install Microsoft ODBC Driver 18 and MSSQL tools (latest release)
# Per Microsoft docs (Alpine, ODBC 18):
# https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
RUN case $(uname -m) in \
        x86_64) architecture="amd64" ;; \
        arm64) architecture="arm64" ;; \
        *) architecture="unsupported" ;; \
    esac \
    && if [ "unsupported" = "$architecture" ]; then \
        echo "Alpine architecture $(uname -m) is not currently supported."; \
        exit 1; \
    fi \
    && curl -O --fail --retry 5 --location --retry-delay 5 https://download.microsoft.com/download/0b3d5518-b4a7-4a2b-afc7-7ee9e967f93c/msodbcsql18_18.6.2.1-1_$architecture.apk \
    && curl -O --fail --retry 5 --location --retry-delay 5 https://download.microsoft.com/download/cad0d30f-b9b1-4765-a011-81d8a66c8b8d/mssql-tools18_18.6.2.1-1_$architecture.apk \
    && apk add --allow-untrusted msodbcsql18_18.6.2.1-1_$architecture.apk \
    && apk add --allow-untrusted mssql-tools18_18.6.2.1-1_$architecture.apk \
    && rm msodbcsql18_18.6.2.1-1_$architecture.apk mssql-tools18_18.6.2.1-1_$architecture.apk

# Set the working directory inside the container
WORKDIR /app

# Copy only the requirements file first to leverage Docker layer caching
COPY ./requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \ 
    && pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache

# Copy the backend application code into the container
COPY ./ .

# Expose port 80 for incoming traffic
EXPOSE 80

# Start the application using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]