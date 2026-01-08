# Axiom Trace

**Local-first, append-only trace vault for AI agents with cryptographic integrity and hybrid search.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/axiom-trace.svg)](https://badge.fury.io/py/axiom-trace)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install axiom-trace
```

## Quick Start

```python
from axiom_trace import AxiomTrace

# Create a vault (defaults to .axiom_trace/ in current directory)
with AxiomTrace() as trace:
    # Record an event
    frame_id = trace.record({
        "event_type": "thought",
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

---

## Memvid Cloud Integration (Optional)

Axiom Trace uses [Memvid](https://memvid.com) for hybrid semantic search. You can enhance search quality with a Memvid API key.

### Setup in Your Project

1. **Create a `.env` file in your project root:**

```bash
# In your project directory (e.g., my_project/)
echo "MEMVID_API_KEY=mv2_your_api_key_here" > .env

# Add to .gitignore to keep it secure
echo ".env" >> .gitignore
```

2. **That's it!** Axiom Trace automatically loads the key:

```python
from axiom_trace import AxiomTrace

# Automatically uses MEMVID_API_KEY from your project's .env
trace = AxiomTrace()
```

### Alternative: Pass Key Directly

```python
trace = AxiomTrace(memvid_api_key="mv2_your_api_key_here")
```

### How It Works

```
your_project/
├── .env                 ← Put MEMVID_API_KEY here
├── .gitignore          ← Add .env to keep key secure
├── main.py             ← from axiom_trace import AxiomTrace
└── .axiom_trace/       ← Default vault location
```

When you import `axiom_trace`, it uses `python-dotenv` to load your project's `.env` file automatically.

---

## Observer Pattern

```python
from axiom_trace import AxiomTrace, session, observe, set_global_trace

trace = AxiomTrace()
set_global_trace(trace)

# Context manager for sessions
with session(session_id="my-session") as obs:
    obs.record_user_input("What is the weather?")
    obs.record_thought("Need to call weather API", "Determining tool to use")
    obs.record_tool_call("weather_api", {"city": "NYC"})
    obs.record_tool_output("weather_api", {"temp": 72, "condition": "sunny"})
    obs.record_final_result("The weather in NYC is 72°F and sunny!")

# Decorator for automatic tracing
@observe(event_type="tool_call")
def search_database(query: str) -> list:
    return ["result1", "result2"]
```

---

## CLI

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

---

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

---

## Vault Structure

```
.axiom_trace/              # Default location (or specify your own)
├── vault.manifest.json    # Metadata + head hash
├── vault.lock             # Write lock
├── vault.mv2              # Memvid index
├── frames.jsonl           # Append-only frame storage
└── axiom.log              # Internal logs
```

---

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

Detects: modified content, deleted frames, reordered frames, manifest tampering.

---

## API Reference

### `AxiomTrace(vault_dir=None, memvid_api_key=None, ...)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vault_dir` | `.axiom_trace/` | Vault storage location |
| `memvid_api_key` | From `.env` | Memvid API key for cloud features |
| `redaction_enabled` | `True` | Auto-redact secrets |
| `auto_flush` | `True` | Background flush every 5s |

### Methods

- `record(event)` → `str` (frame_id)
- `query(prompt, limit=5, filters=None)` → `list[dict]`
- `export_session(session_id, out_path, format="md")`
- `verify_integrity()` → `dict`
- `stats()` → `dict`
- `close()`

---

## License

MIT
