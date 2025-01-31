# Stage 1: Build frontend
FROM node:20-alpine AS frontend  
RUN mkdir -p /home/node/app/node_modules && chown -R node:node /home/node/app

WORKDIR /home/node/app 

# Install dependencies
COPY ./frontend/package*.json ./  
USER node
RUN npm ci  

# Copy source code and build
COPY --chown=node:node ./frontend/ ./frontend  
WORKDIR /home/node/app/frontend
RUN npm run build

# Stage 2: Build backend with static files
FROM python:3.11-alpine 

# Install dependencies
RUN apk add --no-cache --virtual .build-deps \  
    build-base \  
    libffi-dev \  
    openssl-dev \  
    curl \  
    && apk add --no-cache \  
    libpq 

COPY requirements.txt /usr/src/app/  
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt \  
    && rm -rf /root/.cache  

# Copy backend source code
COPY . /usr/src/app/


RUN ls -l /home/node/app/frontend/build/static

RUN [ -d /usr/src/app/static ] && echo "Directory exists" || echo "Directory does not exist"

RUN [ -d /usr/src/app/static ] && ls -l /usr/src/app/static || echo "Directory does not exist"


# Copy static files from the frontend stage to the backend
COPY --from=frontend /home/node/app/frontend/build/static /usr/src/app/static/

# Set working directory and expose port
WORKDIR /usr/src/app  
EXPOSE 80  

# Start application
CMD ["gunicorn", "-b", "0.0.0.0:80", "app:app"]
