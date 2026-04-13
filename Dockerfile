# Stage 1: install Python deps (full image has build tooling for native extensions)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

RUN adduser agent
USER agent
WORKDIR /home/agent

COPY pyproject.toml uv.lock README.md ./
COPY src src

RUN \
    --mount=type=cache,target=/home/agent/.cache/uv,uid=1000 \
    uv sync --locked

# Stage 2: runtime with Java tooling and the pre-built venv
# Pyserini/Anserini in the current lockfile requires Java 21 bytecode support.
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

# Install a full JDK. In practice Pyserini can require `javac` to be present
# during initialization, so a JRE-only image is not sufficient here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

RUN adduser agent
RUN mkdir -p /data/indexes && chown -R agent:agent /data
USER agent
WORKDIR /home/agent

COPY pyproject.toml uv.lock README.md ./
COPY src src
COPY --from=builder --chown=agent:agent /home/agent/.venv .venv

# Download BM25 index at build time so runtime needs no internet
RUN .venv/bin/python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download( \
    repo_id='Tevatron/browsecomp-plus-indexes', \
    repo_type='dataset', \
    allow_patterns=['bm25/*'], \
    local_dir='/data/indexes/bm25-dl', \
)" && mv /data/indexes/bm25-dl/bm25 /data/indexes/bm25 \
   && rm -rf /data/indexes/bm25-dl \
   && touch /data/indexes/bm25.ready

# Path where the corpus volume is mounted at runtime
ENV BM25_INDEX_PATH=/data/indexes/bm25
ENV DEFAULT_K=5

COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0"]
EXPOSE 9009
