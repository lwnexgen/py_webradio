#!/bin/bash
# build test container
docker build -t tuneradio-test -f tests/Dockerfile tests || {
    echo "Failed to build test container. Exiting."
    exit 1
}

rm -f build && make build
docker compose stop server
docker compose rm -f server
docker compose up -d server

# wait for server to start by waiting for a successful HTTP response to
# https://192.168.0.197
start=$(date +%s)
while ! curl -k -s https://192.168.0.197 > /dev/null; do
  echo "Waiting for server to start..."
  sleep 1
  if [ $(($(date +%s) - start)) -gt 60 ]; then
      echo "Server did not start within 60 seconds. Exiting."
      exit 1
  fi
done

docker run --dns 8.8.8.8 --env-file test-env --rm -it tuneradio-test
