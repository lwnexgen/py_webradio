This project enables a scrubbable FM broadcast feed that is streamable to anything that can playback an m3u8 file.

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
1. `make blive` - run this in live mode, tuning to the desired station for the specified duration (minutes) - configured via`live-env` file:
   1. `STATION=101.5`
   1. `DURATION=360`
   1. `HOME=/tmp/pysched`

Note: a letsencrypt.org cert will be requested and provisioned for you based on the DOMAIN and EMAIL you specify in 'domain-info' - this will be stored in the 'certs' volume and updated by the letsencrypt service on cluster startup
