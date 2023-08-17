build:
	docker build -t pywebtuner:latest . --progress=plain
	touch build

live: build
	cp live-env tuner-env.env
	cat domain-info >> tuner-env.env
	docker run --privileged --env-file tuner-env.env pywebtuner:latest
