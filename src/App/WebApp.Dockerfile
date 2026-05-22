FROM node:24-alpine AS build 
WORKDIR /home/node/app  

COPY ./package*.json ./  
  
RUN npm ci --omit=dev 
 
COPY . .  
 
RUN npm run build  
  
FROM nginx:alpine  

COPY --from=build /home/node/app/build /usr/share/nginx/html  

COPY env.sh /docker-entrypoint.d/env.sh
RUN chmod +x /docker-entrypoint.d/env.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/env.sh

# Custom nginx config with API proxy support
COPY nginx.conf /etc/nginx/nginx.conf

# Create empty api-proxy conf (overwritten at startup for WAF deployments)
RUN mkdir -p /etc/nginx/conf.d && touch /etc/nginx/conf.d/api-proxy.conf

# Expose the application port
EXPOSE 3000

# Start NGINX and run env.sh
CMD ["/bin/sh", "-c", "/docker-entrypoint.d/env.sh && nginx -g 'daemon off;'"]