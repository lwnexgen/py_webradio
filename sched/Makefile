TAG ?= "pywebsched:latest"

disk:
	rm -rf at-spool var-run
	mkdir -p at-spool
	mkdir -p var-run

build:
	docker build --progress=plain -t $(TAG) .
	touch build

live: build disk
	docker run --env-file=sched-env.env \
		-v "$(shell readlink -f ./schedule.py):/app/schedule.py" \
		-v "$(shell readlink -f at-spool):/var/spool/at:rw" \
		-v "$(shell readlink -f var-run)/atd.pid:/var/run/atd.pid:rw" \
		--entrypoint /bin/bash --name=livesched --rm -it $(TAG)
