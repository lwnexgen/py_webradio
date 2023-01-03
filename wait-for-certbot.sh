#!/bin/bash
while true ; do
	sleep 3
	docker-compose ps letsencrypt | grep -q 'Exit 0' && exit 0
	docker-compose ps letsencrypt | grep 'Exit' && exit 1
done
