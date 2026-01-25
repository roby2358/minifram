"""LLM client for local model interaction."""
import httpx
import json
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

        # Echo request payload
        print("\n" + "="*80)
        print("🔵 REQUEST TO MODEL:")
        print(json.dumps(payload, indent=2))
        print("="*80 + "\n")

        try:
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

            # Echo response body
            print("\n" + "="*80)
            print("🟢 RESPONSE FROM MODEL:")
            print(json.dumps(result, indent=2))
            print("="*80 + "\n")

            return result
        except httpx.HTTPStatusError as e:
            # If tools caused the error (400), retry without tools
            if e.response.status_code == 400 and tools:
                print(f"⚠️  Tool call failed (400), retrying without tools\n")
                payload.pop("tools", None)

                print("\n" + "="*80)
                print("🔵 RETRY REQUEST TO MODEL:")
                print(json.dumps(payload, indent=2))
                print("="*80 + "\n")

                response = await self.client.post(self.endpoint, json=payload)
                response.raise_for_status()
                result = response.json()

                # Echo response body
                print("\n" + "="*80)
                print("🟢 RETRY RESPONSE FROM MODEL:")
                print(json.dumps(result, indent=2))
                print("="*80 + "\n")

                # Mark that tools aren't supported
                result["_tools_unsupported"] = True
                return result
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
