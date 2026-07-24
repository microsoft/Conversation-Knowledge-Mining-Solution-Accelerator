FROM node:24-alpine AS build
WORKDIR /home/node/app

ENV NO_UPDATE_NOTIFIER=1
ENV NODE_NO_WARNINGS=1

COPY ./package*.json ./

RUN npm install --legacy-peer-deps --no-fund --loglevel=error

COPY . .

RUN npm run build --loglevel=error

FROM nginx:alpine

COPY --from=build /home/node/app/build /usr/share/nginx/html

# SPA fallback for client-side routing (BrowserRouter) so deep-link refreshes don't 404
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY public/startup.sh /usr/share/nginx/html/startup.sh
RUN chmod +x /usr/share/nginx/html/startup.sh && sed -i 's/\r$//' /usr/share/nginx/html/startup.sh

# Expose the application port
EXPOSE 3000

# Run startup script instead of nginx directly
CMD ["/bin/sh", "/usr/share/nginx/html/startup.sh"]