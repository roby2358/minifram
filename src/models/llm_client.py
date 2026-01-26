"""LLM client for local model interaction."""
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """HTTP client for local LLM (GLM or OpenAI-compatible)."""

    def __init__(self, endpoint: str, model: str, timeout: float = 60.0):
        self.endpoint = endpoint
        self.model = model
        self.client = httpx.AsyncClient(timeout=timeout)

    def _log_request(self, payload: dict, label: str = "REQUEST") -> None:
        """Log request payload for debugging."""
        logger.debug("%s TO MODEL:\n%s", label, json.dumps(payload, indent=2))

    def _log_response(self, result: dict, label: str = "RESPONSE") -> None:
        """Log response body for debugging."""
        logger.debug("%s FROM MODEL:\n%s", label, json.dumps(result, indent=2))

    async def _send_request(self, payload: dict, label: str = "") -> dict:
        """Send request and return response, with logging."""
        prefix = f"{label} " if label else ""
        self._log_request(payload, f"{prefix}REQUEST")

        response = await self.client.post(self.endpoint, json=payload)
        response.raise_for_status()
        result = response.json()

        self._log_response(result, f"{prefix}RESPONSE")
        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None
    ) -> dict:
        """Send chat completion request to local LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            LLM response dict
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools

        try:
            return await self._send_request(payload)
        except httpx.HTTPStatusError as e:
            # If tools caused the error (400), retry without tools
            if e.response.status_code == 400 and tools:
                logger.warning("Tool call failed (400), retrying without tools")
                payload.pop("tools", None)
                result = await self._send_request(payload, "RETRY")
                result["_tools_unsupported"] = True
                return result
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
