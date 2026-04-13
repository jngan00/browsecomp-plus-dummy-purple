#!/bin/bash
set -euo pipefail

BM25_INDEX_PATH="${BM25_INDEX_PATH:-/data/indexes/bm25}"
BM25_READY_SENTINEL="${BM25_INDEX_READY_SENTINEL:-${BM25_INDEX_PATH}.ready}"
BM25_FAILED_SENTINEL="${BM25_INDEX_FAILED_SENTINEL:-${BM25_INDEX_PATH}.failed}"
export BM25_INDEX_PATH
export BM25_READY_SENTINEL
export BM25_FAILED_SENTINEL

mkdir -p "$(dirname "$BM25_INDEX_PATH")"

if [[ "${SKIP_INDEX_DOWNLOAD:-}" == "true" ]]; then
    echo "[entrypoint] SKIP_INDEX_DOWNLOAD=1 — skipping BM25 index download"
    exec .venv/bin/python src/server.py "$@"
fi

validate_index() {
    .venv/bin/python - <<'PYEOF'
import os
from pyserini.search.lucene import LuceneSearcher

LuceneSearcher(os.environ["BM25_INDEX_PATH"])
print("[entrypoint] BM25 index validation passed")
PYEOF
}

if [[ -f "$BM25_READY_SENTINEL" ]] || [[ -n "$(find "$BM25_INDEX_PATH" -maxdepth 1 -name 'segments_*' -print -quit 2>/dev/null)" ]]; then
    if validate_index >/dev/null 2>&1; then
        echo "[entrypoint] Reusing cached BM25 index at $BM25_INDEX_PATH"
        touch "$BM25_READY_SENTINEL"
    else
        echo "[entrypoint] Cached BM25 index is invalid; clearing and redownloading"
        rm -rf "$BM25_INDEX_PATH" "$BM25_READY_SENTINEL" "$BM25_FAILED_SENTINEL"
    fi
fi

if [[ ! -f "$BM25_READY_SENTINEL" ]]; then
    rm -f "$BM25_READY_SENTINEL" "$BM25_FAILED_SENTINEL"
    echo "[entrypoint] Starting BM25 index download in background..."
    .venv/bin/python -u - <<'PYEOF' &
import os
import shutil
import tempfile
import traceback
from pathlib import Path

from huggingface_hub import snapshot_download

index_path = Path(os.environ["BM25_INDEX_PATH"])
ready = Path(os.environ["BM25_READY_SENTINEL"])
failed = Path(os.environ["BM25_FAILED_SENTINEL"])

try:
    print(
        "[entrypoint] BM25 downloader started "
        f"index_path={index_path} hf_token_present={bool(os.environ.get('HF_TOKEN'))}",
        flush=True,
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bm25-download-", dir=str(index_path.parent)))
    print(f"[entrypoint] Downloading BM25 snapshot into temporary directory {temp_root}", flush=True)
    snapshot_download(
        repo_id="Tevatron/browsecomp-plus-indexes",
        repo_type="dataset",
        allow_patterns=["bm25/*"],
        local_dir=str(temp_root),
    )
    print(f"[entrypoint] Hugging Face snapshot download completed at {temp_root}", flush=True)
    downloaded = temp_root / "bm25"
    if not downloaded.exists():
        raise FileNotFoundError(f"Downloaded index directory missing: {downloaded}")
    if index_path.exists():
        shutil.rmtree(index_path)
    print(f"[entrypoint] Promoting downloaded BM25 index into {index_path}", flush=True)
    shutil.move(str(downloaded), str(index_path))
    shutil.rmtree(temp_root, ignore_errors=True)
    ready.touch()
    print(f"[entrypoint] BM25 index downloaded to {index_path}", flush=True)
except Exception as exc:
    failed.write_text(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
    print(f"[entrypoint] BM25 index download failed: {exc}", flush=True)
PYEOF
    # Wait for download to complete before starting server
    while [[ ! -f "$BM25_READY_SENTINEL" && ! -f "$BM25_FAILED_SENTINEL" ]]; do
        echo "[entrypoint] BM25 download still running..."
        sleep 5
    done

    if [[ -f "$BM25_FAILED_SENTINEL" ]]; then
        echo "[entrypoint] FATAL: BM25 index download failed:"
        cat "$BM25_FAILED_SENTINEL"
        exit 1
    fi
fi

exec .venv/bin/python src/server.py "$@"
