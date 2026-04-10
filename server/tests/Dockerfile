FROM ubuntu:latest

# Install Python + venv/pip and nslookup
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    dnsutils \
    python3-venv && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv venv && venv/bin/pip install --upgrade pip && venv/bin/pip install requests

COPY test.sh /app/test.sh
COPY test_auth.py /app/test_auth.py

ENTRYPOINT ["/app/test.sh"]
