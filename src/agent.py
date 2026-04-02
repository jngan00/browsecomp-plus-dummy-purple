"""
Dummy research purple agent for BrowseComp-Plus.

Exercises the full green↔research↔retrieval pipeline without doing real research:
  1. Extracts the retrieval agent URL from green's prompt
  2. Sends one real query to the retrieval agent (verifies connectivity)
  3. Returns a fixed answer string

This is useful for testing green-agent plumbing end-to-end without
needing an LLM or correct answers.
"""
import asyncio
import re
import time

from a2a.server.tasks import TaskUpdater
from a2a.types import Message, Part, TaskState, TextPart
from a2a.utils import get_message_text, new_agent_text_message

from messenger import Messenger

DUMMY_ANSWER = "I don't know."
RETRIEVAL_WARMING_MARKER = "[retrieval-index-warming]"
RETRIEVAL_FAILED_MARKER = "[retrieval-index-failed]"
RETRIEVAL_MAX_WAIT_SEC = 180
RETRIEVAL_RETRY_SEC = 5

# Matches the retrieval agent URL embedded in green's prompt:
#   Send your query as a plain text A2A message to: http://host:port/
_RETRIEVAL_URL_RE = re.compile(r"A2A message to:\s*(https?://\S+)")


class Agent:
    def __init__(self):
        self.messenger = Messenger()

    async def run(self, message: Message, updater: TaskUpdater) -> None:
        input_text = get_message_text(message)

        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Dummy research agent received task."),
        )

        retrieval_url = _extract_retrieval_url(input_text)
        if retrieval_url:
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"Calling retrieval agent at {retrieval_url} ..."),
            )
            result = await _call_retrieval(self.messenger, retrieval_url, input_text[:200])
            if result:
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "Retrieval agent responded. Ignoring result — this is a dummy agent."
                    ),
                )
        else:
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("No retrieval URL found in prompt; skipping retrieval."),
            )

        await updater.add_artifact(
            parts=[Part(root=TextPart(text=DUMMY_ANSWER))],
            name="Answer",
        )


def _extract_retrieval_url(text: str) -> str | None:
    m = _RETRIEVAL_URL_RE.search(text)
    return m.group(1) if m else None


async def _call_retrieval(messenger: Messenger, url: str, query: str) -> str | None:
    deadline = time.monotonic() + RETRIEVAL_MAX_WAIT_SEC

    while True:
        try:
            response = await messenger.talk_to_agent(
                message=query,
                url=url,
                new_conversation=True,
                timeout=60,
            )
        except Exception as exc:
            print(f"[dummy-research] retrieval call failed: {exc}")
            return None

        if RETRIEVAL_FAILED_MARKER in response:
            print(f"[dummy-research] retrieval reported failure: {response}")
            return None

        if RETRIEVAL_WARMING_MARKER not in response:
            return response

        if time.monotonic() >= deadline:
            print("[dummy-research] retrieval stayed in warmup too long")
            return None

        await asyncio.sleep(RETRIEVAL_RETRY_SEC)
