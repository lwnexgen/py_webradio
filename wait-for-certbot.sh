#!/bin/bash
while true ; do
	sleep 3
	docker compose ps -a letsencrypt --format=json | jq '.Status' | grep -q 'Exited (0)' && exit 0
	docker compose ps -a letsencrypt --format=json | jq '.Status' | grep -q 'Exited' && exit 1
done
