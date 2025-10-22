FROM nginx:1.24

# copy base deps - TODO - fetch from AWS Secrets Manager
COPY install-or-update.sh /tmp/

# pip deps
RUN apt-get update && apt-get install python3 python3-venv -y
RUN python3 -m venv /opt/certbot
RUN /opt/certbot/bin/pip install --upgrade pip

# certbot install
RUN /opt/certbot/bin/pip install certbot certbot-nginx
RUN ln -s /opt/certbot/bin/certbot /usr/bin/certbot

# Entrypoint
ENTRYPOINT /tmp/install-or-update.sh
