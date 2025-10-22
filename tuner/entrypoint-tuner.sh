#!/bin/sh
if [ ! -z "$LIVE" ] ; then
    exec /bin/bash
fi

rm -f /var/www/html/webtune_live/data/*.{mp3,m3u8}
mkdir -p /var/www/html/webtune_live/data

if [ ! -z "$STATION" ] ; then
    if [ ! -z "$DURATION" ] ; then
	pysched/bin/python tune.py $STATION --duration="$DURATION"min
    else
	pysched/bin/python tune.py $STATION
    fi
    exit 0
fi

make deploy

env

sleep 10
while true ; do
    printf "Starting atd at date %s\n" "$(date)"
    queue=$(atq)
    printf "Remaining at queue\n%s\n" "$queue"
    sh -c "strace /usr/sbin/atd -d -s"
    find /var/spool/at -maxdepth 1 -type f | while read fn ; do
	sched=$(grep 'scheduled_sort' "$fn" | cut -d ':' -f2-)
	odds=$(grep 'odds' "$fn" | cut -d ':' -f2-)
	printf "%s:%s\n" "$sched" "$odds"
    done | sort -h
    sleep 60
done
