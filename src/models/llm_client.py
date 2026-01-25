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
        messages: list[dict[str, str]],
        tools: list[dict] = None
    ) -> dict:
        """Send chat completion request to local LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            LLM response dict
        """
        payload = {
            "model": self.model,
            "messages": messages,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools

        try:
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # If tools caused the error (400), retry without tools
            if e.response.status_code == 400 and tools:
                payload.pop("tools", None)
                response = await self.client.post(self.endpoint, json=payload)
                response.raise_for_status()
                result = response.json()
                # Mark that tools aren't supported
                result["_tools_unsupported"] = True
                return result
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
