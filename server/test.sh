#!/bin/bash
cleanup() {
    echo "Cleaning up..."
    docker compose stop server
    docker compose rm -f server
    # restore the original .htpasswd file
    if [ -f ../tuner-conf.d/.htpasswd.bak ]; then
	mv ../tuner-conf.d/.htpasswd.bak ../tuner-conf.d/.htpasswd
    fi
}

trap cleanup EXIT

# build test container
docker build -t tuneradio-test -f tests/Dockerfile tests || {
    echo "Failed to build test container. Exiting."
    exit 1
}

# generate a random password for htpasswd and add it to ../tuner-conf.d/.htpasswd
username="autotest"
password=$(openssl rand -base64 12)

# make a backup of the .htpasswd file before modifying it
cp tuner-conf.d/.htpasswd tuner-conf.d/.htpasswd.bak

# append the new credentials to the .htpasswd file
htpasswd -b -B tuner-conf.d/.htpasswd "$username" "$password"

# also add the credentials in the form WEBRADIO_CREDENTIALS=username:password to ./test-env-creds
cp tests/hostname-env tests/test-env-no-creds
cp tests/hostname-env tests/test-env-creds
cat >> tests/test-env-creds <<EOL

WEBRADIO_CREDENTIALS=$username:$password
EOL

docker compose stop server
docker compose rm -f server
docker compose up --build -d server

# wait for server to start by waiting for a successful HTTP response to
# https://192.168.0.197
start=$(date +%s)
source tests/hostname-env
while ! curl -k -s $BASEURL_ENDPOINT > /dev/null; do
  if [ $(($(date +%s) - start)) -gt 60 ]; then
      echo "Server did not start within 60 seconds. Exiting."
      exit 1
  fi
  echo "Waiting for server to start..."
  sleep 10
done

echo "Running tests with credentials..."
docker run --dns 8.8.8.8 --env-file tests/test-env-creds --rm -it tuneradio-test --with-auth
