#!/bin/sh
wait_and_retry() {
    wait-for-it -t 300 letsencrypt:80 || exit 1
    certbot -v --non-interactive install -d "$DOMAIN" --cert-name "$DOMAIN" --nginx || exit 1
}

# initialize certbot - TODO ; should be templatized using Jinja
sed -e "s;DOMAIN_PLACEHOLDER;$DOMAIN;g" /etc/nginx/conf.d/default.conf -i

# Install domain cert into container or wait until letsencrypt is done with initial install
certbot -v --non-interactive install -d "$DOMAIN" --cert-name "$DOMAIN" --nginx || wait_and_retry

/usr/sbin/nginx -s stop;
sleep 10;

/usr/sbin/nginx -g "daemon off;"
