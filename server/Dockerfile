FROM nginx:1

# pip deps
RUN apt-get update && apt-get install wget python3-venv libaugeas0 procps -y
RUN python3 -m venv /opt/certbot
RUN /opt/certbot/bin/pip install --upgrade pip

# certbot install
RUN /opt/certbot/bin/pip install certbot certbot-nginx

# download wait-for-it
RUN curl -L "https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f17855a4dc21156cfe1694c31d7d1792e/wait-for-it.sh" -o "/opt/certbot/bin/wait-for-it.sh"

# perms
RUN chmod +x /opt/certbot/bin/wait-for-it.sh

# container-wide install
RUN ln -s /opt/certbot/bin/certbot /usr/bin/certbot
RUN ln -s /opt/certbot/bin/wait-for-it.sh /usr/bin/wait-for-it

# nginx config
COPY tuner-nginx.conf /etc/nginx/nginx.conf
RUN rm -rf /etc/nginx/conf.d
COPY tuner-conf.d /etc/nginx/conf.d
COPY tuner-conf.d/.htpasswd /etc/nginx/.htpasswd

# Entrypoint setup
COPY nginx-entrypoint.sh /tmp/entrypoint-nginx.sh

RUN cat /etc/nginx/conf.d/default.conf
RUN nginx -t

# Entrypoint
ENTRYPOINT /tmp/entrypoint-nginx.sh
