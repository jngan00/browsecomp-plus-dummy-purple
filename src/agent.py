"""
Dummy purple agent for BrowseComp-Plus.

Handles research tasks in a single process: runs local BM25 retrieval
over the pre-downloaded index, then returns a fixed dummy answer. There
is no separate retrieval agent — retrieval is performed locally.

Errors from BM25 search (or missing index) are surfaced to the caller
via the answer artifact so they propagate into green's final rewards
output instead of being silently swallowed.
"""
import asyncio
import json
import os
from pathlib import Path

from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Message, Part, TaskState, TextPart
from a2a.utils import get_message_text, new_agent_text_message

# ---------------------------------------------------------------------------
# BM25 index configuration
# ---------------------------------------------------------------------------
BM25_INDEX_PATH = os.environ.get("BM25_INDEX_PATH", "/data/indexes/bm25")
BM25_READY_SENTINEL = Path(
    os.environ.get("BM25_INDEX_READY_SENTINEL", f"{BM25_INDEX_PATH}.ready")
)
BM25_FAILED_SENTINEL = Path(
    os.environ.get("BM25_INDEX_FAILED_SENTINEL", f"{BM25_INDEX_PATH}.failed")
)
DEFAULT_K = int(os.environ.get("DEFAULT_K", "5"))
WARMING_RETRY_AFTER_SEC = int(os.environ.get("BM25_WARMING_RETRY_AFTER_SEC", "5"))
RETRIEVAL_MAX_WAIT_SEC = int(os.environ.get("RETRIEVAL_MAX_WAIT_SEC", "180"))
SKIP_INDEX_DOWNLOAD = os.environ.get("SKIP_INDEX_DOWNLOAD", "").lower() == "true"

DUMMY_ANSWER = "I don't know."


class Agent:
    def __init__(self) -> None:
        self._searcher = None

    # ------------------------------------------------------------------
    # BM25 helpers
    # ------------------------------------------------------------------
    def _get_searcher(self):
        if self._searcher is None:
            from pyserini.search.lucene import LuceneSearcher

            self._searcher = LuceneSearcher(BM25_INDEX_PATH)
        return self._searcher

    def _index_ready(self) -> bool:
        if BM25_READY_SENTINEL.exists():
            return True
        index_dir = Path(BM25_INDEX_PATH)
        if index_dir.exists() and list(index_dir.glob("segments_*")):
            return True
        return False

    def _search(self, query: str, k: int = DEFAULT_K) -> list[dict]:
        """Run BM25 search. Raises on failure so callers can surface the error."""
        searcher = self._get_searcher()
        hits = searcher.search(query, k)
        results = []
        for hit in hits:
            raw = json.loads(hit.lucene_document.get("raw"))
            results.append(
                {
                    "docid": hit.docid,
                    "score": float(hit.score),
                    "text": raw["contents"],
                }
            )
        return results

    async def _wait_for_index(self) -> None:
        """Block until index is ready, failed, or timeout. Raises on failure/timeout."""
        elapsed = 0
        while not self._index_ready() and not BM25_FAILED_SENTINEL.exists():
            if elapsed >= RETRIEVAL_MAX_WAIT_SEC:
                raise TimeoutError(
                    f"BM25 index not ready after {RETRIEVAL_MAX_WAIT_SEC}s"
                )
            await asyncio.sleep(WARMING_RETRY_AFTER_SEC)
            elapsed += WARMING_RETRY_AFTER_SEC

        if BM25_FAILED_SENTINEL.exists():
            details = BM25_FAILED_SENTINEL.read_text(encoding="utf-8").strip()
            raise RuntimeError(f"BM25 index download failed: {details}")

    # ------------------------------------------------------------------
    # Entry point — receives a research prompt from green, runs local
    # BM25 search to exercise the pipeline, and returns the dummy answer.
    # Any error is surfaced in the answer artifact so green can record it
    # in per-query rewards.
    # ------------------------------------------------------------------
    async def run(self, message: Message, updater: TaskUpdater) -> None:
        input_text = get_message_text(message).strip()

        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Dummy research agent received task. Running local retrieval..."),
        )

        search_error: str | None = None
        results: list[dict] = []

        if SKIP_INDEX_DOWNLOAD and not self._index_ready():
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("Index download skipped; skipping retrieval."),
            )
        else:
            try:
                await self._wait_for_index()
                query = input_text[:200]
                results = self._search(query)
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        f"Local retrieval returned {len(results)} result(s). "
                        "Ignoring — this is a dummy agent."
                    ),
                )
            except Exception as exc:
                search_error = f"{type(exc).__name__}: {exc}"
                print(f"[dummy-purple] retrieval failed: {search_error}")
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(f"Local retrieval failed: {search_error}"),
                )

        answer_parts: list[Part] = [Part(root=TextPart(text=DUMMY_ANSWER))]
        answer_parts.append(
            Part(
                root=DataPart(
                    data={
                        "answer": DUMMY_ANSWER,
                        "retrieval_result_count": len(results),
                        "retrieval_error": search_error,
                    }
                )
            )
        )

        await updater.add_artifact(parts=answer_parts, name="Answer")
