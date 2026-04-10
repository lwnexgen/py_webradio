#!/bin/bash
if [ -z "$BASEURL_ENDPOINT" ]; then
    echo "Error: BASEURL_ENDPOINT is not set" >&2
    exit 1
fi
hostname=$(echo "$BASEURL_ENDPOINT" | awk -F'/' '{print $3}')
nslookup "$hostname" || exit 1
ls -ltr /app

source venv/bin/activate
if [ ! -z $WEBRADIO_CREDENTIALS ]; then
    python /app/test_auth.py --base-url "$BASEURL_ENDPOINT" --with-auth || exit 1
else
    python /app/test_auth.py --base-url "$BASEURL_ENDPOINT" || exit 1
fi
deactivate
