#!/bin/sh
CERTDIR="/etc/letsencrypt/live/$DOMAIN"

sed -e "s;DOMAIN_PLACEHOLDER;$DOMAIN;g" /etc/nginx/conf.d/default.conf -i

/usr/sbin/nginx

# Fetch new certs from Let's Encrypt
if [ ! -d "$CERTDIR" ] ; then
    certbot -v --nginx -m "$EMAIL" --non-interactive --agree-tos -d "$DOMAIN"
else
    # Renew existing cert from Let's Encrypt
    certbot -v --non-interactive renew
fi

/usr/sbin/nginx -s stop
