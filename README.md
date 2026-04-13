# BrowseComp-Plus Dummy Purple Agent

A single dummy purple agent for the BrowseComp-Plus benchmark that handles research and local BM25 retrieval in one process.

Use this to test the green → purple pipeline end to end without needing a real reasoning model or correct answers.

## What It Does

For each task received from the green agent, the dummy purple agent:

1. Waits for the local BM25 index to be ready
2. Runs a BM25 search locally over the pre-downloaded index
3. Ignores the retrieval results
4. Returns `"I don't know."` as the final answer

Any retrieval error (missing index, search failure, timeout) is surfaced in the answer artifact so green can record it in the per-query rewards output.

This means it should consistently score `0`, but it still exercises the wiring between green and purple and the local BM25 retrieval stack.

## Architecture

```text
BrowseComp-Plus Green
  → research prompt → Dummy Purple
    → local BM25 search (Pyserini/Lucene)
    → final answer: "I don't know."
```

## Project Structure

```text
src/
├─ server.py      # A2A server
├─ executor.py    # A2A request handling
└─ agent.py       # Research + local BM25 retrieval
entrypoint.sh     # BM25 index download and validation
Dockerfile
pyproject.toml
```

## Response Artifact

The answer artifact contains:

- `TextPart`: `"I don't know."`
- `DataPart`:

  ```json
  {
    "answer": "I don't know.",
    "retrieval_result_count": 5,
    "retrieval_error": null
  }
  ```

If BM25 retrieval failed, `retrieval_error` contains the error message and `retrieval_result_count` is `0`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BM25_INDEX_PATH` | No | Path to the Lucene BM25 index. Defaults to `/data/indexes/bm25` |
| `DEFAULT_K` | No | Number of hits to return. Defaults to `5` |
| `HF_TOKEN` | No | HuggingFace token for faster index downloads |
| `SKIP_INDEX_DOWNLOAD` | No | Set to `true` to skip the BM25 index download. Retrieval returns empty results |
| `RETRIEVAL_MAX_WAIT_SEC` | No | Max seconds to wait for the index to become ready. Defaults to `180` |

## Data Requirements

On startup the entrypoint downloads the BM25 index from HuggingFace (`Tevatron/browsecomp-plus-indexes`) into `BM25_INDEX_PATH` (default `/data/indexes/bm25`). If a valid cached index already exists at the path, the download is skipped.

## Running Locally

```bash
uv sync
BM25_INDEX_PATH=/path/to/bm25 uv run src/server.py --host 0.0.0.0 --port 9009
```

Java is required because Pyserini depends on the Lucene/Anserini stack.

## Running With Docker

```bash
docker build -t browsecomp-plus-dummy-purple .
docker run -p 9009:9009 browsecomp-plus-dummy-purple
```

## Amber Manifest

The Amber manifest exposes one A2A endpoint and accepts optional `hf_token` and `skip_index_download` config parameters.

## Testing

```bash
uv sync --extra test
uv run pytest --agent-url http://localhost:9009
```

The tests cover the A2A surface only. They do not verify real BM25 search results unless you provide a valid index at runtime.
