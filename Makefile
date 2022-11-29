local_pysched:
	virtualenv -p python3 pysched
	pysched/bin/pip install -U pip
	pysched/bin/pip install -r requirements.txt
	curl -L https://github.com/kubernetes/kompose/releases/download/v1.24.0/kompose-linux-amd64 -o pysched/bin/kompose
	chmod +x pysched/bin/kompose

# docker-compose startup stuff
disk:
	lsmod | grep -q dvb_usb_rt128xxu && sudo modprobe -r dvb_usb_rtl28xxu ||:
	rm -f tuner-env.env
	cp domain-info tuner/tuner-env.env
	python render-compose.py > docker-compose.yml
	docker volume rm -f py_webradio_webdata

# build images fresh and start in "schedule" mode
btest: stop disk
	cat sched-env >> tuner/tuner-env.env
	docker-compose up --detach --build
	make test

# start in "schedule" mode
test: stop disk
	cat sched-env >> tuner/tuner-env.env
	docker-compose up --detach
	sleep 10 && docker-compose restart server
	docker-compose logs -f letsencrypt server tuner

stop:
	docker-compose stop -t 1 ||:
	docker image prune -f
	docker container prune -f
	docker volume rm -f py_webradio_webdata

ncaaf: disk
	docker-compose stop tuner ||:
	docker-compose run tuner --sport ncaaf

nfl: disk
	docker-compose stop tuner ||:
	docker-compose run tuner --sport nfl

mlb: disk
	docker-compose stop tuner ||:
	docker-compose run tuner --sport mlb

nba: disk
	docker-compose stop tuner ||:
	docker-compose run tuner --sport nba

studio_m: disk
	docker-compose stop tuner ||:
	docker-compose run tuner --sport studio_m

fake: disk
	cat sched-env >> tuner/tuner-env.env
	cat fake-env >> tuner/tuner-env.env
	docker-compose down ||:
	docker-compose up --detach
	docker-compose logs -f tuner
