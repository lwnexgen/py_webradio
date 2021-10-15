FROM fedora:latest

RUN dnf -y install /usr/sbin/atd

# bootstrap dependencies
RUN dnf -y install make
RUN dnf -y install python-virtualenv python2

WORKDIR /tmp

COPY entrypoint.py schedule.py __init__.py ./

COPY requirements.txt ./
COPY Makefile.sched Makefile

RUN make pysched

ENTRYPOINT /tmp/entrypoint.py
