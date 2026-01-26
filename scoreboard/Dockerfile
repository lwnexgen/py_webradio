FROM nvcr.io/nvidia/pytorch:24.12-py3

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install build-essential make python3-pip python3-full python3-venv dnsutils -y
RUN apt-get update && apt-get install -y build-essential
RUN apt-get update && apt-get install curl xvfb libgomp1 cmake patchelf zstd clang libgthread-2.0 ccache -y && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/python/3.12.12 && curl -L "https://github.com/astral-sh/python-build-standalone/releases/download/20251031/cpython-3.12.12+20251031-x86_64_v4-unknown-linux-gnu-pgo+lto-full.tar.zst" -o "python.tar.zst" && unzstd python.tar.zst -o python.tar && tar -xf python.tar -C /usr/local/python/3.12.12 --strip-components=1

ENV PATH="/usr/local/python/3.12.12/install/bin:${PATH}"

RUN pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly --extra-index-url https://download.pytorch.org/whl/cu129

RUN pip install -U \
    arrow \
    beautifulsoup4 \
    flask \
    openai \
    pika \
    pillow \
    pydantic \
    requests \
    && echo "done"

RUN pip install -U \
    playwright \
    && echo "done"

RUN find / -name 'playwright' -type f

RUN playwright install chromium
RUN playwright install firefox
RUN playwright install-deps

ENV HF_HOME="/app/huggingface"

WORKDIR /app

RUN pip install -U tablib

COPY entrypoint.py /app/entrypoint.py
COPY mdparse /app/mdparse
COPY screenshotter /app/screenshotter
EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/app/entrypoint.py"]
