FROM nginx:1

# pip deps
RUN apt-get update
RUN apt-get install wget nginx-full nginx-common python3-venv libaugeas0 procps libnginx-mod-http-geoip -y
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

# geoip databases
RUN mkdir -p /var/lib/nginx

RUN curl --verbose -L https://dl.miyuru.lk/geoip/maxmind/country/maxmind.dat.gz -o maxmind-country.dat.gz
RUN gunzip maxmind-country.dat.gz

RUN mv maxmind*.dat /var/lib/nginx/

RUN chown -R nginx: /var/lib/nginx

# nginx config
COPY tuner-nginx.conf /etc/nginx/nginx.conf
RUN rm -rf /etc/nginx/conf.d
COPY tuner-conf.d /etc/nginx/conf.d
COPY tuner-conf.d/.htpasswd /etc/nginx/.htpasswd

# Entrypoint setup
COPY nginx-entrypoint.sh /tmp/entrypoint-nginx.sh

RUN nginx -t

# Entrypoint
ENTRYPOINT /tmp/entrypoint-nginx.sh
