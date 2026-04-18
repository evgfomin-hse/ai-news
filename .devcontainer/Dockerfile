FROM mcr.microsoft.com/devcontainers/javascript-node:1-22-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends make python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
