# Axiom Trace

**Local-first, append-only trace vault for AI agents with cryptographic integrity.**

```bash
pip install axiom-trace
```

---

## Quick Start (3 Lines)

```python
from axiom_trace import trace

trace.log("Processing user request")
trace.thought("Need to fetch user data")
trace.tool("database_query", {"table": "users"})
trace.done("Found 10 users")
```

That's it! Traces are saved to `.axiom_trace/` in your project.

---

## View Your Traces

```bash
# Pretty print recent traces
axiom log

# Watch live (like tail -f)
axiom watch
```

**Output:**
```
────────────────────────────────────────────────────────────────────────────────
AXIOM TRACE LOG (4 entries)
────────────────────────────────────────────────────────────────────────────────
2026-01-09T03:56:43 system_event  Processing user request
2026-01-09T03:56:43 thought       Need to fetch user data
2026-01-09T03:56:43 tool_call     ✓ database_query
2026-01-09T03:56:43 final_result  ✓ Found 10 users
────────────────────────────────────────────────────────────────────────────────
```

---

## API Reference

### Quick Trace Methods

| Method | When to Use | Example |
|--------|-------------|---------|
| `trace.log(msg)` | Simple log message | `trace.log("Starting")` |
| `trace.thought(reasoning)` | Agent is thinking/deciding | `trace.thought("Need API call")` |
| `trace.tool(name, args)` | Calling a tool/function | `trace.tool("search", {"q": "..."})` |
| `trace.done(result)` | Task completed | `trace.done("Success!")` |
| `trace.error(msg, exc)` | Something failed | `trace.error("Failed", e)` |
| `trace.input(text)` | User said something | `trace.input("What's the weather?")` |

### Auto-Trace Decorator

```python
from axiom_trace import auto_trace

@auto_trace
def fetch_user(user_id: int):
    return db.get(user_id)

# Automatically captures: function name, args, result, timing, exceptions
```

---

## Agent-Friendly Fields

Traces include fields designed for AI agent retrospection:

```python
trace.record({
    "event_type": "tool_call",
    "content": {
        "input": "User asked: Build REST API",      # What prompted this
        "output": "Created api/users.py",           # What was produced
        "reasoning": "Need CRUD endpoints"          # Why this action
    },
    "success": True,                                # Did it work?
    "artifacts": ["api/users.py"],                  # Files created
    "caused_by": "previous-frame-id"                # Causality chain
})
```

---

## Memvid Cloud (Optional)

For enhanced semantic search, add your Memvid API key:

```bash
# In your project's .env file
MEMVID_API_KEY=mv2_your_key_here
```

Axiom Trace automatically loads from `.env` when you import it.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `axiom log` | Pretty print recent traces |
| `axiom watch` | Live trace monitoring |
| `axiom query --prompt "..."` | Search traces semantically |
| `axiom verify` | Check hash chain integrity |
| `axiom stats` | Show vault statistics |
| `axiom export --session ID` | Export session to Markdown |

---

## Advanced: Full API

For more control, use the `AxiomTrace` class directly:

```python
from axiom_trace import AxiomTrace

with AxiomTrace(vault_dir="./my_vault") as ax:
    # Record with full control
    ax.record({
        "event_type": "thought",
        "content": {
            "text": "Analyzing request",
            "rationale_summary": "Need to understand intent"
        }
    })
    
    # Query with semantic search
    results = ax.query("user request", limit=5)
    
    # Verify integrity
    status = ax.verify_integrity()
```

---

## Vault Structure

```
.axiom_trace/
├── frames.jsonl           # Your traces (one JSON per line)
├── vault.manifest.json    # Metadata + head hash
├── vault_index.json       # Search index
└── vault.mv2              # Memvid video index
```

---

## Why Axiom Trace?

- **Local-first** - Data stays on your machine
- **Append-only** - Can't delete or modify past traces
- **Tamper-evident** - SHA-256 hash chain detects modifications
- **Agent-friendly** - Fields designed for AI retrospection
- **Zero config** - Works out of the box

---

## License

MIT
