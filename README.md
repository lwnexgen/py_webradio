This project enables a scrubbable FM broadcast feed that is streamable to anything that can playback an m3u8 file.

![image](https://user-images.githubusercontent.com/2223592/137526576-9da596b6-eb17-4909-a152-90afb53b8381.png)

It creates an m3u8/mp3 stream out of data from an [RTL-SDR](https://www.rtl-sdr.com/) device using ffmpeg, and then serves those files using a containerized nginx instance using TLS / SSL from Let's Encrypt.

# Requirements

1. Hardware RTL-SDR device
1. Docker instance
1. domain-info should contain the following info specific to lets encrypt:
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

Note: a letsencrypt.org cert will be requested and provisioned for you
