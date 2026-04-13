# BrowseComp-Plus Dummy Purple Agent

A single dummy purple agent for the BrowseComp-Plus benchmark that handles research and local BM25 retrieval in one process.

Use this to test the green → purple pipeline end to end without needing a real reasoning model or correct answers.

## What It Does

For each task received from the green agent, the dummy purple agent:

1. Runs a BM25 search locally over the pre-baked index
2. Ignores the retrieval results
3. Returns `"I don't know."` as the final answer

The BM25 index is downloaded from HuggingFace and baked into the Docker image at build time. The entrypoint validates it before the server starts.

Any retrieval error at request time (unexpected search failure) is surfaced in the answer artifact so green can record it alongside the dummy answer.

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

## Data Requirements

The BM25 index from HuggingFace (`Tevatron/browsecomp-plus-indexes`) is downloaded into `BM25_INDEX_PATH` (default `/data/indexes/bm25`) at image build time. No network access is required at runtime.

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

The Amber manifest exposes one A2A endpoint. No config parameters are required.

## Testing

```bash
uv sync --extra test
uv run pytest --agent-url http://localhost:9009
```

The tests cover the A2A surface only. They do not verify real BM25 search results unless you provide a valid index at runtime.
