#!/bin/sh
# initialize certbot
env

CERTDIR="/etc/letsencrypt/live/$DOMAIN"

sed -e "s;DOMAIN_PLACEHOLDER;$DOMAIN;g" /etc/nginx/conf.d/default.conf -i

if [ ! -d "$CERTDIR" ] ; then
    certbot -v --nginx -m "$EMAIL" --non-interactive --agree-tos -d "$DOMAIN"
else
    echo "$CERTDIR already exists, need to work on renewal-checking"
    certbot -v --non-interactive renew
    certbot -v --non-interactive install -d "$DOMAIN" --cert-name "$DOMAIN" --nginx
fi

/usr/sbin/nginx -s stop;
sleep 10;
/usr/sbin/nginx -g "daemon off;"
   
