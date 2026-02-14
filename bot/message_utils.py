import os
import tempfile

TELEGRAM_MAX_LENGTH = 4096
SAFE_MAX_LENGTH = 4000  # Reserve space for formatting overhead


def split_message(text: str, max_length: int = SAFE_MAX_LENGTH) -> list[str]:
    """
    Split a long message into chunks that fit Telegram's limit.
    Splits at paragraph boundaries first, then sentence boundaries,
    then falls back to hard cut.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to split at a paragraph boundary (double newline)
        split_pos = remaining.rfind("\n\n", 0, max_length)

        if split_pos == -1 or split_pos < max_length // 2:
            # Try single newline
            split_pos = remaining.rfind("\n", 0, max_length)

        if split_pos == -1 or split_pos < max_length // 2:
            # Try sentence boundary
            for sep in [". ", "! ", "? "]:
                pos = remaining.rfind(sep, 0, max_length)
                if pos > max_length // 2:
                    split_pos = pos + len(sep)
                    break

        if split_pos == -1 or split_pos < max_length // 2:
            # Hard cut at max_length
            split_pos = max_length

        chunks.append(remaining[:split_pos].rstrip())
        remaining = remaining[split_pos:].lstrip()

    return chunks


def format_insights_for_telegram(insights: str) -> str:
    """
    Convert markdown to Telegram-compatible HTML.
    Using HTML parse mode to avoid MarkdownV2 escaping nightmares.
    """
    lines = insights.split("\n")
    converted = []
    for line in lines:
        if line.startswith("### "):
            converted.append(f"\n<b>{_escape_html(line[4:])}</b>\n")
        elif line.startswith("## "):
            converted.append(f"\n<b>{_escape_html(line[3:])}</b>\n")
        elif line.startswith("# "):
            converted.append(f"\n<b>{_escape_html(line[2:])}</b>\n")
        elif line.startswith("- "):
            converted.append(f"\n\u2022 {_convert_inline_bold(line[2:])}")
        elif line.strip() == "":
            converted.append("")
        else:
            converted.append(_convert_inline_bold(line))
    return "\n".join(converted)


def _convert_inline_bold(text: str) -> str:
    """Convert **bold** markdown to <b>bold</b> HTML, escaping the rest."""
    import re
    parts = re.split(r"(\*\*.*?\*\*)", text)
    result = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            result.append(f"<b>{_escape_html(part[2:-2])}</b>")
        else:
            result.append(_escape_html(part))
    return "".join(result)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_long_message(update, context, text: str, parse_mode=None):
    """Send a message, splitting into chunks if necessary."""
    chunks = split_message(text)
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode=parse_mode)


async def send_as_file(update, context, text: str, filename: str):
    """Send text content as a file attachment."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix="transcript_"
    ) as f:
        f.write(text)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            await update.message.reply_document(document=f, filename=filename)
    finally:
        os.remove(temp_path)
