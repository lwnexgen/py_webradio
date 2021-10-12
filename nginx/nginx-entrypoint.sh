#!/bin/sh
# initialize certbot
DOMAIN="***REMOVED***"
CERTDIR="/etc/letsencrypt/live/$DOMAIN"
if [ ! -d "$CERTDIR" ] ; then
    certbot -v --nginx -m lwnexgen@gmail.com --non-interactive --agree-tos -d "$DOMAIN"
else
    echo "$CERTDIR already exists, need to work on renewal-checking"
    certbot -v --non-interactive renew
    certbot -v --non-interactive install -d "$DOMAIN" --cert-name "$DOMAIN" --nginx
fi

/usr/sbin/nginx -s stop;
sleep 10;
/usr/sbin/nginx -g "daemon off;"
   
