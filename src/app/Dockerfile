FROM node:22-bookworm-slim AS build

ARG REACT_APP_API_BASE_URL=""
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

# Production stage — serve with lightweight server
FROM node:22-bookworm-slim
RUN npm install -g serve
WORKDIR /app
COPY --from=build /app/build ./build
COPY serve.json ./

# Non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:3000/ || exit 1
CMD ["serve", "-s", "build", "-l", "3000"]
