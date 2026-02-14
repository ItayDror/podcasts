import re
from dataclasses import dataclass, field


@dataclass
class QualityResult:
    passed: bool
    score: float  # 0.0 to 1.0
    issues: list[str] = field(default_factory=list)


def check_transcript_quality(
    text: str,
    expected_duration_seconds: float | None = None,
    threshold: float = 0.7,
) -> QualityResult:
    """
    Evaluate transcript quality using heuristics.
    Returns a QualityResult with a score and list of issues found.

    Checks:
    1. Word count vs expected duration (~150 words/min)
    2. Punctuation ratio (sentences ending in .?!)
    3. Garbled text detection (repeated words, very short words)
    """
    issues = []
    scores = []

    words = text.split()
    word_count = len(words)

    if word_count < 10:
        return QualityResult(passed=False, score=0.0, issues=["Transcript is nearly empty"])

    # Check 1: Word count vs expected duration
    if expected_duration_seconds and expected_duration_seconds > 0:
        expected_words = (expected_duration_seconds / 60) * 150
        word_ratio = word_count / expected_words
        if word_ratio < 0.3:
            issues.append(
                f"Very low word count: {word_count} words for "
                f"{expected_duration_seconds / 60:.0f} min "
                f"(expected ~{expected_words:.0f})"
            )
            scores.append(0.2)
        elif word_ratio < 0.5:
            issues.append(
                f"Low word count: {word_count} words for "
                f"{expected_duration_seconds / 60:.0f} min "
                f"(expected ~{expected_words:.0f})"
            )
            scores.append(0.5)
        else:
            scores.append(min(1.0, word_ratio))

    # Check 2: Punctuation ratio
    # Split on common sentence boundaries and check if they end properly
    segments = re.split(r"(?<=[.!?])\s+", text)
    if len(segments) > 1:
        punctuated = sum(
            1 for s in segments if s.strip() and s.strip()[-1] in ".!?"
        )
        punct_ratio = punctuated / len(segments)
        if punct_ratio < 0.1:
            issues.append(
                f"Very low punctuation: {punct_ratio:.0%} of segments "
                f"end with sentence-ending punctuation"
            )
            scores.append(0.3)
        elif punct_ratio < 0.3:
            issues.append(f"Low punctuation ratio: {punct_ratio:.0%}")
            scores.append(0.5)
        else:
            scores.append(min(1.0, punct_ratio))
    else:
        # Single segment with no sentence breaks — likely poor quality
        if word_count > 100:
            issues.append("No sentence boundaries detected in long text")
            scores.append(0.3)

    # Check 3: Garbled text detection
    # Look for repeated consecutive words (common in bad auto-captions)
    repeated_count = 0
    for i in range(len(words) - 1):
        if words[i].lower() == words[i + 1].lower() and len(words[i]) > 1:
            repeated_count += 1
    repeat_ratio = repeated_count / max(word_count, 1)
    if repeat_ratio > 0.05:
        issues.append(f"High word repetition: {repeat_ratio:.1%}")
        scores.append(0.4)
    else:
        scores.append(1.0 - repeat_ratio)

    # Check 4: Average word length (garbled text often has very short words)
    avg_word_len = sum(len(w) for w in words) / max(word_count, 1)
    if avg_word_len < 3.0:
        issues.append(f"Unusually short average word length: {avg_word_len:.1f}")
        scores.append(0.4)
    else:
        scores.append(min(1.0, avg_word_len / 5.0))

    # Combine scores
    final_score = sum(scores) / len(scores) if scores else 0.0
    passed = final_score >= threshold and not any(
        "Very low" in issue or "nearly empty" in issue for issue in issues
    )

    return QualityResult(passed=passed, score=round(final_score, 2), issues=issues)
