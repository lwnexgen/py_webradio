FROM nginx:1

# pip deps
RUN apt-get update
RUN apt-get install wget nginx-full nginx-common python3-venv libaugeas0 procps libnginx-mod-http-geoip -y
RUN python3 -m venv /opt/certbot
RUN /opt/certbot/bin/pip install --upgrade pip

# certbot install
RUN /opt/certbot/bin/pip install certbot certbot-nginx
RUN ln -s /opt/certbot/bin/certbot /usr/bin/certbot

# geoip databases
RUN mkdir -p /var/lib/nginx

RUN curl -L https://dl.miyuru.lk/geoip/maxmind/country/maxmind.dat.gz -o maxmind-country.dat.gz
RUN curl -L https://dl.miyuru.lk/geoip/maxmind/city/maxmind.dat.gz -o maxmind-city.dat.gz

RUN gunzip maxmind-country.dat.gz
RUN gunzip maxmind-city.dat.gz

RUN mv maxmind*.dat /var/lib/nginx/

RUN chown -R nginx: /var/lib/nginx

# nginx config
COPY tuner-nginx.conf /etc/nginx/nginx.conf
RUN rm -rf /etc/nginx/conf.d
COPY tuner-conf.d /etc/nginx/conf.d

# Entrypoint setup
COPY nginx-entrypoint.sh /tmp/entrypoint-nginx.sh

RUN nginx -t ||:

# Entrypoint
ENTRYPOINT /tmp/entrypoint-nginx.sh
CMD ""
