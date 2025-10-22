FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    samba

COPY smb.conf /etc/samba/smb.conf

RUN userdel -r ubuntu
RUN useradd sam --uid 1000
RUN useradd guest

RUN /bin/bash -c 'echo -e "guest\nguest\n" | smbpasswd -D7 -a -s guest'
RUN /bin/bash -c 'echo -e "P@ssw0rd\nP@ssw0rd\n" | smbpasswd -D7 -a -s sam'

ENTRYPOINT ["/usr/sbin/smbd"]
CMD ["--foreground", "--no-process-group", "--debug-stdout", "-d2"]
