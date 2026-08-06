#!/bin/sh
echo "Injecting environment variables into runtime-config.js..."

if [ -f /usr/share/nginx/html/runtime-config.js ]; then
  envsubst < /usr/share/nginx/html/runtime-config.js > /usr/share/nginx/html/runtime-config.tmp.js
  mv /usr/share/nginx/html/runtime-config.tmp.js /usr/share/nginx/html/runtime-config.js
  echo "runtime-config.js updated successfully"
else
  echo "runtime-config.js not found!"
fi

# Configure the /api reverse proxy. In private-networking mode the backend has
# no public endpoint, so the SPA calls the frontend same-origin /api and nginx
# forwards to the backend over the VNet. In public mode BACKEND_API_HOST is
# empty and the SPA calls the backend URL directly, so no proxy is emitted.
PROXY_CONF=/etc/nginx/conf.d/api-proxy.inc
if [ -n "$BACKEND_API_HOST" ]; then
  echo "Configuring /api reverse proxy to $BACKEND_API_HOST"
  cat > "$PROXY_CONF" <<EOF
location /api/ {
    proxy_pass https://${BACKEND_API_HOST};
    proxy_set_header Host ${BACKEND_API_HOST};
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_ssl_server_name on;
    proxy_http_version 1.1;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
EOF
else
  : > "$PROXY_CONF"
fi

nginx -g "daemon off;"
