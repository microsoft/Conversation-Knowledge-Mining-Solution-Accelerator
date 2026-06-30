#!/bin/sh

# If BACKEND_API_HOST is set (WAF mode), configure nginx reverse proxy
if [ -n "$BACKEND_API_HOST" ]; then
  # Write nginx proxy config for /api/ and /history/ routes
  cat > /etc/nginx/conf.d/api-proxy.conf << PROXYEOF
location /api/ {
    resolver 168.63.129.16 valid=30s;
    set \$backend "https://$BACKEND_API_HOST";
    proxy_pass \$backend;
    proxy_set_header Host $BACKEND_API_HOST;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_ssl_server_name on;
    proxy_read_timeout 300s;
    proxy_connect_timeout 60s;
    proxy_buffering off;
}

location /history/ {
    resolver 168.63.129.16 valid=30s;
    set \$backend "https://$BACKEND_API_HOST";
    proxy_pass \$backend;
    proxy_set_header Host $BACKEND_API_HOST;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_ssl_server_name on;
    proxy_read_timeout 300s;
    proxy_connect_timeout 60s;
    proxy_buffering off;
}
PROXYEOF
else
  # Ensure empty file exists for non-WAF deployments
  > /etc/nginx/conf.d/api-proxy.conf
fi

# Replace APP_* env vars in built frontend files (existing behavior)
for i in $(env | grep ^APP_)
do
    key=$(echo $i | cut -d '=' -f 1)
    value=$(echo $i | cut -d '=' -f 2-)
    echo $key=$value
    find /usr/share/nginx/html -type f -exec sed -i "s|\b${key}\b|${value}|g" '{}' +
done
echo 'done'