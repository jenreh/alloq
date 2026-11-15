ARG VARIANT=3.14-bookworm
FROM mcr.microsoft.com/devcontainers/python:${VARIANT} AS base

ARG FZF_VERSION=0.75.0
ARG ZOXIDE_VERSION=0.10.0
ARG STARSHIP_VERSION=1.27.0
ARG ANTIDOTE_VERSION=2.3.0

ENV PATH="/root/.local/bin/:$PATH" \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# Stage 1: Install UV separately to optimize caching
#RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin

# Shell: antidote plugin manager, starship prompt, fzf and zoxide (Debian's are too
# old). The plugins are listed in .devcontainer/.zsh_plugins.txt.
RUN curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_$(dpkg --print-architecture).tar.gz" \
        | tar -xz -C /usr/local/bin fzf \
    && curl -fsSL "https://github.com/ajeetdsouza/zoxide/releases/download/v${ZOXIDE_VERSION}/zoxide-${ZOXIDE_VERSION}-$(uname -m)-unknown-linux-musl.tar.gz" \
        | tar -xz -C /usr/local/bin zoxide \
    && curl -fsSL https://starship.rs/install.sh \
        | sh -s -- --yes --bin-dir /usr/local/bin --version "v${STARSHIP_VERSION}" \
    && git clone --quiet --depth 1 --branch "v${ANTIDOTE_VERSION}" \
        https://github.com/mattmc3/antidote.git /usr/local/share/antidote
