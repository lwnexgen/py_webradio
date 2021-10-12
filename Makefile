deploy:
	mkdir -p /var/www/html/webtune_live
	rm -rf /var/www/html/webtune_live/{js,css,manifest*,tuner.html}
	cp -r js css tuner.html tuner_local.html /var/www/html/webtune_live/
	cp favicon.ico /var/www/html/

disk:
	sudo modprobe -r dvb_usb_rtl28xxu ||:
	rm -f tuner-env.env
	rm -f atd.pid
	touch atd.pid
	sudo rm -rf at-spool
	sudo rm -rf at-output
	mkdir -p at-output
	mkdir -p at-spool/spool
	touch at-spool/.SEQ
	sudo rm -rf data
	mkdir -p data/scripts

build: disk
	docker build -t ywebradio:latest ./
	touch btest

btest: disk
	cp default-env tuner-env.env
	docker-compose down ||:
	docker-compose up --build --detach
	docker-compose logs -f tuner

blive: disk
	cp live-env tuner-env.env
	docker-compose down ||:
	docker-compose up --build --detach
	docker-compose logs -f tuner

live: disk
	cp live-env tuner-env.env
	docker-compose down --timeout=1 ||:
	docker-compose up --detach
	docker-compose logs -f tuner

test: disk
	cp default-env tuner-env.env
	docker-compose down ||:
	docker-compose up --detach
	docker-compose logs -f tuner

slive:
	sed -e 's;entrypoint: /tmp/pysched/entrypoint.py;entrypoint: /bin/bash;g' -e 's;entrypoint: /tmp/entrypoint-docker.sh;entrypoint: /bin/bash;g' docker-compose.yml > docker-compose-new.yml
	docker-compose -f docker-compose-new.yml run sched
