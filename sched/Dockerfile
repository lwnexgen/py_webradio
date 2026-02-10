FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install build-essential make python3-pip python3-venv dnsutils zstd -y

WORKDIR /app

RUN python3 -m venv pysched
RUN /app/pysched/bin/pip install -U \
    playwright \
    && echo "done"

RUN /app/pysched/bin/playwright install chromium
RUN /app/pysched/bin/playwright install-deps

RUN apt-get install curl -y
# RUN curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz
RUN curl -L https://github.com/ollama/ollama/releases/download/v0.15.2/ollama-linux-amd64.tar.zst -o ollama-linux-amd64.tar.zst
RUN mkdir -p /app/ollama && tar -I zstd -xvf ollama-linux-amd64.tar.zst -C /app/ollama

RUN /app/pysched/bin/pip install -U \
    arrow \
    beautifulsoup4 \
    openai \
    pillow \
    pydantic \
    requests \
    pika \
    && echo "done"

RUN /app/pysched/bin/pip freeze

COPY teams2.json entrypoint.py schedulellm.py __init__.py sportsline.js wol_creds id_rsa_windows id_rsa_wsl ssh_config /app/

ENV PYTHONUNBUFFERED=1
ENTRYPOINT /app/entrypoint.py
