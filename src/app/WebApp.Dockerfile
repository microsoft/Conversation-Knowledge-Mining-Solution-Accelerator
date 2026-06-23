FROM node:24-alpine AS build
WORKDIR /home/node/app

COPY ./package*.json ./

RUN npm install --legacy-peer-deps

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=build /home/node/app/build /usr/share/nginx/html

COPY public/startup.sh /usr/share/nginx/html/startup.sh
RUN chmod +x /usr/share/nginx/html/startup.sh && sed -i 's/\r$//' /usr/share/nginx/html/startup.sh

# Expose the application port
EXPOSE 3000

# Run startup script instead of nginx directly
CMD ["/bin/sh", "/usr/share/nginx/html/startup.sh"]
