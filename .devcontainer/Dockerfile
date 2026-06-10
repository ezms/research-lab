FROM python:3.13-slim

ARG USERNAME=dev
ARG USER_UID=1001
ARG USER_GID=$USER_UID

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/home/${USERNAME}/.cache/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
        sudo \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

USER ${USERNAME}

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

WORKDIR /workspaces/research-lab
