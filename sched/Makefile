TAG ?= "pywebsched:latest"

disk:
	rm -rf at-spool var-run
	mkdir -p at-spool
	mkdir -p var-run

build:
	docker build -t $(TAG) .
	touch build

live: build disk
	docker run --env-file=sched-env.env -v "$(readlink -f at-spool):/var/spool/at:rw" -v "$(readlink -f var-run)/atd.pid:/var/run/atd.pid:rw" $(TAG)
