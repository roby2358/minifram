"""In-memory state management for conversations."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_call: Optional[str] = None  # For displaying tool calls


@dataclass
class Conversation:
    """A conversation thread."""
    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str, tool_call: Optional[str] = None):
        """Add a message to the conversation."""
        msg = Message(role=role, content=content, tool_call=tool_call)
        self.messages.append(msg)
        return msg

    def to_llm_format(self) -> list[dict]:
        """Convert conversation to LLM API format."""
        result = []
        for msg in self.messages:
            if msg.role in ('user', 'assistant', 'system'):
                # Include tool_call data if present
                if msg.tool_call:
                    # This is a tool call message
                    result.append({
                        "role": msg.role,
                        "content": msg.content,
                        "tool_call_data": msg.tool_call  # Store for reconstruction
                    })
                else:
                    result.append({"role": msg.role, "content": msg.content})
            elif msg.role == 'tool':
                # Tool result message
                result.append({
                    "role": "tool",
                    "content": msg.content
                })
        return result


class ConversationStore:
    """In-memory storage for all conversations."""

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def create(self, conv_id: str) -> Conversation:
        """Create a new conversation."""
        conv = Conversation(id=conv_id)
        self.conversations[conv_id] = conv
        return conv

    def get(self, conv_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conv_id)

    def get_or_create(self, conv_id: str) -> Conversation:
        """Get existing conversation or create new one."""
        if conv_id not in self.conversations:
            return self.create(conv_id)
        return self.conversations[conv_id]

    def delete(self, conv_id: str):
        """Delete a conversation."""
        if conv_id in self.conversations:
            del self.conversations[conv_id]
