#!/bin/bash
set -euo pipefail

BM25_INDEX_PATH="${BM25_INDEX_PATH:-/data/indexes/bm25}"
export BM25_INDEX_PATH

# The BM25 index is baked into the image at build time. Validate it and
# fail fast if something's wrong — we don't attempt runtime recovery.
.venv/bin/python - <<'PYEOF'
import os
from pyserini.search.lucene import LuceneSearcher

LuceneSearcher(os.environ["BM25_INDEX_PATH"])
print("[entrypoint] BM25 index validation passed")
PYEOF

exec .venv/bin/python src/server.py "$@"
