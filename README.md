# BrowseComp-Plus Dummy Purple Agent

A minimal dummy purple agent for the BrowseComp-Plus benchmark.

Use this to test the green → purple → retrieval pipeline end to end without needing a real reasoning model or correct answers.

## What It Does

For each task received from the green agent, the dummy purple agent:

1. Parses the retrieval agent URL embedded in green's prompt
2. Sends one real query to that retrieval participant to verify connectivity
3. Ignores the retrieval result
4. Returns `"I don't know."` as the final answer

This means it should consistently score `0`, but it still exercises the wiring between green, purple, and retrieval.

## Architecture

```text
BrowseComp-Plus Green
  → prompt with retrieval agent URL → Dummy Purple
    → one A2A query → Retrieval agent
    → final answer: "I don't know."
```

## Project Structure

```text
src/
├─ server.py      # A2A server
├─ executor.py    # A2A request handling
├─ agent.py       # Dummy purple behavior
└─ messenger.py   # A2A client utilities
Dockerfile
pyproject.toml
```

## Prompt Contract

The agent expects the incoming prompt to contain a line like:

```text
Send your query as a plain text A2A message to: http://retrieval-agent/
```

It extracts that URL, makes one retrieval call, and then returns the fixed answer.

## Running Locally

```bash
uv sync
uv run src/server.py --host 0.0.0.0 --port 9009
```

Point the green agent's `agent` participant at this service. Green must still be configured with a separate `retrieval` participant.

## Running With Docker

```bash
docker build -t browsecomp-plus-dummy-purple .
docker run -p 9009:9009 browsecomp-plus-dummy-purple
```

## Amber Manifest

The current Amber manifest exposes a single A2A endpoint and does not use Amber's experimental Docker feature.

## Testing

```bash
uv sync --extra test
uv run pytest --agent-url http://localhost:9009
```

The tests cover the A2A surface only. They do not run a full green + retrieval integration flow.
