FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CMAKE_ARGS="-DGGML_CUDA=on"

RUN apt-get update && apt-get install -y python3-full python3-pip python3-venv xvfb ccache git curl

RUN mkdir -p /app
WORKDIR /app

RUN curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz
RUN mkdir -p /app/ollama && tar -xzf ollama-linux-amd64.tgz -C /app/ollama

ENV OLLAMA_HOST=0.0.0.0
ENTRYPOINT ["/app/ollama/bin/ollama"]

