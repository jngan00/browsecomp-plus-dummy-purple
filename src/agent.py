"""
Dummy purple agent for BrowseComp-Plus.

Handles research tasks in a single process: runs local BM25 retrieval
over the pre-baked index, then returns a fixed dummy answer. There is
no separate retrieval agent — retrieval is performed locally.

The BM25 index is baked into the Docker image at build time; the
entrypoint validates it before the server starts, so by the time this
module runs the index is guaranteed to be usable. Any retrieval error
encountered at request time is surfaced in the answer artifact so it
propagates back to green's rewards output instead of being silently
swallowed.
"""
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
DEFAULT_K = int(os.environ.get("DEFAULT_K", "5"))

DUMMY_ANSWER = "I don't know."


class Agent:
    def __init__(self) -> None:
        self._searcher = None

    def _get_searcher(self):
        if self._searcher is None:
            from pyserini.search.lucene import LuceneSearcher

            self._searcher = LuceneSearcher(BM25_INDEX_PATH)
        return self._searcher

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

    async def run(self, message: Message, updater: TaskUpdater) -> None:
        input_text = get_message_text(message).strip()

        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Dummy research agent received task. Running local retrieval..."),
        )

        search_error: str | None = None
        results: list[dict] = []
        try:
            results = self._search(input_text[:200])
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

        answer_parts: list[Part] = [
            Part(root=TextPart(text=DUMMY_ANSWER)),
            Part(
                root=DataPart(
                    data={
                        "answer": DUMMY_ANSWER,
                        "retrieval_result_count": len(results),
                        "retrieval_error": search_error,
                    }
                )
            ),
        ]

        await updater.add_artifact(parts=answer_parts, name="Answer")
