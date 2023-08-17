FROM fedora:34

# bootstrap dependencies
RUN dnf -y install make dnf-plugins-core
RUN dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
RUN dnf -y install python-virtualenv python2 docker-ce-cli

RUN useradd pysched --uid 1000
RUN groupmod -g 988 docker
RUN usermod -a -G docker pysched

USER pysched

WORKDIR /tmp

COPY entrypoint.py schedule.py __init__.py sportsline.js ./

COPY requirements.txt ./
COPY Makefile.sched Makefile

RUN make pysched

ENTRYPOINT /tmp/entrypoint.py
