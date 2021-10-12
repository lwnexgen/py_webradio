#!/bin/sh
if [ ! -z "$LIVE" ] ; then
    exec /bin/bash
fi

env
if [ ! -z "$STATION" ] ; then
    if [ ! -z "$DURATION" ] ; then
	pysched/bin/python tune.py $STATION --duration="$DURATION"min
    else
	pysched/bin/python tune.py $STATION
    fi
    exit 0
fi

make deploy

sleep 10
while true ; do
    printf "Starting atd at date %s\n" "$(date)"
    sh -c "time strace -o /tmp/pysched/data/strace-tuner.log -ff /usr/sbin/atd -d -s 2>/dev/null"
    queue=$(atq)
    printf "Remaining at queue\n%s\n" "$queue"
    find /var/spool/at -maxdepth 1 -type f | while read fn ; do
	sched=$(grep 'scheduled_sort' "$fn" | cut -d ':' -f2-)
	odds=$(grep 'odds' "$fn" | cut -d ':' -f2-)
	printf "%s:%s\n" "$sched" "$odds"
    done | sort -h
    sleep 60
done
