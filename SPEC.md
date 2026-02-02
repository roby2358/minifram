# Self-Modifying Agent System - Technical Specification

A sandboxed, self-modifying AI agent that communicates with the outside world exclusively through git.

## Purpose

This system provides a secure environment for an AI agent to write, test, and deploy code—including modifications to itself. The agent operates in an isolated container with no direct access to the host machine. All communication between the agent and the human operator (the "PM") occurs through git commits. The agent is the project: it builds and improves itself over time.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Host Machine                                                   │
│                                                                 │
│  /home/user/minifram-remote/  (bare git repo)                      │
│         ▲                                                       │
│         │ bind mount                                            │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Podman Container                                       │    │
│  │                                                         │    │
│  │  /mnt/remote  ◄──────────────────────────────────────┐  │    │
│  │                                                      │  │    │
│  │  /bot                                                │  │    │
│  │    /main                                             │  │    │
│  │      /minifram  (working directory) ◄── git pull/push ──┘  │    │
│  │    /feature-x                                           │    │
│  │      /minifram  (experimental branch)                      │    │
│  │                                                         │    │
│  │  Processes:                                             │    │
│  │    - watcher.py (monitors agent, handles crashes)       │    │
│  │    - runner.py  (LLM loop, executes agent logic)        │    │
│  │                                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  /home/user/minifram-working/  (user's working copy)               │
│    - User edits COMMS.md, pushes                                │
│    - User reviews branches, merges                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
/bot/<branch>/minifram/
├── SYSTEM.md              # Base system prompt
├── COMMS.md               # Directives and reports
├── /spec
│   └── SPEC_*.md          # Specifications (read into context as needed)
├── /infra
│   ├── runner.py          # Agent LLM loop
│   └── watcher.py         # Process monitor
├── /src
│   └── ...                # Agent code and any project code
└── /logs
    ├── bootstrap.log      # Bootstrap attempts and outcomes
    └── errors.log         # Captured errors and stderr
```

## Functional Requirements

### Container Isolation

- The container MUST block all network access to RFC1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- The container MUST block access to link-local addresses (169.254.0.0/16)
- The container MUST allow outbound internet access for LLM API calls and package installation
- The container MUST mount the host's bare git repo at /mnt/remote
- The container MUST drop all capabilities except those required for operation
- The container MUST run with no-new-privileges security option

### Git Communication

- The agent MUST use git as the sole mechanism for communicating with the outside world
- The agent MUST pull from /mnt/remote to receive updates
- The agent MUST push to /mnt/remote to publish changes
- The agent MUST commit changes before calling bootstrap
- The host MUST maintain a bare git repository for the agent remote
- The user MUST interact with the agent by cloning, editing, and pushing to the same bare repo

### Agent Tools

The agent MUST have access to the following tools:

- **read_file(path)** - Read contents of a file
- **write_file(path, content)** - Write contents to a file
- **bash(command)** - Execute a shell command
- **bootstrap(branch)** - Signal watcher to restart agent from specified branch
- **rollback(ref)** - Signal watcher to reset to specified git ref and restart

The agent SHOULD use bash for git operations, running tests, and other system tasks.

### Prompt Construction

- The system prompt MUST consist of SYSTEM.md followed by COMMS.md
- The user message MUST be "Continue."
- The agent MUST read SPEC_*.md files into context as needed during execution
- The agent MAY modify SYSTEM.md to change its own base behavior

### COMMS.md Format

- COMMS.md MUST contain a Directives section for PM instructions
- COMMS.md MUST contain a Reports section for agent status updates
- The PM SHOULD add directives by editing the Directives section and pushing
- The agent MUST append to the Reports section to communicate status
- The agent MAY add suggestions or questions to COMMS.md
- Pruning of COMMS.md SHOULD be a shared responsibility between PM and agent

### Spec Files

- Specification files MUST be stored in /spec with the naming pattern SPEC_*.md
- The PM MAY add or edit spec files to provide persistent requirements
- The agent MAY propose spec changes by editing files and committing to a branch
- Spec files SHOULD follow RFC 2119 language conventions

### Bootstrap Process

- The agent MUST write a BOOTSTRAPPING entry to bootstrap.log on startup
- The agent MUST write a SUCCESS entry to bootstrap.log after successful initialization
- The bootstrap log entry MUST include a timestamp and branch name
- If the watcher detects a missing SUCCESS entry after restart, it MUST fall back to main

### Hop-Scotch Upgrade Pattern

- The agent MUST modify code on a branch different from the one it is running on
- To upgrade, the running agent MUST:
    - Commit changes to the target branch
    - Push to remote
    - Call bootstrap(target_branch)
    - Exit
- The newly launched branch MUST:
    - Self-validate
    - Merge into main (if stable)
    - Call bootstrap("main")
    - Exit
- Only one agent process SHOULD run at a time

### Work Loop

- The agent MUST check COMMS.md for new directives at minimum every 10 minutes
- The agent MUST sleep until the next 10-minute interval after completing work
- A unit of work MAY span multiple files and include coding, testing, and validation
- The agent SHOULD use judgment to determine appropriate work boundaries

### Watcher Process

- The watcher MUST run as a separate process from the agent runner
- The watcher MUST check for a running agent process every 10 minutes
- The watcher MUST launch /bot/main/minifram if no agent process is found
- The watcher MUST monitor for signal files in .signal/ directory
- The watcher MUST handle bootstrap signals by launching the specified branch
- The watcher MUST handle rollback signals by resetting git and restarting
- The watcher SHOULD monitor for CPU runaway conditions
- The watcher SHOULD monitor for log file explosion
- The watcher MAY append critical messages to COMMS.md when intervention is needed

### Signal Mechanism

- The agent MUST signal watcher by writing to .signal/ directory
- Bootstrap signal MUST be written to .signal/bootstrap containing the target branch
- Rollback signal MUST be written to .signal/rollback containing the target git ref
- The watcher MUST delete signal files after processing
- Signal files MUST survive agent crashes

### Logging

- The logger MUST capture agent stdout and stderr to /logs/errors.log
- The agent MUST be able to read errors.log to investigate failures
- Bootstrap attempts MUST be logged to /logs/bootstrap.log
- The watcher SHOULD maintain its own operational log
- Log files MUST NOT be committed to git
- The /logs directory MUST be included in .gitignore

### Branch Directory Management

- Each branch MUST be cloned to /agent/<branch>/minifram/
- The agent MUST be responsible for creating branch directories via git clone
- The agent SHOULD clean up old branch directories after successful merge to main
- The watcher MUST only launch from /agent/main/minifram when recovering from crashes

## Non-Functional Requirements

### Security

- The container MUST NOT have access to host filesystem except the git mount
- The container SHOULD run rootless
- Git credentials MUST be scoped to the agent repository only
- The agent MUST NOT be able to access watcher process memory or signals except through defined mechanisms

### Reliability

- The system MUST recover from agent crashes by falling back to main
- The system MUST maintain git history for all changes
- The system SHOULD support rollback to any previous git ref
- The watcher MUST continue running even if agent repeatedly crashes

### Observability

- All agent errors MUST be captured to a readable log file
- All bootstrap attempts MUST be logged with timestamps and outcomes
- The PM MUST be able to review agent activity through git history

## Dependencies

**Container Runtime:**
- Podman for rootless container execution

**Network:**
- nftables for network isolation rules

**Version Control:**
- Git for all communication and state management

**Agent Runtime:**
- Python for watcher and runner infrastructure
- LLM API access (Claude or equivalent)

## Implementation Notes

### Bind Mount vs Network Git

Phase 1 uses a bind-mounted bare git repository for simplicity. This avoids credential management and network configuration. The attack surface is limited to git objects rather than arbitrary files. A future iteration MAY switch to network-based git (git daemon on a single port) for stronger isolation.

### Single Process Constraint

Only one agent process runs at a time to simplify watcher logic. The watcher cannot distinguish between multiple agent processes, so the hop-scotch pattern ensures clean handoffs.

### Context Window Management

SYSTEM.md and COMMS.md are included in every prompt. SPEC_*.md files are read into context on demand. The agent is responsible for managing context window limits. COMMS.md pruning is a shared responsibility.

### Bootstrap Log Interpretation

The watcher determines success by checking for a SUCCESS entry following the most recent BOOTSTRAPPING entry. Absence of SUCCESS indicates a crash during initialization, triggering fallback to main.

## Error Handling

The system MUST handle these error conditions:

- **Agent crash during startup** - Watcher falls back to /agent/main/minifram
- **Agent crash during work** - Watcher restarts from main, agent investigates via error logs
- **Bad bootstrap target** - Watcher attempts launch, fails, falls back to main
- **Git push failure** - Agent retries or reports in COMMS.md
- **LLM API failure** - Agent logs error, sleeps, retries on next interval
- **Runaway process** - Watcher MAY terminate and restart agent
- **Log explosion** - Watcher MAY terminate and alert via COMMS.md