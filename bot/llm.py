import logging

import anthropic

from bot.prompts import (
    INSIGHTS_SYSTEM_PROMPT,
    INSIGHTS_USER_PROMPT,
    CHAT_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Max transcript chars to send to Claude (~150K chars ≈ ~37K tokens,
# leaves room for system prompt + conversation history + response)
MAX_TRANSCRIPT_CHARS = 150_000


class LLMClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate_insights(self, title: str, transcript: str) -> str:
        """One-shot insights generation. Returns insights as markdown text."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=INSIGHTS_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": INSIGHTS_USER_PROMPT.format(
                        title=title,
                        transcript=_truncate(transcript),
                    ),
                }
            ],
        )
        return response.content[0].text

    def chat(
        self,
        title: str,
        insights: str,
        transcript: str,
        conversation_history: list[dict],
        user_message: str,
    ) -> tuple[str, list[dict]]:
        """
        Multi-turn chat with tool_use.
        Loops on tool calls until the model produces a text response
        (up to MAX_TOOL_ROUNDS to prevent infinite loops).
        Returns (assistant_response_text, updated_conversation_history).
        """
        MAX_TOOL_ROUNDS = 5
        system = CHAT_SYSTEM_PROMPT.format(title=title, insights=insights)
        tools = _chat_tools()

        # Sanitize history: drop orphaned tool_use messages that lack tool_results
        clean_history = _sanitize_history(conversation_history)

        # Build messages: prior history + new user message
        messages = list(clean_history) + [
            {"role": "user", "content": user_message}
        ]

        all_text_parts = []

        for round_num in range(MAX_TOOL_ROUNDS + 1):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1500,
                system=system,
                messages=messages,
                tools=tools,
            )

            text_parts, tool_results = _process_response(response, transcript)
            all_text_parts.extend(text_parts)

            # Always append the assistant response to messages
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})

            if not tool_results:
                # No tool calls — model is done, break out
                break

            # Tool calls present — append results and loop for next response
            messages.append({"role": "user", "content": tool_results})
            logger.debug("Tool use round %d, looping for next response", round_num + 1)

        assistant_text = "\n".join(all_text_parts).strip()

        # Safety: never return empty text (Telegram rejects empty messages)
        if not assistant_text:
            logger.warning("LLM returned no text after %d rounds, returning fallback", round_num + 1)
            assistant_text = "I processed your request but couldn't generate a text response. Please try rephrasing your question."

        return assistant_text, messages


def _sanitize_history(history: list[dict]) -> list[dict]:
    """Remove trailing messages that would violate the Anthropic API contract.

    The API requires every assistant message containing tool_use blocks to be
    immediately followed by a user message with matching tool_result blocks.
    If a previous crash left orphaned tool_use messages at the end of the
    history, we trim them off so the next API call doesn't fail with a 400.
    """
    clean = list(history)
    while clean:
        last = clean[-1]
        # Check if the last message is an assistant message with tool_use blocks
        if last.get("role") == "assistant":
            content = last.get("content", [])
            if isinstance(content, list) and any(
                isinstance(block, dict) and block.get("type") == "tool_use"
                for block in content
            ):
                # Orphaned tool_use at the end — remove it
                logger.warning("Removing orphaned tool_use message from conversation history")
                clean.pop()
                continue
        # Also remove trailing user messages with tool_result (orphaned results
        # without a preceding tool_use, or leftover from partial flow)
        if last.get("role") == "user":
            content = last.get("content", [])
            if isinstance(content, list) and all(
                isinstance(block, dict) and block.get("type") == "tool_result"
                for block in content
            ):
                logger.warning("Removing orphaned tool_result message from conversation history")
                clean.pop()
                continue
        break
    return clean


def _chat_tools() -> list[dict]:
    return [
        {
            "name": "search_transcript",
            "description": (
                "Search the podcast transcript for a specific topic, "
                "keyword, or quote. Returns relevant excerpts with context."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term or topic to find",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "update_insights",
            "description": (
                "Replace the current insights with updated content. "
                "Use when the user wants to modify the insights."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "new_insights": {
                        "type": "string",
                        "description": "The complete updated insights markdown",
                    }
                },
                "required": ["new_insights"],
            },
        },
    ]


def _process_response(
    response, transcript: str
) -> tuple[list[str], list[dict]]:
    """Extract text parts and handle tool calls."""
    text_parts = []
    tool_results = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            result = _execute_tool(block.name, block.input, transcript)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
            )

    return text_parts, tool_results


def _execute_tool(name: str, inputs: dict, transcript: str) -> str:
    """Execute a tool call locally and return the result string."""
    if name == "search_transcript":
        return _search_transcript(transcript, inputs["query"])
    elif name == "update_insights":
        return "Insights updated successfully."
    return f"Unknown tool: {name}"


def _search_transcript(transcript: str, query: str) -> str:
    """Simple keyword search in the transcript. Returns surrounding context."""
    query_lower = query.lower()
    sentences = transcript.replace(".\n", ". ").split(". ")
    matches = []

    for i, sentence in enumerate(sentences):
        if query_lower in sentence.lower():
            start = max(0, i - 1)
            end = min(len(sentences), i + 2)
            context = ". ".join(sentences[start:end]).strip()
            if context and context not in matches:
                matches.append(context)
            if len(matches) >= 3:
                break

    if not matches:
        return f"No mentions of '{query}' found in the transcript."
    return "\n\n---\n\n".join(matches)


def _serialize_content(content) -> list[dict]:
    """Convert Anthropic SDK content blocks to plain dicts for JSON storage."""
    serialized = []
    for block in content:
        if hasattr(block, "model_dump"):
            serialized.append(block.model_dump())
        elif isinstance(block, dict):
            serialized.append(block)
        else:
            serialized.append({"type": "text", "text": str(block)})
    return serialized


def _extract_text(response) -> str:
    return "\n".join(
        block.text for block in response.content if block.type == "text"
    )


def _truncate(transcript: str) -> str:
    if len(transcript) <= MAX_TRANSCRIPT_CHARS:
        return transcript
    return transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated due to length]"
