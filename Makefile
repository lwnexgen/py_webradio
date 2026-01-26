local_pysched:
	virtualenv -p python3 pysched
	pysched/bin/pip install -U pip
	pysched/bin/pip install -r requirements.txt
	curl -L https://github.com/kubernetes/kompose/releases/download/v1.24.0/kompose-linux-amd64 -o pysched/bin/kompose
	chmod +x pysched/bin/kompose

# docker compose startup stuff
disk:
	lsmod | grep -q dvb_usb_rtl28xxu && sudo modprobe -r dvb_usb_rtl28xxu ||:
	rm -rf status.log merge.log schedule_skip.log
	cp domain-info tuner/tuner-env.env
	cp domain-info server/server-env.env
	python3 render-compose.py > docker-compose.yml
	touch status.log merge.log schedule_skip.log

# build images fresh and start in "schedule" mode
btest: stop disk
	cat sched-env >> tuner/tuner-env.env
	docker compose up --detach --build
	make test

# Tune for a few minutes pretending
# echo "DURATION=300" >> tuner/tuner-env.env
demo: stop disk
	cat sched-env >> tuner/tuner-env.env
	cat sched-env >> server/server-env.env
	cat demo-env >> tuner/tuner-env.env
	echo "$(shell sched/pysched/bin/python sched/schedulellm.py --sport=ncaaf --time | grep FAKETIME | tail -n 1)" >> tuner/tuner-env.env
	echo "FAKETIME_DONT_RESET=1" >> tuner/tuner-env.
	cat tuner/tuner-env.env
	docker compose up --detach
	./wait-for-certbot.sh && docker compose restart server
	docker compose logs -f letsencrypt server tuner sched

# start in "schedule" mode
test: stop disk
	cat sched-env >> tuner/tuner-env.env
	docker compose up --detach
	./wait-for-certbot.sh && docker compose restart server
	docker compose logs -f letsencrypt server tuner

stop:
	docker compose down --remove-orphans ||:
	docker compose stop -t 1 ||:
	docker ps -a --format=json | grep 'Exited' | jq -r '.ID' | while read dead ; do docker rm -f $$dead ; done
	docker volume rm -f py_webradio_webdata

ncaaf: stop disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --sport ncaaf

ncaab: stop disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --sport ncaab

nfl: stop disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --sport nfl

mlb: disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --sport mlb

nba: stop disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --sport nba

short: stop disk
	docker compose stop letsencrypt ||:
	docker compose up --detach server
	docker compose run --rm tuner --short
