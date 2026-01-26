"""Reasoning extraction from LLM responses."""
import re


def extract_reasoning_field(message: dict) -> str | None:
    """Extract reasoning from message.reasoning field (GLM-4.7-flash)."""
    return message.get("reasoning")


def extract_think_tags(content: str) -> tuple[str | None, str]:
    """Extract <think>/<thinking> tags from content.

    Handles both tag variants and unclosed tags.

    Returns:
        (reasoning, cleaned_content) tuple
    """
    if not content:
        return None, content

    # Quick check for any think tags
    if not any(tag in content for tag in ["<think>", "</think>", "<thinking>", "</thinking>"]):
        return None, content

    all_reasoning = []
    cleaned = content

    for tag in ["thinking", "think"]:
        # Extract and remove complete tag pairs
        pattern = rf'<{tag}>(.*?)</{tag}>'
        all_reasoning.extend(re.findall(pattern, cleaned, re.DOTALL))
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)

        # Handle unclosed tags
        if f"<{tag}>" in cleaned:
            unclosed = re.search(rf'<{tag}>(.*)$', cleaned, re.DOTALL)
            if unclosed:
                all_reasoning.append(unclosed.group(1))
                cleaned = re.sub(rf'<{tag}>(.*)$', '', cleaned, flags=re.DOTALL)

        # Remove stray closing tags
        cleaned = cleaned.replace(f"</{tag}>", '')

    if not all_reasoning:
        return None, cleaned.strip()

    reasoning = "\n\n".join(r.strip() for r in all_reasoning if r.strip())
    return reasoning if reasoning else None, cleaned.strip()


def extract_reasoning(message: dict, content: str) -> tuple[str | None, str]:
    """Extract reasoning from message, trying field first then tags.

    Returns:
        (reasoning, cleaned_content) tuple
    """
    reasoning = extract_reasoning_field(message)
    if reasoning:
        return reasoning, content
    return extract_think_tags(content)
