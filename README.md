This project enables a scrubbable FM broadcast feed that is streamable to anything that can playback an m3u8 file.

![image](https://user-images.githubusercontent.com/2223592/137526576-9da596b6-eb17-4909-a152-90afb53b8381.png)

It creates an m3u8/mp3 stream out of data from an [RTL-SDR](https://www.rtl-sdr.com/) device using ffmpeg, and then serves those files using a containerized nginx instance using TLS / SSL from Let's Encrypt.

# Requirements

1. Hardware RTL-SDR device
1. Docker instance
1. Write a file named 'domain-info' in this directory - it should contain the following info specific to Let's Encrypt:
   1. `DOMAIN=desired letsencrypt hostname`
   1. `EMAIL=letsencrypt email`

# Configuration

1. Copy tuner/config.json.sample to tuner/config.json
   1. `local_address` should be of the form `http://<ip>:<port>/` on some IP that you want your webserver to listen
	  1. Example: `http://192.168.0.10:80/`
   1. `public_address` is an https DNS-resolvable name
	  1. Example: `https://supercoolserver/`

# Running

1. `make btest` - this will build the docker images, and use docker-compose to deploy them
1. `make test` - just run run the docker-compose deployment without building the latest images

## Live Mode

1. To run in 'live' mode, first start the cluster via `make test`
1. Once it's running, stop the tuner container: `docker-compose stop tuner`
1. Once it's stopped, start it in 'now' mode: `docker-compose run --rm tuner --now`
1. Wait 30s for the stream to become available at your domain

Note: a letsencrypt.org cert will be requested and provisioned for you based on the DOMAIN and EMAIL you specify in 'domain-info' - this will be stored in the 'certs' volume and updated by the letsencrypt service on cluster startup
