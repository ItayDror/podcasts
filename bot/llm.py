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
        Returns (assistant_response_text, updated_conversation_history).
        """
        system = CHAT_SYSTEM_PROMPT.format(title=title, insights=insights)
        tools = _chat_tools()

        # Build messages: prior history + new user message
        messages = list(conversation_history) + [
            {"role": "user", "content": user_message}
        ]

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=system,
            messages=messages,
            tools=tools,
        )

        # Process response — handle text + tool_use blocks
        text_parts, tool_results = _process_response(response, transcript)

        # If there were tool calls, send results back and get final response
        if tool_results:
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            final_response = self._client.messages.create(
                model=self._model,
                max_tokens=1500,
                system=system,
                messages=messages,
                tools=tools,
            )
            assistant_text = _extract_text(final_response)
            messages.append(
                {"role": "assistant", "content": final_response.content}
            )
        else:
            assistant_text = "\n".join(text_parts)
            messages.append({"role": "assistant", "content": response.content})

        return assistant_text, messages


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


def _extract_text(response) -> str:
    return "\n".join(
        block.text for block in response.content if block.type == "text"
    )


def _truncate(transcript: str) -> str:
    if len(transcript) <= MAX_TRANSCRIPT_CHARS:
        return transcript
    return transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated due to length]"
