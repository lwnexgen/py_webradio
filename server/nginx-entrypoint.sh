#!/bin/sh
# Wait for letsencrypt container to be up
wait-for-it letsencrypt:80 || exit 1

# initialize certbot - TODO ; should be templatized using Jinja
sed -e "s;DOMAIN_PLACEHOLDER;$DOMAIN;g" /etc/nginx/conf.d/default.conf -i

# Install domain cert into container
certbot -v --non-interactive install -d "$DOMAIN" --cert-name "$DOMAIN" --nginx

/usr/sbin/nginx -s stop;
sleep 10;
/usr/sbin/nginx -g "daemon off;"
   
