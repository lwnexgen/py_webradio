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

# build images fresh and start in "schedule" mode
btest: disk
	cat sched-env >> tuner/tuner-env.env
	docker-compose down ||:
	docker-compose up --build --detach
	docker-compose logs -f tuner

# start in "schedule" mode
test: disk
	cat sched-env >> tuner/tuner-env.env
	docker-compose down ||:
	docker-compose up --detach
	docker-compose logs -f tuner


fake: disk
	cat sched-env >> tuner/tuner-env.env
	cat fake-env >> tuner/tuner-env.env
	docker-compose down ||:
	docker-compose up --detach
	docker-compose logs -f tuner

# build images fresh and start in "live" mode
blive: disk
	cat live-env >> tuner/tuner-env.env
	docker-compose down ||:
	docker-compose up --build --detach
	docker-compose logs -f tuner

# start in "live" mode
live: disk
	cat live-env >> tuner/tuner-env.env
	docker-compose down --timeout=1 ||:
	docker-compose up --detach
	docker-compose logs -f tuner
