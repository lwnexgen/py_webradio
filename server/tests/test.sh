#!/bin/bash
nslookup ***REMOVED*** || exit 1
ls -ltr /app

source venv/bin/activate
python /app/test_auth.py --base-url "https://***REMOVED***" || exit 1
deactivate
