FROM nginx:1

# copy base deps - TODO - fetch from AWS Secrets Manager
COPY install-or-update.sh /tmp/

# pip deps
RUN apt-get update
RUN apt-get install wget nginx-full nginx-common python3-venv libaugeas0 procps libnginx-mod-http-geoip -y
RUN python3 -m venv /opt/certbot
RUN /opt/certbot/bin/pip install --upgrade pip

# certbot install
RUN /opt/certbot/bin/pip install certbot certbot-nginx
RUN ln -s /opt/certbot/bin/certbot /usr/bin/certbot

# Entrypoint
ENTRYPOINT /tmp/install-or-update.sh
