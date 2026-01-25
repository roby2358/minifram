"""LLM client for local model interaction."""
import httpx
from typing import AsyncIterator


class LLMClient:
    """HTTP client for local LLM (GLM or OpenAI-compatible)."""

    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: list[dict[str, str]]
    ) -> dict:
        """Send chat completion request to local LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            LLM response dict
        """
        payload = {
            "model": self.model,
            "messages": messages,
        }

        response = await self.client.post(self.endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
