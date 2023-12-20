FROM fedora:34

# bootstrap dependencies
RUN dnf -y install make dnf-plugins-core
RUN dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
RUN dnf -y install python-virtualenv python2 docker-ce-cli openssh-clients

RUN useradd pysched --uid 1000
RUN groupmod -g 988 docker
RUN usermod -a -G docker pysched

RUN mkdir -p /app /etc/ssh
COPY teams2.json entrypoint.py schedule.py __init__.py sportsline.js wol_creds id_rsa_windows id_rsa_wsl ssh_config /app/
COPY known_hosts /etc/ssh/ssh_known_hosts

RUN chown -R pysched:pysched /app

USER pysched

WORKDIR /app

COPY Makefile.sched Makefile
COPY requirements.txt ./

RUN make pysched

RUN mkdir -p /app/content_scraper
COPY content_scraper /app/content_scraper

ENTRYPOINT /app/entrypoint.py
