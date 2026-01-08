# Axiom Trace

**Local-first, append-only trace vault for AI agents with cryptographic integrity and hybrid search.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/axiom-trace.svg)](https://badge.fury.io/py/axiom-trace)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install axiom-trace
```

For development:
```bash
git clone https://github.com/your-username/axiom-trace.git
cd axiom-trace
pip install -e ".[dev]"
```

## Quick Start

### Python SDK

```python
from axiom_trace import AxiomTrace

# Create or open a vault
with AxiomTrace("./my_vault") as trace:
    # Record an event
    frame_id = trace.record({
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "thought",
        "actor": {"type": "agent", "id": "my-agent"},
        "content": {
            "text": "Analyzing user request...",
            "rationale_summary": "Breaking down the problem"
        },
        "metadata": {"model_name": "gpt-4"}
    })
    
    # Query the vault
    results = trace.query("user request", limit=5)
    
    # Verify integrity
    status = trace.verify_integrity()
    print(f"Integrity OK: {status['ok']}")
```

### With Memvid Cloud (Optional)

For enhanced semantic search, create a `.env` file:

```bash
# Copy the example and add your key
cp .env.example .env
```

Then edit `.env`:
```
MEMVID_API_KEY=your-api-key-here
```

Or pass it directly in code:

```python
trace = AxiomTrace("./my_vault", memvid_api_key="your-api-key")
```

### Observer Pattern

```python
from axiom_trace import AxiomTrace, session, observe, set_global_trace

trace = AxiomTrace("./my_vault")
set_global_trace(trace)

# Context manager for sessions
with session(session_id="my-session") as obs:
    obs.record_user_input("What is the weather?")
    obs.record_thought("Need to call weather API", "Determining tool to use")
    obs.record_tool_call("weather_api", {"city": "NYC"})
    obs.record_tool_output("weather_api", {"temp": 72, "condition": "sunny"})
    obs.record_final_result("The weather in NYC is 72°F and sunny!")

# Decorator for automatic tracing
@observe(session_id="my-session")
def search_database(query: str) -> list:
    return ["result1", "result2"]
```

### CLI

```bash
# Record an event from JSON file
axiom record --vault ./my_vault --event event.json

# Query the vault
axiom query --vault ./my_vault --prompt "weather" --limit 5

# Export a session to Markdown
axiom export --vault ./my_vault --session <uuid> --out session.md

# Verify vault integrity
axiom verify --vault ./my_vault

# Show statistics
axiom stats --vault ./my_vault
```

## Event Types

| Type | Description |
|------|-------------|
| `thought` | Agent reasoning (requires `rationale_summary`) |
| `tool_call` | Tool invocation (requires `tool_name` in metadata) |
| `tool_output` | Tool result (requires `tool_name` in metadata) |
| `user_input` | User message |
| `final_result` | Final response |
| `system_event` | System notifications |
| `error` | Error with stack trace |

## Vault Structure

```
my_vault/
├── vault.manifest.json   # Metadata + head hash
├── vault.lock            # Write lock
├── vault.mv2             # Memvid index (optional)
├── frames.jsonl          # Append-only frame storage
└── axiom.log             # Internal logs
```

## Integrity Verification

Axiom Trace uses SHA-256 hash chains for tamper detection:

```python
result = trace.verify_integrity()
# {
#     "ok": True,
#     "checked_frames": 150,
#     "head_hash": "abc123...",
#     "error": None
# }
```

Detects:
- Modified frame content
- Deleted frames
- Reordered frames
- Manifest tampering

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MEMVID_API_KEY` | API key for Memvid cloud features (enhanced semantic search) |

## Publishing (for maintainers)

The package is automatically published to PyPI when you create a GitHub release:

1. Go to GitHub → Releases → "Create a new release"
2. Tag with version (e.g., `v1.1.0`)
3. Publish release

The GitHub Actions workflow handles building and uploading to PyPI.

## License

MIT
