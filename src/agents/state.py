"""In-memory state management for agents."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.foundation.state import Conversation


class AgentStatus(Enum):
    """Agent execution states."""
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class AgentOutput:
    """A single output entry from an agent."""
    type: str  # 'assistant', 'tool', 'error', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_call: str | None = None


@dataclass
class Agent:
    """An autonomous agent with a contract."""
    id: str
    contract: str = ""
    status: AgentStatus = AgentStatus.READY
    output: list[AgentOutput] = field(default_factory=list)
    conversation: Conversation | None = None
    created_at: datetime = field(default_factory=datetime.now)
    stop_requested: bool = False
    # MCP-related fields
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stopped_at: datetime | None = None
    summary: str | None = None
    payload: bytes | None = None  # gzip-compressed
    payload_size: int | None = None  # original uncompressed size

    def add_output(self, type: str, content: str, tool_call: str | None = None):
        """Add an output entry."""
        entry = AgentOutput(type=type, content=content, tool_call=tool_call)
        self.output.append(entry)
        return entry

    def request_stop(self):
        """Request the agent to stop after current operation."""
        self.stop_requested = True

    def reset_for_restart(self):
        """Reset agent state for a new run."""
        self.status = AgentStatus.READY
        self.output = []
        self.conversation = None
        self.stop_requested = False


class AgentStore:
    """In-memory storage for all agents."""

    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self._next_id = 1

    def create(self) -> Agent:
        """Create a new agent with auto-generated ID."""
        agent_id = f"agent-{self._next_id}"
        self._next_id += 1
        agent = Agent(id=agent_id)
        self.agents[agent_id] = agent
        return agent

    def get(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def delete(self, agent_id: str):
        """Delete an agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]

    def get_all(self) -> list[Agent]:
        """Get all agents."""
        return list(self.agents.values())
