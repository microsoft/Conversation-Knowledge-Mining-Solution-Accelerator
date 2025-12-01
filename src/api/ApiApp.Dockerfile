FROM python:3.11-alpine

# Install system dependencies required for building and running the application
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    libffi-dev \
    openssl-dev \
    curl \
    unixodbc-dev \
    libpq \
    opus-dev \
    libvpx-dev

# Download and install Microsoft ODBC Driver and MSSQL tools
RUN curl -O https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/msodbcsql17_17.10.6.1-1_amd64.apk \
    && curl -O https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/mssql-tools_17.10.1.1-1_amd64.apk \
    && apk add --allow-untrusted msodbcsql17_17.10.6.1-1_amd64.apk \
    && apk add --allow-untrusted mssql-tools_17.10.1.1-1_amd64.apk \
    && rm msodbcsql17_17.10.6.1-1_amd64.apk mssql-tools_17.10.1.1-1_amd64.apk

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